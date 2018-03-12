#
# Copyright (C) 2018 Zubax Robotics OU
#
# This file is part of Kucher.
# Kucher is free software: you can redistribute it and/or modify it under the terms of the GNU General Public License
# as published by the Free Software Foundation, either version 3 of the License, or (at your option) any later version.
# Kucher is distributed in the hope that it will be useful, but WITHOUT ANY WARRANTY; without even the implied warranty
# of MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU General Public License for more details.
# You should have received a copy of the GNU General Public License along with Kucher.
# If not, see <http://www.gnu.org/licenses/>.
#
# Author: Pavel Kirienko <pavel.kirienko@zubax.com>
#

import time
import enum
import typing
import asyncio
import datetime
import functools
import itertools
import dataclasses
from logging import getLogger
from PyQt5.QtWidgets import QWidget
from PyQt5.QtCore import Qt, QAbstractItemModel, QModelIndex, QVariant, QRect
from PyQt5.QtGui import QPalette, QFontMetrics, QFont, QPixmap, QPainter, QBitmap
from view.utils import gui_test, get_monospace_font, get_icon
from view.device_model_representation import Register


_logger = getLogger(__name__)


_NAME_SEGMENT_SEPARATOR = '.'


# noinspection PyMethodOverriding
class Model(QAbstractItemModel):
    """
    As it turns out, the interface we're implementing here is quite complex.
    This tutorial is somewhat useful: http://doc.qt.io/qt-5/qtwidgets-itemviews-simpletreemodel-example.html
    """

    _COLUMNS = [
        'Tree',
        'Type',
        'Value',
        'Default',
        'Min',
        'Max',
        'Flags',
        'Device timestamp',
        'Full name',
    ]

    class _ColumnIndices(enum.IntEnum):
        NAME             = 0
        TYPE             = 1
        VALUE            = 2
        DEFAULT          = 3
        MIN              = 4
        MAX              = 5
        FLAGS            = 6
        DEVICE_TIMESTAMP = 7
        FULL_NAME        = 8

    def __init__(self,
                 parent: QWidget,
                 registers: typing.Iterable[Register]):
        super(Model, self).__init__(parent)

        self._regular_font = get_monospace_font()

        self._underlined_font = get_monospace_font()
        self._underlined_font.setUnderline(True)

        self._italic_font = get_monospace_font()
        self._italic_font.setItalic(True)

        self._icon_size = QFontMetrics(QFont()).height()

        self._registers = list(sorted(registers, key=lambda r: r.name))

        self._tree = _plant_tree(self._registers)
        _logger.debug('Register tree:\n%s\n', self._tree.to_pretty_string())

        # This map contains references from register name to the model index pointing to the zero column
        self._register_name_to_index_column_zero_map: typing.Dict[str, QModelIndex] = {}

        def build_index(root: QModelIndex):
            for row in itertools.count():
                index = self.index(row, 0, root)
                if index.isValid():
                    build_index(index)
                    try:
                        self._register_name_to_index_column_zero_map[self._unwrap(index).register.name] = index
                    except AttributeError:
                        pass
                else:
                    break

        build_index(QModelIndex())
        _logger.info('Register look-up table: %r', self._register_name_to_index_column_zero_map)

        # Set up register update callbacks decoupled via weak references
        # It is important to use weak references because we don't want the events to keep our object alive
        for r in self._registers:
            r.update_event.connect_weak(self, Model._on_register_update)

    async def reload_all(self, progress_callback: typing.Optional[typing.Callable[[Register, int, int], None]]=None):
        """
        :param progress_callback: (register: Register, current_register_index: int, total_registers: int) -> None
        """
        progress_callback = progress_callback if progress_callback is not None else lambda *_: None

        _logger.info('Reload-all: %r registers to go', len(self._registers))

        # Mark all for update
        for r in self._registers:
            # Great Scott! One point twenty-one gigawatt of power!
            node = self._unwrap(self._register_name_to_index_column_zero_map[r.name])
            node.set_state(_Node.State.PENDING, 'Waiting for update...')

        # Actually update all
        for index, r in enumerate(self._registers):
            progress_callback(r, index, len(self._registers))
            node = self._unwrap(self._register_name_to_index_column_zero_map[r.name])
            # noinspection PyBroadException
            try:
                await r.read_through()
            except asyncio.CancelledError:
                raise
            except Exception as ex:
                _logger.exception('Reload-all progress: Could not read %r', r)
                node.set_state(node.State.ERROR, f'Update failed: {ex}')
            else:
                _logger.info('Reload-all progress: Read %r', r)
                node.set_state(node.State.DEFAULT)

    @staticmethod
    def get_register_from_index(index: QModelIndex) -> Register:
        """Returns None if no register is bound to the index."""
        return Model._unwrap(index).register

    def index(self, row: int, column: int, parent: QModelIndex=None) -> QModelIndex:
        if column >= self.columnCount(parent):
            return QModelIndex()

        try:
            return self.createIndex(row, column, self._resolve_parent_node(parent)[row])
        except IndexError:
            return QModelIndex()

    def parent(self, index: QModelIndex) -> QModelIndex:
        parent_node = self._unwrap(index).parent
        # We must not let the consumer access the root of the tree, because that would create a lone top level item
        # in the widget. We don't want that, hence we return an invalid index if the parent of the current index
        # is the root of the list.
        if parent_node is not None and parent_node.parent is not None:
            # Index in parent equals row.
            # Column is set to zero because only zero-column items have children, this is per the Qt's conventions.
            # http://doc.qt.io/qt-5/qtwidgets-itemviews-simpletreemodel-example.html
            return self.createIndex(parent_node.index_in_parent, 0, parent_node)
        else:
            return QModelIndex()

    def rowCount(self, parent: QModelIndex=None) -> int:
        # Only zero-column items have children, this is per the Qt's conventions.
        # http://doc.qt.io/qt-5/qtwidgets-itemviews-simpletreemodel-example.html
        if parent is not None and parent.column() > 0:
            return 0

        return len(self._resolve_parent_node(parent).children)

    def columnCount(self, parent: QModelIndex=None) -> int:
        return len(self._COLUMNS)

    def data(self, index: QModelIndex, role: int=None):
        row, column = index.row(), index.column()
        node = self._unwrap(index)
        assert node.index_in_parent == row  # These two represent the same concept at different levels of abstraction

        column_indices = self._ColumnIndices

        if role == Qt.DisplayRole:
            if column == column_indices.NAME:
                return node.name

            if node.register is None:
                return str()

            if column == column_indices.TYPE:
                out = str(node.register.type_id).split('.')[-1].lower()
                if node.register.cached_value and not isinstance(node.register.cached_value, (str, bytes)):
                    size = len(node.register.cached_value)
                    if size > 1:
                        out += f'[{size}]'

                return out

            if column == column_indices.VALUE:
                return display_value(node.register.cached_value, node.register.type_id)

            if column == column_indices.DEFAULT:
                return display_value(node.register.default_value, node.register.type_id)

            if column == column_indices.MIN:
                return display_value(node.register.min_value, node.register.type_id)

            if column == column_indices.MAX:
                return display_value(node.register.max_value, node.register.type_id)

            if column == column_indices.DEVICE_TIMESTAMP:
                return str(datetime.timedelta(seconds=float(node.register.update_timestamp_device_time)))

            if column == column_indices.FULL_NAME:
                return node.register.name

        if role in (Qt.ToolTipRole, Qt.StatusTipRole):
            if column == column_indices.NAME:
                if node.message.strip():
                    return node.message

            if column == column_indices.VALUE:
                if node.register is not None:
                    out = f'This register is {"mutable" if node.register.mutable else "immutable"}. '
                    if node.register.mutable and node.register.has_default_value:
                        if node.register.cached_value_is_default_value:
                            out += 'Current value is default value.'
                        else:
                            out += 'Current value differs from the default value.'
                    return out

            if column == column_indices.FLAGS:
                if node.register is not None:
                    return ', '.join([
                        'mutable' if node.register.mutable else 'immutable',
                        'persistent' if node.register.persistent else 'not persistent',
                    ]).capitalize()

            if column == column_indices.DEVICE_TIMESTAMP:
                if node.register is not None:
                    delta = time.monotonic() - node.register.update_timestamp_monotonic
                    return f'Last synchronized {round(delta)} seconds ago'

        if role == Qt.ForegroundRole:
            palette = QPalette()
            if node.register and (self.flags(index) & Qt.ItemIsEditable):
                if node.register.cached_value_is_default_value or not node.register.has_default_value:
                    return palette.color(QPalette.Link)
                else:
                    return palette.color(QPalette.LinkVisited)
            else:
                return palette.color(QPalette.WindowText)

        if role == Qt.BackgroundRole:
            palette = QPalette()
            if column in (0, column_indices.VALUE, len(self._COLUMNS) - 1):
                return palette.color(QPalette.Base)
            else:
                return palette.color(QPalette.AlternateBase)

        if role == Qt.FontRole:
            if node.state == node.State.PENDING:
                return self._italic_font

            if self.flags(index) & Qt.ItemIsEditable:
                return self._underlined_font
            else:
                return self._regular_font

        if role == Qt.DecorationRole:
            if node.register is not None:
                if column == column_indices.NAME:
                    try:
                        return get_icon({
                            _Node.State.PENDING: 'process',
                            _Node.State.SUCCESS: 'ok',
                            _Node.State.ERROR:   'error',
                        }[node.state])
                    except KeyError:
                        pass

                if column == column_indices.FLAGS:
                    return _draw_flags_icon(mutable=node.register.mutable,
                                            persistent=node.register.persistent,
                                            icon_size=self._icon_size)

        return QVariant()

    def setData(self, index: QModelIndex, value, role: int=None) -> bool:
        # As per http://doc.qt.io/qt-5/model-view-programming.html
        if not index.isValid() or role != Qt.EditRole:
            return False

        node = self._unwrap(index)
        if node.register is None:
            raise ValueError(f'The specified index {index} has no register associated with it')

        if not node.register.mutable:
            raise ValueError(f'The register is immutable: {node.register}')

        async def executor():
            node.set_state(node.State.PENDING, 'Write in progress...')
            self._invalidate(index)
            # noinspection PyBroadException
            try:
                _logger.info('Writing register %r with %r', node.register, value)
                new_value = await node.register.write_through(value)
            except Exception as ex:
                _logger.exception('Could not write register %r', node.register)
                node.set_state(node.State.ERROR, f'Write failed: {ex}')
            else:
                _logger.info('Write to %r complete; new value: %r', node.register, new_value)
                node.set_state(node.State.SUCCESS, 'Value has been written successfully')
            finally:
                self._invalidate(index)

        asyncio.get_event_loop().create_task(executor())
        return True

    def flags(self, index: QModelIndex) -> int:
        node = self._unwrap(index)
        out = Qt.ItemIsEnabled
        if node and node.register and node.register.type_id != Register.ValueType.EMPTY:
            out |= Qt.ItemIsSelectable
            if node.register.mutable and index.column() == self._ColumnIndices.VALUE:
                if node.state != node.State.PENDING:
                    out |= Qt.ItemIsEditable

        return out

    def headerData(self, section: int, orientation: int, role: int=None):
        if orientation == Qt.Horizontal:
            if role == Qt.DisplayRole:
                return self._COLUMNS[section]

        return QVariant()

    # noinspection PyArgumentList,PyUnresolvedReferences
    def _invalidate(self, index_or_register: typing.Union[QModelIndex, Register]):
        if isinstance(index_or_register, Register):
            index = self._register_name_to_index_column_zero_map[index_or_register.name]
        elif isinstance(index_or_register, QModelIndex):
            index = index_or_register
        else:
            raise TypeError(f'Unexpected type: {type(index_or_register)}')

        top_left: QModelIndex = index.sibling(index.row(), 0)
        bottom_right: QModelIndex = index.sibling(index.row(), self.columnCount(index.parent()) - 1)
        assert top_left.isValid()
        assert bottom_right.isValid()
        self.dataChanged.emit(top_left, bottom_right)

    def _on_register_update(self, register: Register):
        """
        This is invoked by Register objects when they get updated.
        Note that when we write a new value, this callback is invoked as well!
        """
        index = self._register_name_to_index_column_zero_map[register.name]
        node = self._unwrap(index)
        node.set_state(node.State.DEFAULT)
        self._invalidate(index)

    def _resolve_parent_node(self, index: typing.Optional[QModelIndex]) -> '_Node':
        if index is None or not index.isValid():
            return self._tree
        else:
            return self._unwrap(index)

    @staticmethod
    def _unwrap(index: QModelIndex) -> '_Node':
        return index.internalPointer()


def display_value(value, type_id: Register.ValueType) -> str:
    """
    Converts a register value to human-readable text.
    """
    def format_scalar(x) -> str:
        if type_id == Register.ValueType.F32:
            return '{:7g}'.format(x).strip()
        elif type_id == Register.ValueType.F64:
            return '{:16g}'.format(x).strip()
        else:
            return str(x)

    if value is None:
        return ''
    elif isinstance(value, (str, bytes)):
        return str(value)
    else:
        return ', '.join(map(format_scalar, value))


def parse_value(text: str, type_id: Register.ValueType):
    """
    Inverse to @ref display_value().
    """
    def impl():
        if type_id == Register.ValueType.EMPTY:
            return None

        if type_id == Register.ValueType.STRING:
            return text

        if type_id == Register.ValueType.UNSTRUCTURED:
            return text.encode('latin1')

        if str(Register.ValueType(type_id)).split('.')[-1][0].lower() == 'f':
            native_type = float
        else:
            native_type = int

        # Normalize the case and resolve some special values
        normalized = text.lower().replace('true', '1').replace('false', '0')

        return [native_type(x) for x in normalized.split(',')]

    value = impl()
    _logger.info('Value parser [with type %r]: %r --> %r', type_id, text, value)
    return value


@dataclasses.dataclass
class _Node:
    """
    An element of the register tree.
    Each element may have at most one register and an arbitrary number of children.
    Each child node is referred to by the name of its segment.
    """
    parent:   typing.Optional['_Node']                  # Only the root node doesn't have one
    name:     str
    register: typing.Optional[Register]        = None
    children: typing.DefaultDict[str, '_Node'] = dataclasses.field(default_factory=dict)

    class State(enum.Enum):
        DEFAULT = enum.auto()
        PENDING = enum.auto()
        SUCCESS = enum.auto()
        ERROR   = enum.auto()

    state:    State = State.DEFAULT
    message:  str = ''

    def set_state(self, state: '_Node.State', message: str=''):
        self.message = message
        self.state = self.State(state)

    def __getitem__(self, item: typing.Union[str, int]) -> '_Node':
        if isinstance(item, str):
            return self.children[item]
        else:
            return list(self.children.values())[item]

    def __setitem__(self, item: str, value: '_Node'):
        self.children[item] = value

    def __contains__(self, item) -> bool:
        return item in self.children

    @property
    def index_in_parent(self) -> int:
        """Computes the index of the current node in its parent. If it has no parent, returns zero."""
        if self.parent is None:
            return 0

        for index, nm in enumerate(self.parent.children.keys()):
            if nm == self.name:
                return index

        raise ValueError(f'Invalid tree: item {self!r} is not owned by its parent {self.parent!r}')

    def to_pretty_string(self, _depth=0) -> str:
        """Traverses the tree in depth starting from the current node and returns a neat multi-line formatted string"""
        return ''.join(map(lambda x: '\n'.join([(' ' * _depth * 4 + x[0]).ljust(40) + ' ' + str(x[1].register or ''),
                                                x[1].to_pretty_string(_depth + 1)]),
                           self.children.items())).rstrip('\n' if not _depth else '')


def _plant_tree(registers: typing.Iterable[Register]) -> _Node:
    """
    Transforms a flat list of registers into an hierarchical tree.
    """
    root = _Node(None, '')      # No parent, no name
    for reg in registers:
        node = root
        for segment in reg.name.split(_NAME_SEGMENT_SEPARATOR):     # Traverse until the last segment
            if segment not in node:
                node[segment] = _Node(node, segment)

            node = node[segment]

        assert node.register is None
        node.register = reg

    return root


@functools.lru_cache()
def _draw_flags_icon(mutable: bool, persistent: bool, icon_size: int) -> QPixmap:
    """
    Combines icons into a single large icon and renders it into a pixmap of specified size.
    This operation is quite resource-consuming (we're drawing pictures after all, ask Picasso),
    so we cache the results in a LRU cache.
    """
    icon_name = 'edit' if mutable else 'lock'
    mutability: QPixmap = get_icon(icon_name).pixmap(icon_size, icon_size)

    # https://youtu.be/AX2uz2XYkbo?t=21s
    icon_name = 'save' if persistent else 'random-access-memory'
    persistence: QPixmap = get_icon(icon_name).pixmap(icon_size, icon_size)

    icon_size_rect = QRect(0, 0, icon_size, icon_size)

    pixmap = QPixmap(icon_size * 2, icon_size)
    mask = QBitmap(pixmap.width(), pixmap.height())
    mask.clear()
    pixmap.setMask(mask)

    painter = QPainter(pixmap)
    painter.drawPixmap(icon_size_rect, mutability, icon_size_rect)
    painter.drawPixmap(QRect(icon_size, 0, icon_size, icon_size),
                       persistence, icon_size_rect)
    return pixmap


def _unittest_parse_value():
    from pytest import approx
    tid = Register.ValueType
    assert parse_value('', tid.EMPTY) is None
    assert parse_value('Arbitrary', tid.EMPTY) is None
    assert parse_value('Arbitrary', tid.STRING) == 'Arbitrary'
    assert parse_value('\x01\x02\x88\xFF', tid.UNSTRUCTURED) == bytes([1, 2, 0x88, 0xFF])
    assert parse_value('0', tid.BOOLEAN) == [False]
    assert parse_value('True, false', tid.BOOLEAN) == [True, False]
    assert parse_value('true, False', tid.I8) == [1, 0]
    assert parse_value('0.123, 56.45', tid.F32) == [approx(0.123), approx(56.45)]
    assert parse_value('0.123, 56.45', tid.F64) == [approx(0.123), approx(56.45)]


def _unittest_register_tree():
    from ._mock_registers import get_mock_registers

    # noinspection PyTypeChecker
    tree = _plant_tree(get_mock_registers())
    print('Register tree view:', tree.to_pretty_string(), sep='\n')

    uavcan_transfer_cnt_tx = tree['uavcan']['transfer_cnt']['tx']
    assert uavcan_transfer_cnt_tx.register.name == 'uavcan.transfer_cnt.tx'
    assert uavcan_transfer_cnt_tx.parent['tx'].register.name == 'uavcan.transfer_cnt.tx'


# noinspection PyArgumentList
@gui_test
def _unittest_register_tree_model():
    import gc
    from PyQt5.QtWidgets import QApplication, QMainWindow, QTreeView, QHeaderView, QStyleOptionViewItem
    from ._mock_registers import get_mock_registers
    from .editor_delegate import EditorDelegate
    from .style_option_modifying_delegate import StyleOptionModifyingDelegate

    app = QApplication([])
    win = QMainWindow()

    tw = QTreeView(win)
    tw.setItemDelegate(EditorDelegate(tw))
    tw.setItemDelegateForColumn(0, StyleOptionModifyingDelegate(tw, QStyleOptionViewItem.Right))
    tw.setStyleSheet('''
    QTreeView::item { padding: 0 5px; }
    ''')

    header: QHeaderView = tw.header()
    header.setSectionResizeMode(QHeaderView.ResizeToContents)
    header.setStretchLastSection(False)     # Horizontal scroll bar doesn't work if this is enabled

    registers = get_mock_registers()
    for r in registers:
        assert r.update_event.num_handlers == 0

    model = Model(win, registers)
    tw.setModel(model)

    for r in registers:
        assert r.update_event.num_handlers == 1

    win.setCentralWidget(tw)
    win.show()

    good_night_sweet_prince = False

    async def run_events():
        while not good_night_sweet_prince:
            app.processEvents()
            await asyncio.sleep(0.01)

    async def walk():
        nonlocal good_night_sweet_prince
        await asyncio.sleep(5)
        good_night_sweet_prince = True

    asyncio.get_event_loop().run_until_complete(asyncio.gather(
        run_events(),
        walk()
    ))

    win.close()

    # At the very end, making sure that our registers do not keep the model alive via weak callback references
    del tw
    del win
    del app
    gc.collect()

    print('Model references:', gc.get_referrers(model))
    del model
    gc.collect()

    for r in registers:
        assert r.update_event.num_handlers == 1
        r.update_event.emit(r)
        assert r.update_event.num_handlers == 0

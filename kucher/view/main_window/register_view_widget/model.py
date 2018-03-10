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

import enum
import typing
import datetime
import functools
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

        self._icon_size = QFontMetrics(QFont()).height()

        registers = list(sorted(registers, key=lambda r: r.name))

        self._default_tree = _plant_tree(registers)
        _logger.debug('Default tree:\n%s\n', self._default_tree.to_pretty_string())
        # TODO: Trees grouped by mutability and persistence

    def reload(self, register: Register):
        pass    # TODO: locate the register in the tree and invalidate it

    @staticmethod
    def get_register_from_index(index: QModelIndex) -> Register:
        """Returns None if no register is bound to the index."""
        return Model._unwrap(index).value

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

            if node.value is None:
                return str()

            if column == column_indices.TYPE:
                out = str(node.value.type_id).split('.')[-1].lower().replace('boolean', 'bool')
                if node.value.cached_value and not isinstance(node.value.cached_value, (str, bytes)):
                    size = len(node.value.cached_value)
                    if size > 1:
                        out += f'[{size}]'

                return out

            if column == column_indices.VALUE:
                return display_value(node.value.cached_value, node.value.type_id)

            if column == column_indices.DEFAULT:
                return display_value(node.value.default_value, node.value.type_id)

            if column == column_indices.MIN:
                return display_value(node.value.min_value, node.value.type_id)

            if column == column_indices.MAX:
                return display_value(node.value.max_value, node.value.type_id)

            if column == column_indices.DEVICE_TIMESTAMP:
                return str(datetime.timedelta(seconds=float(node.value.update_timestamp_device_time)))

            if column == column_indices.FULL_NAME:
                return node.value.name

        if role in (Qt.ToolTipRole, Qt.StatusTipRole):
            if column == column_indices.VALUE:
                if node.value is not None:
                    out = f'This register is {"mutable" if node.value.mutable else "immutable"}. '
                    if node.value.mutable and node.value.has_default_value:
                        if node.value.cached_value_is_default_value:
                            out += 'Current value is default value.'
                        else:
                            out += 'Current value differs from the default value.'
                    return out

            if column == column_indices.FLAGS:
                if node.value is not None:
                    return ', '.join([
                        'mutable' if node.value.mutable else 'immutable',
                        'persistent' if node.value.persistent else 'not persistent',
                    ]).capitalize()

        if role == Qt.ForegroundRole:
            palette = QPalette()
            if node.value and (self.flags(index) & Qt.ItemIsEditable):
                if node.value.cached_value_is_default_value or not node.value.has_default_value:
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
            if self.flags(index) & Qt.ItemIsEditable:
                return self._underlined_font
            else:
                return self._regular_font

        if role == Qt.DecorationRole:
            if node.value is not None:
                if column == column_indices.FLAGS:
                    return _draw_flags_icon(mutable=node.value.mutable,
                                            persistent=node.value.persistent,
                                            icon_size=self._icon_size)

        return QVariant()

    def setData(self, index: QModelIndex, value, role=None) -> bool:
        # TODO: Execute request to the device! Right now we're just changing the data locally, for testing
        # noinspection PyProtectedMember
        self._unwrap(index).value._cached_value = Register._stricten(value)
        return True

    def flags(self, index: QModelIndex) -> int:
        node = self._unwrap(index)
        out = Qt.ItemIsEnabled
        if node and node.value and node.value.type_id != Register.ValueType.EMPTY:
            out |= Qt.ItemIsSelectable
            if node.value.mutable and index.column() == self._ColumnIndices.VALUE:
                out |= Qt.ItemIsEditable

        return out

    def headerData(self, section: int, orientation: int, role: int=None):
        if orientation == Qt.Horizontal:
            if role == Qt.DisplayRole:
                return self._COLUMNS[section]

        return QVariant()

    def _resolve_parent_node(self, index: typing.Optional[QModelIndex]) -> '_Node':
        if index is None or not index.isValid():
            return self._default_tree
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
    raise NotImplementedError('Parser is not yet implemented')


@dataclasses.dataclass
class _Node:
    """
    An element of a register tree.
    Each element may have at most one value and an arbitrary number of children.
    Each child node is referred to by the name of its segment.
    """
    parent:   typing.Optional['_Node']                  # Only the root node doesn't have one
    name:     str
    value:    typing.Optional[Register]        = None
    children: typing.DefaultDict[str, '_Node'] = dataclasses.field(default_factory=dict)

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
        return ''.join(map(lambda x: '\n'.join([(' ' * _depth * 4 + x[0]).ljust(40) + ' ' + str(x[1].value or ''),
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

        assert node.value is None
        node.value = reg

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
    icon_name = 'sd' if persistent else 'random-access-memory'
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


def _unittest_register_tree():
    from ._mock_registers import get_mock_registers

    # noinspection PyTypeChecker
    tree = _plant_tree(get_mock_registers())
    print('Register tree view:', tree.to_pretty_string(), sep='\n')

    uavcan_transfer_cnt_tx = tree['uavcan']['transfer_cnt']['tx']
    assert uavcan_transfer_cnt_tx.value.name == 'uavcan.transfer_cnt.tx'
    assert uavcan_transfer_cnt_tx.parent['tx'].value.name == 'uavcan.transfer_cnt.tx'


# noinspection PyArgumentList
@gui_test
def _unittest_register_tree_model():
    import time
    from PyQt5.QtWidgets import QApplication, QMainWindow, QTreeView, QHeaderView
    from ._mock_registers import get_mock_registers
    from .editor_delegate import EditorDelegate

    app = QApplication([])
    win = QMainWindow()

    tw = QTreeView(win)
    tw.setItemDelegate(EditorDelegate(tw))
    tw.setStyleSheet('''
    QTreeView::item { padding: 0 5px; }
    ''')

    header: QHeaderView = tw.header()
    header.setSectionResizeMode(QHeaderView.ResizeToContents)
    header.setStretchLastSection(False)     # Horizontal scroll bar doesn't work if this is enabled

    model = Model(win, get_mock_registers())
    tw.setModel(model)

    win.setCentralWidget(tw)
    win.show()

    def go_go_go():
        for _ in range(1000):
            time.sleep(0.001)
            app.processEvents()

    while True:
        go_go_go()

    win.close()

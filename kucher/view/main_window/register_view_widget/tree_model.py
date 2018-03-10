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
import dataclasses
from logging import getLogger
from PyQt5.QtWidgets import QWidget
from PyQt5.QtCore import Qt, QAbstractItemModel, QModelIndex, QVariant
from view.utils import gui_test
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
        'Name',             # E.g. "register"
        'Type',             # E.g. "F32[2]" or "U8"; icon representing mutability and persistence
        'Value',            # Value as is; scalars should be simplified (unwrapped, i.e. "123" not "[123]")
        'DTS',              # Update timestamp, device time; show age on hover (tooltip)?
    ]

    class _ColumnIndices(enum.IntEnum):
        NAME = 0
        TYPE = 1
        VALUE = 2
        DEVICE_TIMESTAMP = 3

    def __init__(self,
                 parent: QWidget,
                 registers: typing.Iterable[Register]):
        super(Model, self).__init__(parent)

        self._default_tree = _plant_tree(registers)
        # TODO: Trees grouped by mutability and persistence

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

        if role == Qt.DisplayRole:
            if column == self._ColumnIndices.NAME:
                return node.name

            if node.value is None:
                return str()

            if column == self._ColumnIndices.TYPE:
                out = str(node.value.type_id).split('.')[-1].lower().replace('boolean', 'bool')
                if node.value.cached_value and not isinstance(node.value.cached_value, (str, bytes)):
                    size = len(node.value.cached_value)
                    if size > 1:
                        out += f'[{size}]'

                return out

            if column == self._ColumnIndices.VALUE:
                def format_scalar(x) -> str:
                    if node.value.type_id == Register.ValueType.F32:
                        return '{:7g}'.format(x).strip()
                    elif node.value.type_id == Register.ValueType.F64:
                        return '{:16g}'.format(x).strip()
                    else:
                        return str(x)

                if node.value.cached_value is None:
                    return ''
                elif isinstance(node.value.cached_value, (str, bytes)):
                    return str(node.value.cached_value)
                else:
                    return ', '.join(map(format_scalar, node.value.cached_value))

            if column == self._ColumnIndices.DEVICE_TIMESTAMP:
                return str(datetime.timedelta(seconds=float(node.value.update_timestamp_device_time)))

        return QVariant()

    def setData(self, index: QModelIndex, value, role=None) -> bool:
        return False        # TODO: Editable fields

    def flags(self, index: QModelIndex) -> int:
        node = self._unwrap(index)
        out = Qt.ItemIsSelectable | Qt.ItemIsEnabled
        if node and node.value and index.column() == self._ColumnIndices.VALUE:
            if node.value.mutable:
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


def _unittest_register_tree():
    def print_tree(node: _Node, indent=0):
        for segment, ch in node.children.items():
            print((' ' * indent * 4 + segment).ljust(40), ch.value.name if ch.value else '')
            print_tree(ch, indent + 1)

    # noinspection PyTypeChecker
    tree = _plant_tree(_get_mock_registers())
    print('Register tree view:')
    print_tree(tree)

    uavcan_transfer_cnt_tx = tree['uavcan']['transfer_cnt']['tx']
    assert uavcan_transfer_cnt_tx.value.name == 'uavcan.transfer_cnt.tx'
    assert uavcan_transfer_cnt_tx.parent['tx'].value.name == 'uavcan.transfer_cnt.tx'


# noinspection PyArgumentList
@gui_test
def _unittest_register_tree_model():
    import time
    from PyQt5.QtWidgets import QApplication, QMainWindow, QTreeView
    from view.utils import get_monospace_font

    app = QApplication([])
    win = QMainWindow()

    tw = QTreeView(win)
    tw.setFont(get_monospace_font())

    model = Model(win, _get_mock_registers())
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


def _get_mock_registers():
    from decimal import Decimal

    # noinspection PyPep8Naming
    ValueType = Register.ValueType

    @dataclasses.dataclass
    class Flags:
        mutable: bool
        persistent: bool

    @dataclasses.dataclass
    class Mock:
        timestamp: Decimal
        flags: Flags
        name: str
        type_id: ValueType
        value: typing.Union[str, bytes, list]

        @property
        def cached_value(self):
            return self.value

        @property
        def update_timestamp_device_time(self) -> Decimal:
            return Decimal(self.timestamp)

        @property
        def update_timestamp_monotonic(self) -> float:
            return float(self.timestamp)

        @property
        def mutable(self) -> bool:
            return self.flags.mutable

        @property
        def persistent(self) -> bool:
            return self.flags.persistent

    return [
        Mock(timestamp=851.711638638, flags=Flags(mutable=True, persistent=True),
             name='exec_aux_command', type_id=ValueType.I16, value=[-1]),
        Mock(timestamp=851.714542638, flags=Flags(mutable=True, persistent=True),
             name='exec_aux_command=', type_id=ValueType.I16, value=[-1]),
        Mock(timestamp=851.717591372, flags=Flags(mutable=True, persistent=True),
             name='exec_aux_command<', type_id=ValueType.I16, value=[-1]),
        Mock(timestamp=851.720854227, flags=Flags(mutable=True, persistent=True),
             name='exec_aux_command>', type_id=ValueType.I16, value=[9999]),
        Mock(timestamp=851.723690861, flags=Flags(mutable=True, persistent=True),
             name='vsi.pwm_freq_khz', type_id=ValueType.F32, value=[45.000003814697266]),
        Mock(timestamp=851.726534338, flags=Flags(mutable=True, persistent=True),
             name='vsi.pwm_freq_khz=', type_id=ValueType.F32, value=[0.0]),
        Mock(timestamp=851.72971755, flags=Flags(mutable=True, persistent=True),
             name='vsi.pwm_freq_khz<', type_id=ValueType.F32, value=[0.0]),
        Mock(timestamp=851.732355705, flags=Flags(mutable=True, persistent=True),
             name='vsi.pwm_freq_khz>', type_id=ValueType.F32, value=[50.0]),
        Mock(timestamp=851.73534375, flags=Flags(mutable=True, persistent=True),
             name='ctl.spinup_durat', type_id=ValueType.F32, value=[1.5]),
        Mock(timestamp=851.739275616, flags=Flags(mutable=True, persistent=True),
             name='ctl.spinup_durat=', type_id=ValueType.F32, value=[1.5]),
        Mock(timestamp=851.742441327, flags=Flags(mutable=True, persistent=True),
             name='ctl.spinup_durat<', type_id=ValueType.F32, value=[0.10000000149011612]),
        Mock(timestamp=851.745427505, flags=Flags(mutable=True, persistent=True),
             name='ctl.spinup_durat>', type_id=ValueType.F32, value=[10.0]),
        Mock(timestamp=851.748394294, flags=Flags(mutable=True, persistent=True),
             name='ctl.num_attempts', type_id=ValueType.U32, value=[100]),
        Mock(timestamp=851.751416605, flags=Flags(mutable=True, persistent=True),
             name='ctl.num_attempts=', type_id=ValueType.U32, value=[100]),
        Mock(timestamp=851.754419961, flags=Flags(mutable=True, persistent=True),
             name='ctl.num_attempts<', type_id=ValueType.U32, value=[1]),
        Mock(timestamp=851.757365305, flags=Flags(mutable=True, persistent=True),
             name='ctl.num_attempts>', type_id=ValueType.U32, value=[10000000]),
        Mock(timestamp=851.760408894, flags=Flags(mutable=True, persistent=True),
             name='ctl.vm_cci_comp', type_id=ValueType.BOOLEAN, value=[False]),
        Mock(timestamp=851.763470294, flags=Flags(mutable=True, persistent=True),
             name='ctl.vm_cci_comp=', type_id=ValueType.BOOLEAN, value=[False]),
        Mock(timestamp=851.767278961, flags=Flags(mutable=True, persistent=True),
             name='ctl.vm_cci_comp<', type_id=ValueType.BOOLEAN, value=[False]),
        Mock(timestamp=851.770608261, flags=Flags(mutable=True, persistent=True),
             name='ctl.vm_cci_comp>', type_id=ValueType.BOOLEAN, value=[True]),
        Mock(timestamp=851.773533083, flags=Flags(mutable=True, persistent=True),
             name='ctl.vm_oversatur', type_id=ValueType.BOOLEAN, value=[False]),
        Mock(timestamp=851.776490183, flags=Flags(mutable=True, persistent=True),
             name='ctl.vm_oversatur=', type_id=ValueType.BOOLEAN, value=[False]),
        Mock(timestamp=851.779599183, flags=Flags(mutable=True, persistent=True),
             name='ctl.vm_oversatur<', type_id=ValueType.BOOLEAN, value=[False]),
        Mock(timestamp=851.782599105, flags=Flags(mutable=True, persistent=True),
             name='ctl.vm_oversatur>', type_id=ValueType.BOOLEAN, value=[True]),
        Mock(timestamp=851.785595627, flags=Flags(mutable=True, persistent=True),
             name='ctl.vm_pppwm_thr', type_id=ValueType.F32, value=[0.949999988079071]),
        Mock(timestamp=851.788617383, flags=Flags(mutable=True, persistent=True),
             name='ctl.vm_pppwm_thr=', type_id=ValueType.F32, value=[0.949999988079071]),
        Mock(timestamp=851.791578683, flags=Flags(mutable=True, persistent=True),
             name='ctl.vm_pppwm_thr<', type_id=ValueType.F32, value=[0.0]),
        Mock(timestamp=851.794644627, flags=Flags(mutable=True, persistent=True),
             name='ctl.vm_pppwm_thr>', type_id=ValueType.F32, value=[1.0]),
        Mock(timestamp=851.797268238, flags=Flags(mutable=True, persistent=True),
             name='m.num_poles', type_id=ValueType.U8, value=[14]),
        Mock(timestamp=851.800533261, flags=Flags(mutable=True, persistent=True),
             name='m.num_poles=', type_id=ValueType.U8, value=[0]),
        Mock(timestamp=851.803604894, flags=Flags(mutable=True, persistent=True),
             name='m.num_poles<', type_id=ValueType.U8, value=[0]),
        Mock(timestamp=851.80669495, flags=Flags(mutable=True, persistent=True),
             name='m.num_poles>', type_id=ValueType.U8, value=[200]),
        Mock(timestamp=851.809813161, flags=Flags(mutable=True, persistent=True),
             name='m.max_current', type_id=ValueType.F32, value=[14.0]),
        Mock(timestamp=851.81272075, flags=Flags(mutable=True, persistent=True),
             name='m.max_current=', type_id=ValueType.F32, value=[0.0]),
        Mock(timestamp=851.815664916, flags=Flags(mutable=True, persistent=True),
             name='m.max_current<', type_id=ValueType.F32, value=[0.0]),
        Mock(timestamp=851.818537527, flags=Flags(mutable=True, persistent=True),
             name='m.max_current>', type_id=ValueType.F32, value=[200.0]),
        Mock(timestamp=851.821507683, flags=Flags(mutable=True, persistent=True),
             name='m.min_current', type_id=ValueType.F32, value=[0.3499999940395355]),
        Mock(timestamp=851.824600905, flags=Flags(mutable=True, persistent=True),
             name='m.min_current=', type_id=ValueType.F32, value=[0.0]),
        Mock(timestamp=851.827497794, flags=Flags(mutable=True, persistent=True),
             name='m.min_current<', type_id=ValueType.F32, value=[0.0]),
        Mock(timestamp=851.830515894, flags=Flags(mutable=True, persistent=True),
             name='m.min_current>', type_id=ValueType.F32, value=[50.0]),
        Mock(timestamp=851.833599394, flags=Flags(mutable=True, persistent=True),
             name='m.spup_current_l', type_id=ValueType.F32, value=[0.699999988079071]),
        Mock(timestamp=851.83661225, flags=Flags(mutable=True, persistent=True),
             name='m.spup_current_l=', type_id=ValueType.F32, value=[0.0]),
        Mock(timestamp=851.839510416, flags=Flags(mutable=True, persistent=True),
             name='m.spup_current_l<', type_id=ValueType.F32, value=[0.0]),
        Mock(timestamp=851.842568494, flags=Flags(mutable=True, persistent=True),
             name='m.spup_current_l>', type_id=ValueType.F32, value=[50.0]),
        Mock(timestamp=851.845634983, flags=Flags(mutable=True, persistent=True),
             name='m.spup_current_h', type_id=ValueType.F32, value=[7.0]),
        Mock(timestamp=851.848518116, flags=Flags(mutable=True, persistent=True),
             name='m.spup_current_h=', type_id=ValueType.F32, value=[0.0]),
        Mock(timestamp=851.851583505, flags=Flags(mutable=True, persistent=True),
             name='m.spup_current_h<', type_id=ValueType.F32, value=[0.0]),
        Mock(timestamp=851.854634516, flags=Flags(mutable=True, persistent=True),
             name='m.spup_current_h>', type_id=ValueType.F32, value=[50.0]),
        Mock(timestamp=851.857606561, flags=Flags(mutable=True, persistent=True),
             name='m.phi_milliweber', type_id=ValueType.F32, value=[0.9692422747612]),
        Mock(timestamp=851.860655961, flags=Flags(mutable=True, persistent=True),
             name='m.phi_milliweber=', type_id=ValueType.F32, value=[0.0]),
        Mock(timestamp=851.863669938, flags=Flags(mutable=True, persistent=True),
             name='m.phi_milliweber<', type_id=ValueType.F32, value=[0.0]),
        Mock(timestamp=851.866608294, flags=Flags(mutable=True, persistent=True),
             name='m.phi_milliweber>', type_id=ValueType.F32, value=[500.0]),
        Mock(timestamp=851.86960055, flags=Flags(mutable=True, persistent=True),
             name='m.rs_ohm', type_id=ValueType.F32, value=[0.09571981430053711]),
        Mock(timestamp=851.87262915, flags=Flags(mutable=True, persistent=True),
             name='m.rs_ohm=', type_id=ValueType.F32, value=[0.0]),
        Mock(timestamp=851.875559972, flags=Flags(mutable=True, persistent=True),
             name='m.rs_ohm<', type_id=ValueType.F32, value=[0.0]),
        Mock(timestamp=851.87858975, flags=Flags(mutable=True, persistent=True),
             name='m.rs_ohm>', type_id=ValueType.F32, value=[10.0]),
        Mock(timestamp=851.881658305, flags=Flags(mutable=True, persistent=True),
             name='m.ld_microhenry', type_id=ValueType.F32, value=[12.47910213470459]),
        Mock(timestamp=851.88456425, flags=Flags(mutable=True, persistent=True),
             name='m.ld_microhenry=', type_id=ValueType.F32, value=[0.0]),
        Mock(timestamp=851.887616761, flags=Flags(mutable=True, persistent=True),
             name='m.ld_microhenry<', type_id=ValueType.F32, value=[0.0]),
        Mock(timestamp=851.890684594, flags=Flags(mutable=True, persistent=True),
             name='m.ld_microhenry>', type_id=ValueType.F32, value=[500000.0]),
        Mock(timestamp=851.893629927, flags=Flags(mutable=True, persistent=True),
             name='m.lq_microhenry', type_id=ValueType.F32, value=[12.47910213470459]),
        Mock(timestamp=851.896611383, flags=Flags(mutable=True, persistent=True),
             name='m.lq_microhenry=', type_id=ValueType.F32, value=[0.0]),
        Mock(timestamp=851.899549916, flags=Flags(mutable=True, persistent=True),
             name='m.lq_microhenry<', type_id=ValueType.F32, value=[0.0]),
        Mock(timestamp=851.902652272, flags=Flags(mutable=True, persistent=True),
             name='m.lq_microhenry>', type_id=ValueType.F32, value=[500000.0]),
        Mock(timestamp=851.905621716, flags=Flags(mutable=True, persistent=True),
             name='m.min_eangvel', type_id=ValueType.F32, value=[400.0]),
        Mock(timestamp=851.908651061, flags=Flags(mutable=True, persistent=True),
             name='m.min_eangvel=', type_id=ValueType.F32, value=[400.0]),
        Mock(timestamp=851.911596016, flags=Flags(mutable=True, persistent=True),
             name='m.min_eangvel<', type_id=ValueType.F32, value=[10.0]),
        Mock(timestamp=851.914579505, flags=Flags(mutable=True, persistent=True),
             name='m.min_eangvel>', type_id=ValueType.F32, value=[1000.0]),
        Mock(timestamp=851.91766875, flags=Flags(mutable=True, persistent=True),
             name='m.max_eangvel', type_id=ValueType.F32, value=[5000.0]),
        Mock(timestamp=851.920623572, flags=Flags(mutable=True, persistent=True),
             name='m.max_eangvel=', type_id=ValueType.F32, value=[10000.0]),
        Mock(timestamp=851.923579561, flags=Flags(mutable=True, persistent=True),
             name='m.max_eangvel<', type_id=ValueType.F32, value=[10.0]),
        Mock(timestamp=851.926661261, flags=Flags(mutable=True, persistent=True),
             name='m.max_eangvel>', type_id=ValueType.F32, value=[20000.0]),
        Mock(timestamp=851.929657983, flags=Flags(mutable=True, persistent=True),
             name='m.current_ramp', type_id=ValueType.F32, value=[100.0]),
        Mock(timestamp=851.93259355, flags=Flags(mutable=True, persistent=True),
             name='m.current_ramp=', type_id=ValueType.F32, value=[100.0]),
        Mock(timestamp=851.935596727, flags=Flags(mutable=True, persistent=True),
             name='m.current_ramp<', type_id=ValueType.F32, value=[0.10000000149011612]),
        Mock(timestamp=851.938597094, flags=Flags(mutable=True, persistent=True),
             name='m.current_ramp>', type_id=ValueType.F32, value=[10000.0]),
        Mock(timestamp=851.941626283, flags=Flags(mutable=True, persistent=True),
             name='m.voltage_ramp', type_id=ValueType.F32, value=[20.0]),
        Mock(timestamp=851.944615372, flags=Flags(mutable=True, persistent=True),
             name='m.voltage_ramp=', type_id=ValueType.F32, value=[20.0]),
        Mock(timestamp=851.947590216, flags=Flags(mutable=True, persistent=True),
             name='m.voltage_ramp<', type_id=ValueType.F32, value=[0.009999999776482582]),
        Mock(timestamp=851.95056275, flags=Flags(mutable=True, persistent=True),
             name='m.voltage_ramp>', type_id=ValueType.F32, value=[1000.0]),
        Mock(timestamp=851.953582194, flags=Flags(mutable=True, persistent=True),
             name='m.eangvel_rampup', type_id=ValueType.F32, value=[2000.0]),
        Mock(timestamp=851.956661205, flags=Flags(mutable=True, persistent=True),
             name='m.eangvel_rampup=', type_id=ValueType.F32, value=[2000.0]),
        Mock(timestamp=851.959587061, flags=Flags(mutable=True, persistent=True),
             name='m.eangvel_rampup<', type_id=ValueType.F32, value=[0.009999999776482582]),
        Mock(timestamp=851.962571427, flags=Flags(mutable=True, persistent=True),
             name='m.eangvel_rampup>', type_id=ValueType.F32, value=[1000000.0]),
        Mock(timestamp=851.965648327, flags=Flags(mutable=True, persistent=True),
             name='m.eangvel_rampdn', type_id=ValueType.F32, value=[2000.0]),
        Mock(timestamp=851.968548205, flags=Flags(mutable=True, persistent=True),
             name='m.eangvel_rampdn=', type_id=ValueType.F32, value=[0.0]),
        Mock(timestamp=851.971596716, flags=Flags(mutable=True, persistent=True),
             name='m.eangvel_rampdn<', type_id=ValueType.F32, value=[0.0]),
        Mock(timestamp=851.974608372, flags=Flags(mutable=True, persistent=True),
             name='m.eangvel_rampdn>', type_id=ValueType.F32, value=[1000000.0]),
        Mock(timestamp=851.977630983, flags=Flags(mutable=True, persistent=True),
             name='m.eangvel_ctl_kp', type_id=ValueType.F32, value=[0.003000000026077032]),
        Mock(timestamp=851.980666116, flags=Flags(mutable=True, persistent=True),
             name='m.eangvel_ctl_kp=', type_id=ValueType.F32, value=[0.003000000026077032]),
        Mock(timestamp=851.983632327, flags=Flags(mutable=True, persistent=True),
             name='m.eangvel_ctl_kp<', type_id=ValueType.F32, value=[0.0]),
        Mock(timestamp=851.98660195, flags=Flags(mutable=True, persistent=True),
             name='m.eangvel_ctl_kp>', type_id=ValueType.F32, value=[100.0]),
        Mock(timestamp=851.989630872, flags=Flags(mutable=True, persistent=True),
             name='m.eangvel_ctl_ki', type_id=ValueType.F32, value=[0.0010000000474974513]),
        Mock(timestamp=851.992615427, flags=Flags(mutable=True, persistent=True),
             name='m.eangvel_ctl_ki=', type_id=ValueType.F32, value=[0.0010000000474974513]),
        Mock(timestamp=851.995606583, flags=Flags(mutable=True, persistent=True),
             name='m.eangvel_ctl_ki<', type_id=ValueType.F32, value=[0.0]),
        Mock(timestamp=851.998557827, flags=Flags(mutable=True, persistent=True),
             name='m.eangvel_ctl_ki>', type_id=ValueType.F32, value=[100.0]),
        Mock(timestamp=852.001608716, flags=Flags(mutable=True, persistent=True),
             name='m.current_ctl_bw', type_id=ValueType.F32, value=[0.019999999552965164]),
        Mock(timestamp=852.004650305, flags=Flags(mutable=True, persistent=True),
             name='m.current_ctl_bw=', type_id=ValueType.F32, value=[0.019999999552965164]),
        Mock(timestamp=852.00761535, flags=Flags(mutable=True, persistent=True),
             name='m.current_ctl_bw<', type_id=ValueType.F32, value=[9.999999747378752e-06]),
        Mock(timestamp=852.01065045, flags=Flags(mutable=True, persistent=True),
             name='m.current_ctl_bw>', type_id=ValueType.F32, value=[0.5]),
        Mock(timestamp=852.013645761, flags=Flags(mutable=True, persistent=True),
             name='mid.phi.curr_mul', type_id=ValueType.F32, value=[0.30000001192092896]),
        Mock(timestamp=852.016572127, flags=Flags(mutable=True, persistent=True),
             name='mid.phi.curr_mul=', type_id=ValueType.F32, value=[0.30000001192092896]),
        Mock(timestamp=852.019585494, flags=Flags(mutable=True, persistent=True),
             name='mid.phi.curr_mul<', type_id=ValueType.F32, value=[0.10000000149011612]),
        Mock(timestamp=852.022633127, flags=Flags(mutable=True, persistent=True),
             name='mid.phi.curr_mul>', type_id=ValueType.F32, value=[1.0]),
        Mock(timestamp=852.025551105, flags=Flags(mutable=True, persistent=True),
             name='mid.phi.eangvel', type_id=ValueType.F32, value=[300.0]),
        Mock(timestamp=852.028652661, flags=Flags(mutable=True, persistent=True),
             name='mid.phi.eangvel=', type_id=ValueType.F32, value=[300.0]),
        Mock(timestamp=852.031581883, flags=Flags(mutable=True, persistent=True),
             name='mid.phi.eangvel<', type_id=ValueType.F32, value=[50.0]),
        Mock(timestamp=852.03466055, flags=Flags(mutable=True, persistent=True),
             name='mid.phi.eangvel>', type_id=ValueType.F32, value=[2000.0]),
        Mock(timestamp=852.037673794, flags=Flags(mutable=True, persistent=True),
             name='mid.phi.stall_th', type_id=ValueType.F32, value=[5.0]),
        Mock(timestamp=852.040562805, flags=Flags(mutable=True, persistent=True),
             name='mid.phi.stall_th=', type_id=ValueType.F32, value=[5.0]),
        Mock(timestamp=852.043585727, flags=Flags(mutable=True, persistent=True),
             name='mid.phi.stall_th<', type_id=ValueType.F32, value=[2.0]),
        Mock(timestamp=852.046686272, flags=Flags(mutable=True, persistent=True),
             name='mid.phi.stall_th>', type_id=ValueType.F32, value=[20.0]),
        Mock(timestamp=852.049624483, flags=Flags(mutable=True, persistent=True),
             name='mid.l.curr_mul', type_id=ValueType.F32, value=[0.05999999865889549]),
        Mock(timestamp=852.052551016, flags=Flags(mutable=True, persistent=True),
             name='mid.l.curr_mul=', type_id=ValueType.F32, value=[0.05999999865889549]),
        Mock(timestamp=852.055549516, flags=Flags(mutable=True, persistent=True),
             name='mid.l.curr_mul<', type_id=ValueType.F32, value=[0.009999999776482582]),
        Mock(timestamp=852.058625238, flags=Flags(mutable=True, persistent=True),
             name='mid.l.curr_mul>', type_id=ValueType.F32, value=[0.5]),
        Mock(timestamp=852.061569305, flags=Flags(mutable=True, persistent=True),
             name='mid.l.curr_freq', type_id=ValueType.F32, value=[900.0]),
        Mock(timestamp=852.064565905, flags=Flags(mutable=True, persistent=True),
             name='mid.l.curr_freq=', type_id=ValueType.F32, value=[900.0]),
        Mock(timestamp=852.06762895, flags=Flags(mutable=True, persistent=True),
             name='mid.l.curr_freq<', type_id=ValueType.F32, value=[50.0]),
        Mock(timestamp=852.07051995, flags=Flags(mutable=True, persistent=True),
             name='mid.l.curr_freq>', type_id=ValueType.F32, value=[1500.0]),
        Mock(timestamp=852.073595427, flags=Flags(mutable=True, persistent=True),
             name='mid.r.curr_mul', type_id=ValueType.F32, value=[0.30000001192092896]),
        Mock(timestamp=852.076631116, flags=Flags(mutable=True, persistent=True),
             name='mid.r.curr_mul=', type_id=ValueType.F32, value=[0.30000001192092896]),
        Mock(timestamp=852.079579283, flags=Flags(mutable=True, persistent=True),
             name='mid.r.curr_mul<', type_id=ValueType.F32, value=[0.05000000074505806]),
        Mock(timestamp=852.082565038, flags=Flags(mutable=True, persistent=True),
             name='mid.r.curr_mul>', type_id=ValueType.F32, value=[1.0]),
        Mock(timestamp=852.085517905, flags=Flags(mutable=True, persistent=True),
             name='o.type', type_id=ValueType.BOOLEAN, value=[False]),
        Mock(timestamp=852.08849975, flags=Flags(mutable=True, persistent=True),
             name='o.type=', type_id=ValueType.BOOLEAN, value=[False]),
        Mock(timestamp=852.091474205, flags=Flags(mutable=True, persistent=True),
             name='o.type<', type_id=ValueType.BOOLEAN, value=[False]),
        Mock(timestamp=852.094534116, flags=Flags(mutable=True, persistent=True),
             name='o.type>', type_id=ValueType.BOOLEAN, value=[True]),
        Mock(timestamp=852.097530905, flags=Flags(mutable=True, persistent=True),
             name='o.ekf.q_id', type_id=ValueType.F32, value=[1000000.0]),
        Mock(timestamp=852.10047915, flags=Flags(mutable=True, persistent=True),
             name='o.ekf.q_id=', type_id=ValueType.F32, value=[30000.0]),
        Mock(timestamp=852.103522772, flags=Flags(mutable=True, persistent=True),
             name='o.ekf.q_id<', type_id=ValueType.F32, value=[0.10000000149011612]),
        Mock(timestamp=852.106569983, flags=Flags(mutable=True, persistent=True),
             name='o.ekf.q_id>', type_id=ValueType.F32, value=[1000000000.0]),
        Mock(timestamp=852.109532105, flags=Flags(mutable=True, persistent=True),
             name='o.ekf.q_iq', type_id=ValueType.F32, value=[100000000.0]),
        Mock(timestamp=852.112636472, flags=Flags(mutable=True, persistent=True),
             name='o.ekf.q_iq=', type_id=ValueType.F32, value=[300000.0]),
        Mock(timestamp=852.115450561, flags=Flags(mutable=True, persistent=True),
             name='o.ekf.q_iq<', type_id=ValueType.F32, value=[0.10000000149011612]),
        Mock(timestamp=852.118478527, flags=Flags(mutable=True, persistent=True),
             name='o.ekf.q_iq>', type_id=ValueType.F32, value=[1000000000.0]),
        Mock(timestamp=852.121586083, flags=Flags(mutable=True, persistent=True),
             name='o.ekf.q_eangvel', type_id=ValueType.F32, value=[1000000000.0]),
        Mock(timestamp=852.12463575, flags=Flags(mutable=True, persistent=True),
             name='o.ekf.q_eangvel=', type_id=ValueType.F32, value=[300000000.0]),
        Mock(timestamp=852.127653661, flags=Flags(mutable=True, persistent=True),
             name='o.ekf.q_eangvel<', type_id=ValueType.F32, value=[0.10000000149011612]),
        Mock(timestamp=852.130633205, flags=Flags(mutable=True, persistent=True),
             name='o.ekf.q_eangvel>', type_id=ValueType.F32, value=[1000000000.0]),
        Mock(timestamp=852.133494372, flags=Flags(mutable=True, persistent=True),
             name='o.ekf.p0_idq', type_id=ValueType.F32, value=[0.0010000000474974513]),
        Mock(timestamp=852.136584883, flags=Flags(mutable=True, persistent=True),
             name='o.ekf.p0_idq=', type_id=ValueType.F32, value=[0.0010000000474974513]),
        Mock(timestamp=852.139487694, flags=Flags(mutable=True, persistent=True),
             name='o.ekf.p0_idq<', type_id=ValueType.F32, value=[0.0]),
        Mock(timestamp=852.142414038, flags=Flags(mutable=True, persistent=True),
             name='o.ekf.p0_idq>', type_id=ValueType.F32, value=[1000000.0]),
        Mock(timestamp=852.14567015, flags=Flags(mutable=True, persistent=True),
             name='o.ekf.p0_eangvel', type_id=ValueType.F32, value=[0.0010000000474974513]),
        Mock(timestamp=852.148625538, flags=Flags(mutable=True, persistent=True),
             name='o.ekf.p0_eangvel=', type_id=ValueType.F32, value=[0.0010000000474974513]),
        Mock(timestamp=852.151599605, flags=Flags(mutable=True, persistent=True),
             name='o.ekf.p0_eangvel<', type_id=ValueType.F32, value=[0.0]),
        Mock(timestamp=852.154476616, flags=Flags(mutable=True, persistent=True),
             name='o.ekf.p0_eangvel>', type_id=ValueType.F32, value=[1000000.0]),
        Mock(timestamp=852.157432894, flags=Flags(mutable=True, persistent=True),
             name='o.ekf.cc_comp', type_id=ValueType.F32, value=[0.0]),
        Mock(timestamp=852.160473883, flags=Flags(mutable=True, persistent=True),
             name='o.ekf.cc_comp=', type_id=ValueType.F32, value=[0.0]),
        Mock(timestamp=852.163610861, flags=Flags(mutable=True, persistent=True),
             name='o.ekf.cc_comp<', type_id=ValueType.F32, value=[0.0]),
        Mock(timestamp=852.166614194, flags=Flags(mutable=True, persistent=True),
             name='o.ekf.cc_comp>', type_id=ValueType.F32, value=[10.0]),
        Mock(timestamp=852.169647316, flags=Flags(mutable=True, persistent=True),
             name='o.mras.gain', type_id=ValueType.F32, value=[150000.0]),
        Mock(timestamp=852.172673916, flags=Flags(mutable=True, persistent=True),
             name='o.mras.gain=', type_id=ValueType.F32, value=[150000.0]),
        Mock(timestamp=852.175408527, flags=Flags(mutable=True, persistent=True),
             name='o.mras.gain<', type_id=ValueType.F32, value=[0.0010000000474974513]),
        Mock(timestamp=852.178540427, flags=Flags(mutable=True, persistent=True),
             name='o.mras.gain>', type_id=ValueType.F32, value=[1000000.0]),
        Mock(timestamp=852.181572583, flags=Flags(mutable=True, persistent=True),
             name='bec.can_pwr_on', type_id=ValueType.BOOLEAN, value=[False]),
        Mock(timestamp=852.184489972, flags=Flags(mutable=True, persistent=True),
             name='bec.can_pwr_on=', type_id=ValueType.BOOLEAN, value=[False]),
        Mock(timestamp=852.187463516, flags=Flags(mutable=True, persistent=True),
             name='bec.can_pwr_on<', type_id=ValueType.BOOLEAN, value=[False]),
        Mock(timestamp=852.190533638, flags=Flags(mutable=True, persistent=True),
             name='bec.can_pwr_on>', type_id=ValueType.BOOLEAN, value=[True]),
        Mock(timestamp=852.193576638, flags=Flags(mutable=True, persistent=True),
             name='uavcan.esc_index', type_id=ValueType.U8, value=[0]),
        Mock(timestamp=852.196430438, flags=Flags(mutable=True, persistent=True),
             name='uavcan.esc_index=', type_id=ValueType.U8, value=[0]),
        Mock(timestamp=852.199422027, flags=Flags(mutable=True, persistent=True),
             name='uavcan.esc_index<', type_id=ValueType.U8, value=[0]),
        Mock(timestamp=852.202474072, flags=Flags(mutable=True, persistent=True),
             name='uavcan.esc_index>', type_id=ValueType.U8, value=[15]),
        Mock(timestamp=852.205692016, flags=Flags(mutable=True, persistent=True),
             name='uavcan.esc_ttl', type_id=ValueType.F32, value=[0.30000001192092896]),
        Mock(timestamp=852.208637972, flags=Flags(mutable=True, persistent=True),
             name='uavcan.esc_ttl=', type_id=ValueType.F32, value=[0.30000001192092896]),
        Mock(timestamp=852.211634405, flags=Flags(mutable=True, persistent=True),
             name='uavcan.esc_ttl<', type_id=ValueType.F32, value=[0.10000000149011612]),
        Mock(timestamp=852.214656805, flags=Flags(mutable=True, persistent=True),
             name='uavcan.esc_ttl>', type_id=ValueType.F32, value=[10.0]),
        Mock(timestamp=852.217600527, flags=Flags(mutable=True, persistent=True),
             name='uavcan.esc_sint', type_id=ValueType.F32, value=[0.05000000074505806]),
        Mock(timestamp=852.220531361, flags=Flags(mutable=True, persistent=True),
             name='uavcan.esc_sint=', type_id=ValueType.F32, value=[0.05000000074505806]),
        Mock(timestamp=852.223468127, flags=Flags(mutable=True, persistent=True),
             name='uavcan.esc_sint<', type_id=ValueType.F32, value=[0.009999999776482582]),
        Mock(timestamp=852.226420716, flags=Flags(mutable=True, persistent=True),
             name='uavcan.esc_sint>', type_id=ValueType.F32, value=[1.0]),
        Mock(timestamp=852.229546883, flags=Flags(mutable=True, persistent=True),
             name='uavcan.esc_sintp', type_id=ValueType.F32, value=[0.5]),
        Mock(timestamp=852.232701794, flags=Flags(mutable=True, persistent=True),
             name='uavcan.esc_sintp=', type_id=ValueType.F32, value=[0.5]),
        Mock(timestamp=852.235410816, flags=Flags(mutable=True, persistent=True),
             name='uavcan.esc_sintp<', type_id=ValueType.F32, value=[0.009999999776482582]),
        Mock(timestamp=852.238505527, flags=Flags(mutable=True, persistent=True),
             name='uavcan.esc_sintp>', type_id=ValueType.F32, value=[10.0]),
        Mock(timestamp=852.241439894, flags=Flags(mutable=True, persistent=True),
             name='uavcan.esc_rcm', type_id=ValueType.U8, value=[1]),
        Mock(timestamp=852.244376294, flags=Flags(mutable=True, persistent=True),
             name='uavcan.esc_rcm=', type_id=ValueType.U8, value=[1]),
        Mock(timestamp=852.247386527, flags=Flags(mutable=True, persistent=True),
             name='uavcan.esc_rcm<', type_id=ValueType.U8, value=[0]),
        Mock(timestamp=852.250587783, flags=Flags(mutable=True, persistent=True),
             name='uavcan.esc_rcm>', type_id=ValueType.U8, value=[2]),
        Mock(timestamp=852.253549694, flags=Flags(mutable=True, persistent=True),
             name='uavcan.node_id', type_id=ValueType.U8, value=[0]),
        Mock(timestamp=852.256521694, flags=Flags(mutable=True, persistent=True),
             name='uavcan.node_id=', type_id=ValueType.U8, value=[0]),
        Mock(timestamp=852.259555961, flags=Flags(mutable=True, persistent=True),
             name='uavcan.node_id<', type_id=ValueType.U8, value=[0]),
        Mock(timestamp=852.262513094, flags=Flags(mutable=True, persistent=True),
             name='uavcan.node_id>', type_id=ValueType.U8, value=[125]),
        Mock(timestamp=852.26554435, flags=Flags(mutable=False, persistent=False),
             name='uavcan.transfer_cnt.error', type_id=ValueType.U64, value=[0]),
        Mock(timestamp=852.268587272, flags=Flags(mutable=False, persistent=False),
             name='uavcan.transfer_cnt.rx', type_id=ValueType.U64, value=[0]),
        Mock(timestamp=852.271563561, flags=Flags(mutable=False, persistent=False),
             name='uavcan.transfer_cnt.tx', type_id=ValueType.U64, value=[0]),
        Mock(timestamp=852.274584272, flags=Flags(mutable=False, persistent=False),
             name='ctrl.task_switch_count', type_id=ValueType.U32, value=[0]),
        Mock(timestamp=852.27753835, flags=Flags(mutable=False, persistent=False),
             name='vsi.motor_temp', type_id=ValueType.F32, value=[0.0]),
        Mock(timestamp=852.280559061, flags=Flags(mutable=False, persistent=False),
             name='vsi.cpu_temp', type_id=ValueType.F32, value=[0.0]),
        Mock(timestamp=852.283468716, flags=Flags(mutable=False, persistent=False),
             name='vsi.vsi_temp', type_id=ValueType.F32, value=[0.0]),
        Mock(timestamp=852.286600483, flags=Flags(mutable=False, persistent=False),
             name='vsi.pwm_irq_duration', type_id=ValueType.F32, value=[0.0]),
        Mock(timestamp=852.289598983, flags=Flags(mutable=False, persistent=False),
             name='vsi.phase_voltage_error', type_id=ValueType.F32, value=[0.0, 0.0, 0.0]),
        Mock(timestamp=852.292641905, flags=Flags(mutable=False, persistent=False),
             name='vsi.hw_flag_cnt.fault', type_id=ValueType.U32, value=[0]),
        Mock(timestamp=852.295573772, flags=Flags(mutable=False, persistent=False),
             name='vsi.hw_flag_cnt.overload', type_id=ValueType.U32, value=[0]),
        Mock(timestamp=852.298661116, flags=Flags(mutable=False, persistent=False),
             name='vsi.hw_flag_cnt.lvps_malfunction', type_id=ValueType.U32, value=[0]),
        Mock(timestamp=852.30152635, flags=Flags(mutable=False, persistent=False),
             name='vsi.phase_voltage', type_id=ValueType.F32, value=[0.0, 0.0, 0.0]),
        Mock(timestamp=852.304547061, flags=Flags(mutable=False, persistent=False),
             name='vsi.phase_current', type_id=ValueType.F32, value=[0.0, 0.0]),
        Mock(timestamp=852.307656616, flags=Flags(mutable=False, persistent=False),
             name='vsi.dc_current_lpf', type_id=ValueType.F32, value=[0.0]),
        Mock(timestamp=852.31052185, flags=Flags(mutable=False, persistent=False),
             name='vsi.dc_current', type_id=ValueType.F32, value=[0.0]),
        Mock(timestamp=852.313675827, flags=Flags(mutable=False, persistent=False),
             name='vsi.dc_voltage_lpf', type_id=ValueType.F32, value=[0.0]),
        Mock(timestamp=852.316652116, flags=Flags(mutable=False, persistent=False),
             name='vsi.dc_voltage', type_id=ValueType.F32, value=[0.0]),
        Mock(timestamp=852.319583983, flags=Flags(mutable=False, persistent=False),
             name='vsi.current_gain_level', type_id=ValueType.BOOLEAN, value=[True]),
        Mock(timestamp=852.322582483, flags=Flags(mutable=False, persistent=False),
             name='motor.pwm_setpoint', type_id=ValueType.F32, value=[0.0, 0.0, 0.0]),
        Mock(timestamp=852.325603194, flags=Flags(mutable=False, persistent=False),
             name='motor.electrical_angle', type_id=ValueType.F32, value=[0.0]),
        Mock(timestamp=852.328734961, flags=Flags(mutable=False, persistent=False),
             name='motor.scalar.frequency', type_id=ValueType.F32, value=[0.0]),
        Mock(timestamp=852.331666827, flags=Flags(mutable=False, persistent=False),
             name='motor.id.phi_noise_threshold', type_id=ValueType.F32, value=[0.0]),
        Mock(timestamp=852.334665327, flags=Flags(mutable=False, persistent=False),
             name='motor.id.phi_noise_sample', type_id=ValueType.F32, value=[0.0]),
        Mock(timestamp=852.337574983, flags=Flags(mutable=False, persistent=False),
             name='motor.id.phi', type_id=ValueType.F32, value=[0.0]),
        Mock(timestamp=852.340595694, flags=Flags(mutable=False, persistent=False),
             name='motor.id.raw_phi', type_id=ValueType.F32, value=[0.0]),
        Mock(timestamp=852.343638616, flags=Flags(mutable=False, persistent=False),
             name='motor.setpoint_q', type_id=ValueType.F32, value=[0.0]),
        Mock(timestamp=852.346659327, flags=Flags(mutable=False, persistent=False),
             name='motor.electrical_angular_velocity', type_id=ValueType.F32, value=[0.0]),
        Mock(timestamp=852.349591194, flags=Flags(mutable=False, persistent=False),
             name='motor.u_dq', type_id=ValueType.F32, value=[0.0, 0.0]),
        Mock(timestamp=852.352611905, flags=Flags(mutable=False, persistent=False),
             name='motor.i_dq', type_id=ValueType.F32, value=[0.0, 0.0]),
        Mock(timestamp=852.355677038, flags=Flags(mutable=False, persistent=False),
             name='observer.variance.electrical_angle', type_id=ValueType.F32, value=[0.0]),
        Mock(timestamp=852.358675538, flags=Flags(mutable=False, persistent=False),
             name='observer.variance.electrical_ang_vel', type_id=ValueType.F32, value=[0.0]),
        Mock(timestamp=852.361740672, flags=Flags(mutable=False, persistent=False),
             name='observer.variance.i_q', type_id=ValueType.F32, value=[0.0]),
        Mock(timestamp=852.36469475, flags=Flags(mutable=False, persistent=False),
             name='observer.variance.i_d', type_id=ValueType.F32, value=[0.0]),
        Mock(timestamp=852.367582194, flags=Flags(mutable=False, persistent=False),
             name='observer.x', type_id=ValueType.F32, value=[0.0, 0.0, 0.0, 0.0]),
        Mock(timestamp=852.370780594, flags=Flags(mutable=False, persistent=False),
             name='setpoint.elect_ang_vel_ctrl.integral', type_id=ValueType.F32, value=[0.0]),
        Mock(timestamp=852.373734672, flags=Flags(mutable=False, persistent=False),
             name='setpoint.electrical_angular_velocity', type_id=ValueType.F32, value=[0.0]),
        Mock(timestamp=852.376622116, flags=Flags(mutable=False, persistent=False),
             name='motor.i_q_pid.error_integral', type_id=ValueType.F32, value=[0.0]),
        Mock(timestamp=852.379709461, flags=Flags(mutable=False, persistent=False),
             name='motor.i_d_pid.error_integral', type_id=ValueType.F32, value=[0.0]),
        Mock(timestamp=852.38268575, flags=Flags(mutable=False, persistent=False),
             name='motor.passive_phase_modulation_on', type_id=ValueType.BOOLEAN, value=[False]),
        Mock(timestamp=852.385662038, flags=Flags(mutable=False, persistent=False),
             name='motor.phase_voltage_setpoint', type_id=ValueType.F32, value=[0.0, 0.0, 0.0]),
        Mock(timestamp=852.389326872, flags=Flags(mutable=False, persistent=False),
             name='motor.u_dq_setpoint', type_id=ValueType.F32, value=[0.0, 0.0]),
    ]

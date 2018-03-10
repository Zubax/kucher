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
from PyQt5.QtGui import QPalette
from view.utils import gui_test, get_monospace_font
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
        'DTS',              # Update timestamp, device time; show age on hover (tooltip)?
        'Full name',
    ]

    class _ColumnIndices(enum.IntEnum):
        NAME             = 0
        TYPE             = 1
        VALUE            = 2
        DEFAULT          = 3
        MIN              = 4
        MAX              = 5
        DEVICE_TIMESTAMP = 6
        FULL_NAME        = 7

    def __init__(self,
                 parent: QWidget,
                 registers: typing.Iterable[Register]):
        super(Model, self).__init__(parent)

        self._regular_font = get_monospace_font()
        self._underlined_font = get_monospace_font()
        self._underlined_font.setUnderline(True)

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
                return self._display_value(node.value.cached_value, node.value.type_id)

            if column == column_indices.DEFAULT:
                return self._display_value(node.value.default_value, node.value.type_id)

            if column == column_indices.MIN:
                return self._display_value(node.value.min_value, node.value.type_id)

            if column == column_indices.MAX:
                return self._display_value(node.value.max_value, node.value.type_id)

            if column == column_indices.DEVICE_TIMESTAMP:
                return str(datetime.timedelta(seconds=float(node.value.update_timestamp_device_time)))

            if column == column_indices.FULL_NAME:
                return node.value.name

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

        return QVariant()

    def setData(self, index: QModelIndex, value, role=None) -> bool:
        return False        # TODO: Editable fields

    def flags(self, index: QModelIndex) -> int:
        node = self._unwrap(index)
        out = Qt.ItemIsEnabled
        if node and node.value:
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

    @staticmethod
    def _display_value(value, type_id: Register.ValueType) -> str:
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
    from PyQt5.QtWidgets import QApplication, QMainWindow, QTreeView, QHeaderView

    app = QApplication([])
    win = QMainWindow()

    tw = QTreeView(win)
    tw.setStyleSheet('''
    QTreeView::item { padding: 0 5px; }
    ''')

    header: QHeaderView = tw.header()
    header.setSectionResizeMode(QHeaderView.ResizeToContents)
    header.setStretchLastSection(False)     # Horizontal scroll bar doesn't work if this is enabled

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
    from popcop.standard.register import Flags, ValueType

    # noinspection PyShadowingBuiltins
    def mock(cached, default, min, max, mutable, persistent, ts_device, ts_mono, **kwargs):
        flags = Flags()
        flags.mutable = mutable
        flags.persistent = persistent

        def set_get_callback(value):
            raise NotImplementedError('Mock objects do not model the device')

        return Register(value=cached,
                        default_value=default,
                        min_value=min,
                        max_value=max,
                        flags=flags,
                        update_timestamp_device_time=ts_device,
                        update_timestamp_monotonic=ts_mono,
                        set_get_callback=set_get_callback,
                        **kwargs)
    return [
        mock(name='exec_aux_command', type_id=ValueType.I16, cached=[-1], default=[-1], min=[-1], max=[9999],
             mutable=True, persistent=True, ts_device=167.120176761, ts_mono=11474.095037309),
        mock(name='vsi.pwm_freq_khz', type_id=ValueType.F32, cached=[45.000003814697266], default=[0.0], min=[0.0],
             max=[50.0], mutable=True, persistent=True, ts_device=167.150843761, ts_mono=11474.095083372),
        mock(name='ctl.spinup_durat', type_id=ValueType.F32, cached=[1.5], default=[1.5], min=[0.10000000149011612],
             max=[10.0], mutable=True, persistent=True, ts_device=167.189638527, ts_mono=11474.095108553),
        mock(name='ctl.num_attempts', type_id=ValueType.U32, cached=[100], default=[100], min=[1], max=[10000000],
             mutable=True, persistent=True, ts_device=167.22092805, ts_mono=11474.095134015),
        mock(name='ctl.vm_cci_comp', type_id=ValueType.BOOLEAN, cached=[False], default=[False], min=[False],
             max=[True], mutable=True, persistent=True, ts_device=167.252589227, ts_mono=11474.095157437),
        mock(name='ctl.vm_oversatur', type_id=ValueType.BOOLEAN, cached=[False], default=[False], min=[False],
             max=[True], mutable=True, persistent=True, ts_device=167.283183261, ts_mono=11474.09518067),
        mock(name='ctl.vm_pppwm_thr', type_id=ValueType.F32, cached=[0.949999988079071], default=[0.949999988079071],
             min=[0.0], max=[1.0], mutable=True, persistent=True, ts_device=167.313057172, ts_mono=11474.095203923),
        mock(name='m.num_poles', type_id=ValueType.U8, cached=[14], default=[0], min=[0], max=[200], mutable=True,
             persistent=True, ts_device=167.343252161, ts_mono=11474.095226993),
        mock(name='m.max_current', type_id=ValueType.F32, cached=[14.0], default=[0.0], min=[0.0], max=[200.0],
             mutable=True, persistent=True, ts_device=167.369294972, ts_mono=11474.095250044),
        mock(name='m.min_current', type_id=ValueType.F32, cached=[0.3499999940395355], default=[0.0], min=[0.0],
             max=[50.0], mutable=True, persistent=True, ts_device=167.398127294, ts_mono=11474.095273253),
        mock(name='m.spup_current_l', type_id=ValueType.F32, cached=[0.699999988079071], default=[0.0], min=[0.0],
             max=[50.0], mutable=True, persistent=True, ts_device=167.427121272, ts_mono=11474.095296358),
        mock(name='m.spup_current_h', type_id=ValueType.F32, cached=[7.0], default=[0.0], min=[0.0], max=[50.0],
             mutable=True, persistent=True, ts_device=167.457667294, ts_mono=11474.095321345),
        mock(name='m.phi_milliweber', type_id=ValueType.F32, cached=[0.9692422747612], default=[0.0], min=[0.0],
             max=[500.0], mutable=True, persistent=True, ts_device=167.487963305, ts_mono=11474.095344579),
        mock(name='m.rs_ohm', type_id=ValueType.F32, cached=[0.09571981430053711], default=[0.0], min=[0.0], max=[10.0],
             mutable=True, persistent=True, ts_device=167.517682005, ts_mono=11474.095367282),
        mock(name='m.ld_microhenry', type_id=ValueType.F32, cached=[12.47910213470459], default=[0.0], min=[0.0],
             max=[500000.0], mutable=True, persistent=True, ts_device=167.54309675, ts_mono=11474.095390037),
        mock(name='m.lq_microhenry', type_id=ValueType.F32, cached=[12.47910213470459], default=[0.0], min=[0.0],
             max=[500000.0], mutable=True, persistent=True, ts_device=167.573339927, ts_mono=11474.09541249),
        mock(name='m.min_eangvel', type_id=ValueType.F32, cached=[400.0], default=[400.0], min=[10.0], max=[1000.0],
             mutable=True, persistent=True, ts_device=167.602944972, ts_mono=11474.095435058),
        mock(name='m.max_eangvel', type_id=ValueType.F32, cached=[5000.0], default=[10000.0], min=[10.0], max=[20000.0],
             mutable=True, persistent=True, ts_device=167.631806272, ts_mono=11474.095458084),
        mock(name='m.current_ramp', type_id=ValueType.F32, cached=[100.0], default=[100.0], min=[0.10000000149011612],
             max=[10000.0], mutable=True, persistent=True, ts_device=167.660413072, ts_mono=11474.095481023),
        mock(name='m.voltage_ramp', type_id=ValueType.F32, cached=[20.0], default=[20.0], min=[0.009999999776482582],
             max=[1000.0], mutable=True, persistent=True, ts_device=167.689644772, ts_mono=11474.095556567),
        mock(name='m.eangvel_rampup', type_id=ValueType.F32, cached=[2000.0], default=[2000.0],
             min=[0.009999999776482582], max=[1000000.0], mutable=True, persistent=True, ts_device=167.719028994,
             ts_mono=11474.095586866),
        mock(name='m.eangvel_rampdn', type_id=ValueType.F32, cached=[2000.0], default=[0.0], min=[0.0], max=[1000000.0],
             mutable=True, persistent=True, ts_device=167.749470094, ts_mono=11474.095610592),
        mock(name='m.eangvel_ctl_kp', type_id=ValueType.F32, cached=[0.003000000026077032],
             default=[0.003000000026077032], min=[0.0], max=[100.0], mutable=True, persistent=True,
             ts_device=167.77973525, ts_mono=11474.095634679),
        mock(name='m.eangvel_ctl_ki', type_id=ValueType.F32, cached=[0.0010000000474974513],
             default=[0.0010000000474974513], min=[0.0], max=[100.0], mutable=True, persistent=True,
             ts_device=167.809852683, ts_mono=11474.09565974),
        mock(name='m.current_ctl_bw', type_id=ValueType.F32, cached=[0.019999999552965164],
             default=[0.019999999552965164], min=[9.999999747378752e-06], max=[0.5], mutable=True, persistent=True,
             ts_device=167.840277894, ts_mono=11474.095685348),
        mock(name='mid.phi.curr_mul', type_id=ValueType.F32, cached=[0.30000001192092896],
             default=[0.30000001192092896], min=[0.10000000149011612], max=[1.0], mutable=True, persistent=True,
             ts_device=167.870644161, ts_mono=11474.095708942),
        mock(name='mid.phi.eangvel', type_id=ValueType.F32, cached=[300.0], default=[300.0], min=[50.0], max=[2000.0],
             mutable=True, persistent=True, ts_device=167.900911227, ts_mono=11474.095732269),
        mock(name='mid.phi.stall_th', type_id=ValueType.F32, cached=[5.0], default=[5.0], min=[2.0], max=[20.0],
             mutable=True, persistent=True, ts_device=167.93105435, ts_mono=11474.095755858),
        mock(name='mid.l.curr_mul', type_id=ValueType.F32, cached=[0.05999999865889549], default=[0.05999999865889549],
             min=[0.009999999776482582], max=[0.5], mutable=True, persistent=True, ts_device=167.961478361,
             ts_mono=11474.095782118),
        mock(name='mid.l.curr_freq', type_id=ValueType.F32, cached=[900.0], default=[900.0], min=[50.0], max=[1500.0],
             mutable=True, persistent=True, ts_device=167.99063795, ts_mono=11474.095807649),
        mock(name='mid.r.curr_mul', type_id=ValueType.F32, cached=[0.30000001192092896], default=[0.30000001192092896],
             min=[0.05000000074505806], max=[1.0], mutable=True, persistent=True, ts_device=168.02053605,
             ts_mono=11474.095831341),
        mock(name='o.type', type_id=ValueType.BOOLEAN, cached=[False], default=[False], min=[False], max=[True],
             mutable=True, persistent=True, ts_device=168.048972783, ts_mono=11474.095858845),
        mock(name='o.ekf.q_id', type_id=ValueType.F32, cached=[1000000.0], default=[30000.0], min=[0.10000000149011612],
             max=[1000000000.0], mutable=True, persistent=True, ts_device=168.07176205, ts_mono=11474.095884825),
        mock(name='o.ekf.q_iq', type_id=ValueType.F32, cached=[100000000.0], default=[300000.0],
             min=[0.10000000149011612], max=[1000000000.0], mutable=True, persistent=True, ts_device=168.098169505,
             ts_mono=11474.095908585),
        mock(name='o.ekf.q_eangvel', type_id=ValueType.F32, cached=[1000000000.0], default=[300000000.0],
             min=[0.10000000149011612], max=[1000000000.0], mutable=True, persistent=True, ts_device=168.124119783,
             ts_mono=11474.095935612),
        mock(name='o.ekf.p0_idq', type_id=ValueType.F32, cached=[0.0010000000474974513],
             default=[0.0010000000474974513], min=[0.0], max=[1000000.0], mutable=True, persistent=True,
             ts_device=168.152991494, ts_mono=11474.095976266),
        mock(name='o.ekf.p0_eangvel', type_id=ValueType.F32, cached=[0.0010000000474974513],
             default=[0.0010000000474974513], min=[0.0], max=[1000000.0], mutable=True, persistent=True,
             ts_device=168.180930294, ts_mono=11474.096031996),
        mock(name='o.ekf.cc_comp', type_id=ValueType.F32, cached=[0.0], default=[0.0], min=[0.0], max=[10.0],
             mutable=True, persistent=True, ts_device=168.211163661, ts_mono=11474.096078469),
        mock(name='o.mras.gain', type_id=ValueType.F32, cached=[150000.0], default=[150000.0],
             min=[0.0010000000474974513], max=[1000000.0], mutable=True, persistent=True, ts_device=168.23962725,
             ts_mono=11474.096112982),
        mock(name='bec.can_pwr_on', type_id=ValueType.BOOLEAN, cached=[False], default=[False], min=[False], max=[True],
             mutable=True, persistent=True, ts_device=168.266927538, ts_mono=11474.096137455),
        mock(name='uavcan.esc_index', type_id=ValueType.U8, cached=[0], default=[0], min=[0], max=[15], mutable=True,
             persistent=True, ts_device=168.295695294, ts_mono=11474.0961611),
        mock(name='uavcan.esc_ttl', type_id=ValueType.F32, cached=[0.30000001192092896], default=[0.30000001192092896],
             min=[0.10000000149011612], max=[10.0], mutable=True, persistent=True, ts_device=168.325321394,
             ts_mono=11474.096187528),
        mock(name='uavcan.esc_sint', type_id=ValueType.F32, cached=[0.05000000074505806], default=[0.05000000074505806],
             min=[0.009999999776482582], max=[1.0], mutable=True, persistent=True, ts_device=168.354900616,
             ts_mono=11474.096214092),
        mock(name='uavcan.esc_sintp', type_id=ValueType.F32, cached=[0.5], default=[0.5], min=[0.009999999776482582],
             max=[10.0], mutable=True, persistent=True, ts_device=168.384844983, ts_mono=11474.096241364),
        mock(name='uavcan.esc_rcm', type_id=ValueType.U8, cached=[1], default=[1], min=[0], max=[2], mutable=True,
             persistent=True, ts_device=168.415360083, ts_mono=11474.096265363),
        mock(name='uavcan.node_id', type_id=ValueType.U8, cached=[0], default=[0], min=[0], max=[125], mutable=True,
             persistent=True, ts_device=168.443844627, ts_mono=11474.096288244),
        mock(name='uavcan.transfer_cnt.error', type_id=ValueType.U64, cached=[0], default=None, min=None, max=None,
             mutable=False, persistent=False, ts_device=168.473500294, ts_mono=11474.09631309),
        mock(name='uavcan.transfer_cnt.rx', type_id=ValueType.U64, cached=[0], default=None, min=None, max=None,
             mutable=False, persistent=False, ts_device=168.482784538, ts_mono=11474.096334935),
        mock(name='uavcan.transfer_cnt.tx', type_id=ValueType.U64, cached=[0], default=None, min=None, max=None,
             mutable=False, persistent=False, ts_device=168.491846672, ts_mono=11474.09635874),
        mock(name='ctrl.task_switch_count', type_id=ValueType.U32, cached=[0], default=None, min=None, max=None,
             mutable=False, persistent=False, ts_device=168.500842172, ts_mono=11474.096381102),
        mock(name='vsi.motor_temp', type_id=ValueType.F32, cached=[0.0], default=None, min=None, max=None,
             mutable=False, persistent=False, ts_device=168.508704905, ts_mono=11474.096429273),
        mock(name='vsi.cpu_temp', type_id=ValueType.F32, cached=[0.0], default=None, min=None, max=None, mutable=False,
             persistent=False, ts_device=168.515967938, ts_mono=11474.096475768),
        mock(name='vsi.vsi_temp', type_id=ValueType.F32, cached=[0.0], default=None, min=None, max=None, mutable=False,
             persistent=False, ts_device=168.522875594, ts_mono=11474.096519214),
        mock(name='vsi.pwm_irq_duration', type_id=ValueType.F32, cached=[0.0], default=None, min=None, max=None,
             mutable=False, persistent=False, ts_device=168.530338527, ts_mono=11474.09654562),
        mock(name='vsi.phase_voltage_error', type_id=ValueType.F32, cached=[0.0, 0.0, 0.0], default=None, min=None,
             max=None, mutable=False, persistent=False, ts_device=168.53857885, ts_mono=11474.09657154),
        mock(name='vsi.hw_flag_cnt.fault', type_id=ValueType.U32, cached=[0], default=None, min=None, max=None,
             mutable=False, persistent=False, ts_device=168.547752038, ts_mono=11474.096593609),
        mock(name='vsi.hw_flag_cnt.overload', type_id=ValueType.U32, cached=[0], default=None, min=None, max=None,
             mutable=False, persistent=False, ts_device=168.556525427, ts_mono=11474.096651339),
        mock(name='vsi.hw_flag_cnt.lvps_malfunction', type_id=ValueType.U32, cached=[0], default=None, min=None,
             max=None, mutable=False, persistent=False, ts_device=168.566342738, ts_mono=11474.096678888),
        mock(name='vsi.phase_voltage', type_id=ValueType.F32, cached=[0.0, 0.0, 0.0], default=None, min=None, max=None,
             mutable=False, persistent=False, ts_device=168.575515927, ts_mono=11474.09671855),
        mock(name='vsi.phase_current', type_id=ValueType.F32, cached=[0.0, 0.0], default=None, min=None, max=None,
             mutable=False, persistent=False, ts_device=168.583911727, ts_mono=11474.096745765),
        mock(name='vsi.dc_current_lpf', type_id=ValueType.F32, cached=[0.0], default=None, min=None, max=None,
             mutable=False, persistent=False, ts_device=168.59195215, ts_mono=11474.096768286),
        mock(name='vsi.dc_current', type_id=ValueType.F32, cached=[0.0], default=None, min=None, max=None,
             mutable=False, persistent=False, ts_device=168.599614983, ts_mono=11474.096790113),
        mock(name='vsi.dc_voltage_lpf', type_id=ValueType.F32, cached=[0.0], default=None, min=None, max=None,
             mutable=False, persistent=False, ts_device=168.607077916, ts_mono=11474.096811819),
        mock(name='vsi.dc_voltage', type_id=ValueType.F32, cached=[0.0], default=None, min=None, max=None,
             mutable=False, persistent=False, ts_device=168.614829594, ts_mono=11474.096833574),
        mock(name='vsi.current_gain_level', type_id=ValueType.BOOLEAN, cached=[True], default=None, min=None, max=None,
             mutable=False, persistent=False, ts_device=168.622847805, ts_mono=11474.096857869),
        mock(name='motor.pwm_setpoint', type_id=ValueType.F32, cached=[0.0, 0.0, 0.0], default=None, min=None, max=None,
             mutable=False, persistent=False, ts_device=168.630754961, ts_mono=11474.09688225),
        mock(name='motor.electrical_angle', type_id=ValueType.F32, cached=[0.0], default=None, min=None, max=None,
             mutable=False, persistent=False, ts_device=168.639839305, ts_mono=11474.09690772),
        mock(name='motor.scalar.frequency', type_id=ValueType.F32, cached=[0.0], default=None, min=None, max=None,
             mutable=False, persistent=False, ts_device=168.648634905, ts_mono=11474.0969341),
        mock(name='motor.id.phi_noise_threshold', type_id=ValueType.F32, cached=[0.0], default=None, min=None, max=None,
             mutable=False, persistent=False, ts_device=168.657585983, ts_mono=11474.096956255),
        mock(name='motor.id.phi_noise_sample', type_id=ValueType.F32, cached=[0.0], default=None, min=None, max=None,
             mutable=False, persistent=False, ts_device=168.666981283, ts_mono=11474.096980231),
        mock(name='motor.id.phi', type_id=ValueType.F32, cached=[0.0], default=None, min=None, max=None, mutable=False,
             persistent=False, ts_device=168.674888438, ts_mono=11474.09700427),
        mock(name='motor.id.raw_phi', type_id=ValueType.F32, cached=[0.0], default=None, min=None, max=None,
             mutable=False, persistent=False, ts_device=168.682195894, ts_mono=11474.097026366),
        mock(name='motor.setpoint_q', type_id=ValueType.F32, cached=[0.0], default=None, min=None, max=None,
             mutable=False, persistent=False, ts_device=168.690036416, ts_mono=11474.0970501),
        mock(name='motor.electrical_angular_velocity', type_id=ValueType.F32, cached=[0.0], default=None, min=None,
             max=None, mutable=False, persistent=False, ts_device=168.699209605, ts_mono=11474.097072857),
        mock(name='motor.u_dq', type_id=ValueType.F32, cached=[0.0, 0.0], default=None, min=None, max=None,
             mutable=False, persistent=False, ts_device=168.707583194, ts_mono=11474.097096338),
        mock(name='motor.i_dq', type_id=ValueType.F32, cached=[0.0, 0.0], default=None, min=None, max=None,
             mutable=False, persistent=False, ts_device=168.714402005, ts_mono=11474.097118982),
        mock(name='observer.variance.electrical_angle', type_id=ValueType.F32, cached=[0.0], default=None, min=None,
             max=None, mutable=False, persistent=False, ts_device=168.723330872, ts_mono=11474.097144446),
        mock(name='observer.variance.electrical_ang_vel', type_id=ValueType.F32, cached=[0.0], default=None, min=None,
             max=None, mutable=False, persistent=False, ts_device=168.734192105, ts_mono=11474.097168879),
        mock(name='observer.variance.i_q', type_id=ValueType.F32, cached=[0.0], default=None, min=None, max=None,
             mutable=False, persistent=False, ts_device=168.743765094, ts_mono=11474.097190949),
        mock(name='observer.variance.i_d', type_id=ValueType.F32, cached=[0.0], default=None, min=None, max=None,
             mutable=False, persistent=False, ts_device=168.752205316, ts_mono=11474.097212606),
        mock(name='observer.x', type_id=ValueType.F32, cached=[0.0, 0.0, 0.0, 0.0], default=None, min=None, max=None,
             mutable=False, persistent=False, ts_device=168.768175105, ts_mono=11474.097234168),
        mock(name='setpoint.elect_ang_vel_ctrl.integral', type_id=ValueType.F32, cached=[0.0], default=None, min=None,
             max=None, mutable=False, persistent=False, ts_device=168.777970205, ts_mono=11474.097256111),
        mock(name='setpoint.electrical_angular_velocity', type_id=ValueType.F32, cached=[0.0], default=None, min=None,
             max=None, mutable=False, persistent=False, ts_device=168.789075761, ts_mono=11474.097282835),
        mock(name='motor.i_q_pid.error_integral', type_id=ValueType.F32, cached=[0.0], default=None, min=None, max=None,
             mutable=False, persistent=False, ts_device=168.799670461, ts_mono=11474.097305723),
        mock(name='motor.i_d_pid.error_integral', type_id=ValueType.F32, cached=[0.0], default=None, min=None, max=None,
             mutable=False, persistent=False, ts_device=168.809398927, ts_mono=11474.097327512),
        mock(name='motor.passive_phase_modulation_on', type_id=ValueType.BOOLEAN, cached=[False], default=None,
             min=None, max=None, mutable=False, persistent=False, ts_device=168.819704883, ts_mono=11474.097349266),
        mock(name='motor.phase_voltage_setpoint', type_id=ValueType.F32, cached=[0.0, 0.0, 0.0], default=None, min=None,
             max=None, mutable=False, persistent=False, ts_device=168.829588827, ts_mono=11474.097374602),
        mock(name='motor.u_dq_setpoint', type_id=ValueType.F32, cached=[0.0, 0.0], default=None, min=None, max=None,
             mutable=False, persistent=False, ts_device=168.839961416, ts_mono=11474.097399175),
    ]

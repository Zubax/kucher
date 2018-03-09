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

import typing
import datetime
import dataclasses
from collections import defaultdict
from logging import getLogger
from PyQt5.QtWidgets import QWidget
from PyQt5.QtCore import Qt, QAbstractItemModel, QModelIndex, QVariant
from view.device_model_representation import Register


_logger = getLogger(__name__)


_NAME_SEGMENT_SEPARATOR = '.'


# noinspection PyMethodOverriding
class Model(QAbstractItemModel):
    def __init__(self,
                 parent: QWidget,
                 registers: typing.Iterable[Register]):
        super(Model, self).__init__(parent)

        self._registers: typing.Dict[str, Register] = {r.name.lower(): r for r in registers}
        self._tree = _plant_tree(registers)

    def index(self, row: int, column: int, parent: QModelIndex = None) -> QModelIndex:
        pass

    def parent(self, index: QModelIndex) -> QModelIndex:
        pass

    def rowCount(self, parent: QModelIndex = None) -> int:
        pass

    def columnCount(self, parent: QModelIndex = None) -> int:
        pass

    def flags(self, index: QModelIndex) -> int:
        pass

    def data(self, index: QModelIndex, role=None) -> QVariant:
        pass

    def setData(self, index: QModelIndex, value, role=None):
        pass

    def hasChildren(self, parent: QModelIndex = None) -> bool:
        pass

    def headerData(self, section: int, orientation: int, role=None) -> QVariant:
        pass


@dataclasses.dataclass
class _Node:
    """
    An element of a register tree.
    Each element may have at most one value and an arbitrary number of children.
    Each child node is referred to by the name of its segment.
    """
    children: typing.DefaultDict[str, '_Node'] = dataclasses.field(default_factory=lambda: defaultdict(_Node))
    value:    Register = None

    def __getitem__(self, item: str) -> '_Node':
        return self.children[item]


def _plant_tree(registers: typing.Iterable[Register]) -> _Node:
    """
    Transforms a flat list of registers into an hierarchical tree.
    """
    root = _Node()
    for reg in registers:
        ref = root
        for segment in reg.name.split(_NAME_SEGMENT_SEPARATOR):
            ref = ref[segment]

        assert ref.value is None
        ref.value = reg

    return root


def _unittest_register_tree():
    @dataclasses.dataclass
    class Mock:
        name: str

    registers = list(map(Mock, [
        'exec_aux_command',
        'vsi.pwm_freq_khz',
        'ctl.spinup_durat',
        'ctl.num_attempts',
        'ctl.vm_cci_comp',
        'ctl.vm_oversatur',
        'ctl.vm_pppwm_thr',
        'm.num_poles',
        'm.max_current',
        'm.min_current',
        'm.spup_current_l',
        'm.spup_current_h',
        'm.phi_milliweber',
        'm.rs_ohm',
        'm.ld_microhenry',
        'm.lq_microhenry',
        'm.min_eangvel',
        'm.max_eangvel',
        'm.current_ramp',
        'm.voltage_ramp',
        'm.eangvel_rampup',
        'm.eangvel_rampdn',
        'm.eangvel_ctl_kp',
        'm.eangvel_ctl_ki',
        'm.current_ctl_bw',
        'mid.phi.curr_mul',
        'mid.phi.eangvel',
        'mid.phi.stall_th',
        'mid.l.curr_mul',
        'mid.l.curr_freq',
        'mid.r.curr_mul',
        'o.type',
        'o.ekf.q_id',
        'o.ekf.q_iq',
        'o.ekf.q_eangvel',
        'o.ekf.p0_idq',
        'o.ekf.p0_eangvel',
        'o.ekf.cc_comp',
        'o.mras.gain',
        'bec.can_pwr_on',
        'uavcan.esc_index',
        'uavcan.esc_ttl',
        'uavcan.esc_sint',
        'uavcan.esc_sintp',
        'uavcan.esc_rcm',
        'uavcan.node_id',
        'uavcan.transfer_cnt.error',
        'uavcan.transfer_cnt.rx',
        'uavcan.transfer_cnt.tx',
        'ctrl.task_switch_count',
        'vsi.motor_temp',
        'vsi.cpu_temp',
        'vsi.vsi_temp',
        'vsi.pwm_irq_duration',
        'vsi.phase_voltage_error',
        'vsi.hw_flag_cnt.fault',
        'vsi.hw_flag_cnt.overload',
        'vsi.hw_flag_cnt.lvps_malfunction',
        'vsi.phase_voltage',
        'vsi.phase_current',
        'vsi.dc_current_lpf',
        'vsi.dc_current',
        'vsi.dc_voltage_lpf',
        'vsi.dc_voltage',
        'vsi.current_gain_level',
        'motor.pwm_setpoint',
        'motor.electrical_angle',
        'motor.scalar.frequency',
        'motor.id.phi_noise_threshold',
        'motor.id.phi_noise_sample',
        'motor.id.phi',
        'motor.id.raw_phi',
        'motor.setpoint_q',
        'motor.electrical_angular_velocity',
        'motor.u_dq',
        'motor.i_dq',
        'observer.variance.electrical_angle',
        'observer.variance.electrical_ang_vel',
        'observer.variance.i_q',
        'observer.variance.i_d',
        'observer.x',
        'setpoint.elect_ang_vel_ctrl.integral',
        'setpoint.electrical_angular_velocity',
        'motor.i_q_pid.error_integral',
        'motor.i_d_pid.error_integral',
        'motor.passive_phase_modulation_on',
        'motor.phase_voltage_setpoint',
        'motor.u_dq_setpoint',
    ]))

    def print_tree(node: _Node, indent=0):
        for segment, ch in node.children.items():
            print((' ' * indent * 4 + segment).ljust(40), ch.value.name if ch.value else '')
            print_tree(ch, indent + 1)

    # noinspection PyTypeChecker
    tree = _plant_tree(registers)
    print('Register tree view:')
    print_tree(tree)

    assert tree['uavcan']['transfer_cnt']['tx'].value.name == 'uavcan.transfer_cnt.tx'

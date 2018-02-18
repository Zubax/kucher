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

import math
import typing
from dataclasses import dataclass
from logging import getLogger
from PyQt5.QtWidgets import QWidget, QCheckBox, QComboBox, QLabel
from view.device_model_representation import Commander, GeneralStatusView, ControlMode, TaskID, TaskSpecificStatusReport
from view.utils import get_icon, lay_out_vertically, lay_out_horizontally
from view.widgets.spinbox_linked_with_slider import SpinboxLinkedWithSlider
from .base import SpecializedControlWidgetBase


_logger = getLogger(__name__)


class RunControlWidget(SpecializedControlWidgetBase):
    # noinspection PyUnresolvedReferences,PyArgumentList
    def __init__(self,
                 parent:    QWidget,
                 commander: Commander):
        from . import STOP_SHORTCUT

        super(RunControlWidget, self).__init__(parent)

        self._commander = commander

        self._last_status: typing.Optional[TaskSpecificStatusReport.Running] = None

        # noinspection PyTypeChecker
        self._named_control_policies: typing.Dict[str, _ControlPolicy] = _make_named_control_policies()

        self._guru_mode_checkbox = QCheckBox('Guru', self)
        self._guru_mode_checkbox.setToolTip("The Guru Mode is dangerous! "
                                            "Use it only if you know what you're doing, and be ready for problems.")
        self._guru_mode_checkbox.setStatusTip(self._guru_mode_checkbox.toolTip())
        self._guru_mode_checkbox.setIcon(get_icon('guru'))
        self._guru_mode_checkbox.toggled.connect(self._on_guru_mode_toggled)

        self._setpoint_control =\
            SpinboxLinkedWithSlider(self,
                                    slider_orientation=SpinboxLinkedWithSlider.SliderOrientation.HORIZONTAL)
        self._setpoint_control.tool_tip = f'To stop the motor, press {STOP_SHORTCUT} or click the Stop button'
        self._setpoint_control.status_tip = self._setpoint_control.tool_tip
        self._setpoint_control.value_change_event.connect(self._on_setpoint_changed)

        self._mode_selector = QComboBox(self)
        self._mode_selector.setEditable(False)
        self._mode_selector.currentIndexChanged.connect(lambda *_: self._on_control_mode_changed())
        for name, cp in self._named_control_policies.items():
            if not cp.only_for_guru:
                self._mode_selector.addItem(get_icon(cp.icon_name), name)

        self._on_control_mode_changed()

        self.setLayout(
            lay_out_vertically(
                lay_out_horizontally(
                    QLabel('Control mode', self),
                    self._mode_selector,
                    (None, 1),
                    QLabel('Setpoint', self),
                    (self._setpoint_control.spinbox, 1),
                    (None, 1),
                    self._guru_mode_checkbox,
                ),
                self._setpoint_control.slider,
                (None, 1)
            )
        )

    def stop(self):
        # Note that we do not invoke stop when switching out, because we don't want to interfere with other tasks
        self._last_status = None
        self.setEnabled(False)
        # Disable first, then reset to zero - this way we won't emit unnecessary zero setpoints when switching out
        self._setpoint_control.value = 0

    def on_general_status_update(self, timestamp: float, s: GeneralStatusView):
        if isinstance(s.task_specific_status_report, TaskSpecificStatusReport.Running):
            self._last_status = s.task_specific_status_report
        else:
            self._last_status = None

        if s.current_task_id in (TaskID.IDLE, TaskID.RUNNING):
            self.setEnabled(True)
        else:
            self.setEnabled(False)
            self._setpoint_control.value = 0

        self._mode_selector.setEnabled((s.current_task_id == TaskID.IDLE) or self._guru_mode_checkbox.isChecked())

        if self.isEnabled() and (abs(self._setpoint_control.value) > 1e-6):
            # We do not emit zero setpoints periodically - that is not necessary because the device will
            # always automatically stop by timeout if setpoints are not refreshed periodically.
            # Also, that would make it impossible to control the device from other interfaces while it is
            # connected to the GUI!
            self._emit_setpoint()

    def _emit_setpoint(self):
        cp = self._get_current_control_policy()
        value = self._setpoint_control.value
        if cp.is_ratiometric:
            value *= 0.01           # Percent scaling

        self._launch_async(self._commander.run(mode=cp.mode, value=value))

    def _on_setpoint_changed(self, _value: float):
        if self.isEnabled():
            self._emit_setpoint()

    def _on_control_mode_changed(self):
        cp = self._get_current_control_policy()
        _logger.info(f'New control mode: {cp}')

        # Determining the initial value from the last received status
        if self._last_status is not None:
            # noinspection PyArgumentList
            initial_value = cp.get_value_from_status(self._last_status)
        else:
            initial_value = 0.0

        _logger.info(f'Initial value of the new control mode: {initial_value} {cp.unit}')

        assert cp.setpoint_range[1] > cp.setpoint_range[0]
        assert cp.setpoint_range[1] >= 0
        assert cp.setpoint_range[0] <= 0

        self._setpoint_control.update_atomically(minimum=cp.setpoint_range[0],
                                                 maximum=cp.setpoint_range[1],
                                                 step=cp.setpoint_step,
                                                 value=initial_value)
        self._setpoint_control.spinbox.setSuffix(f' {cp.unit}')
        self._setpoint_control.slider_visible = cp.is_ratiometric

    def _on_guru_mode_toggled(self, active: bool):
        _logger.warning(f'GURU MODE TOGGLED. New state: {"ACTIVE" if active else "inactive"}')

        if self._get_current_control_policy().only_for_guru:
            self.stop()
            self._mode_selector.setCurrentIndex(0)

        # Eliminating all guru-only modes
        for name, cp in self._named_control_policies.items():
            if cp.only_for_guru:
                for index in range(self._mode_selector.count()):
                    if self._mode_selector.itemText(index).strip() == name:
                        self._mode_selector.removeItem(index)
                        break

        # Adding guru-only items if enabled (always at the end)
        if active:
            for name, cp in self._named_control_policies.items():
                if cp.only_for_guru:
                    self._mode_selector.addItem(get_icon(cp.icon_name), name)

        # Updating the mode selector state - always enabled in guru mode
        self._mode_selector.setEnabled(active)

    def _get_current_control_policy(self) -> '_ControlPolicy':
        return self._named_control_policies[self._mode_selector.currentText().strip()]


@dataclass(frozen=True)
class _ControlPolicy:
    mode:                   ControlMode
    unit:                   str
    setpoint_range:         typing.Tuple[float, float]
    setpoint_step:          float
    icon_name:              str
    is_ratiometric:         bool
    only_for_guru:          bool
    get_value_from_status:  typing.Callable[[TaskSpecificStatusReport.Running], float] = lambda _: 0.0


def _make_named_control_policies():
    percent_range = -100.0, +100.0

    def get_rpm(s: TaskSpecificStatusReport.Running) -> float:
        return _angular_velocity_to_rpm(s.mechanical_angular_velocity)

    def get_i_q(s: TaskSpecificStatusReport.Running) -> float:
        return s.i_dq[1]

    def get_u_q(s: TaskSpecificStatusReport.Running) -> float:
        return s.u_dq[1]

    return {
        'Ratiometric angular velocity': _ControlPolicy(mode=ControlMode.RATIOMETRIC_ANGULAR_VELOCITY,
                                                       unit='%rad/s',
                                                       setpoint_range=percent_range,
                                                       setpoint_step=0.1,
                                                       icon_name='rotation-percent',
                                                       is_ratiometric=True,
                                                       only_for_guru=False),

        'Mechanical RPM':               _ControlPolicy(mode=ControlMode.MECHANICAL_RPM,
                                                       unit='RPM',
                                                       setpoint_range=(-999999, +999999),  # 1e6 takes too much space
                                                       setpoint_step=10.0,
                                                       icon_name='rotation',
                                                       is_ratiometric=False,
                                                       only_for_guru=False,
                                                       get_value_from_status=get_rpm),

        'Ratiometric current':          _ControlPolicy(mode=ControlMode.RATIOMETRIC_CURRENT,
                                                       unit='%A',
                                                       setpoint_range=percent_range,
                                                       setpoint_step=0.1,
                                                       icon_name='muscle-percent',
                                                       is_ratiometric=True,
                                                       only_for_guru=False),

        'Current':                      _ControlPolicy(mode=ControlMode.CURRENT,
                                                       unit='A',
                                                       setpoint_range=(-1e3, +1e3),
                                                       setpoint_step=0.1,
                                                       icon_name='muscle',
                                                       is_ratiometric=False,
                                                       only_for_guru=False,
                                                       get_value_from_status=get_i_q),

        'Ratiometric voltage':          _ControlPolicy(mode=ControlMode.RATIOMETRIC_VOLTAGE,
                                                       unit='%V',
                                                       setpoint_range=percent_range,
                                                       setpoint_step=0.1,
                                                       icon_name='voltage-percent',
                                                       is_ratiometric=True,
                                                       only_for_guru=True),

        'Voltage':                      _ControlPolicy(mode=ControlMode.VOLTAGE,
                                                       unit='V',
                                                       setpoint_range=(-1e3, +1e3),
                                                       setpoint_step=0.1,
                                                       icon_name='voltage',
                                                       is_ratiometric=False,
                                                       only_for_guru=True,
                                                       get_value_from_status=get_u_q),
    }


def _angular_velocity_to_rpm(radian_per_sec: float) -> float:
    return radian_per_sec * (60.0 / (math.pi * 2.0))

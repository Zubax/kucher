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
from contextlib import contextmanager
from logging import getLogger
from PyQt5.QtWidgets import QWidget, QCheckBox, QComboBox, QSlider, QDoubleSpinBox, QLabel
from PyQt5.QtCore import Qt
from view.device_model_representation import Commander, GeneralStatusView, ControlMode, TaskID, TaskSpecificStatusReport
from view.utils import get_icon, lay_out_vertically, lay_out_horizontally
from .base import SpecializedControlWidgetBase


_SLIDER_HALF_RANGE = 1000
_HUNDRED_PERCENT = 100


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

        self._spinbox = QDoubleSpinBox(self)
        self._spinbox.setToolTip(f'To stop the motor, press {STOP_SHORTCUT} or click the Stop button')
        self._spinbox.setStatusTip(self._spinbox.toolTip())

        self._slider = QSlider(Qt.Horizontal, self)
        self._slider.setRange(-_SLIDER_HALF_RANGE,
                              +_SLIDER_HALF_RANGE)
        self._slider.setTickInterval(_SLIDER_HALF_RANGE)
        self._slider.setTickPosition(QSlider.TicksBothSides)

        # Linking the spin box and the slider. We unlink them every time either of them is changed in order
        # to synchronize the values, and then we immediately link them back again; see _unlinker() for more info.
        self._spinbox.valueChanged[float].connect(self._on_spinbox_changed)
        self._slider.valueChanged.connect(self._on_slider_moved)

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
                    (self._spinbox, 1),
                    (None, 1),
                    self._guru_mode_checkbox,
                ),
                self._slider,
                (None, 1)
            )
        )

    def start(self):
        self._last_status = None
        self.setEnabled(True)

    def stop(self):
        self._last_status = None
        self._spinbox.setValue(0.0)
        self._launch_async(self._commander.stop())      # Super paranoia

    def on_general_status_update(self, timestamp: float, s: GeneralStatusView):
        if isinstance(s.task_specific_status_report, TaskSpecificStatusReport.Running):
            self._last_status = s.task_specific_status_report
        else:
            self._last_status = None

        if s.current_task_id in (TaskID.IDLE, TaskID.RUNNING):
            self.setEnabled(True)
        else:
            self.setEnabled(False)

        self._mode_selector.setEnabled((s.current_task_id == TaskID.IDLE) or self._guru_mode_checkbox.isChecked())

        if abs(self._spinbox.value()) > 1e-6:
            # We do not emit zero setpoints periodically - that is not necessary because the device will
            # always automatically stop by timeout if setpoints are not refreshed periodically.
            self._emit_setpoint()

    def _emit_setpoint(self):
        cp = self._get_current_control_policy()
        value = self._spinbox.value()
        if cp.is_ratiometric:
            value *= 0.01           # Percent scaling

        self._launch_async(self._commander.run(mode=cp.mode, value=value))

    def _on_spinbox_changed(self, value: float):
        # For consistency, we always try to maintain the slider at the same value as the spinbox.
        with self._unlinker():
            self._slider.setValue((value / _HUNDRED_PERCENT) * _SLIDER_HALF_RANGE)

        self._emit_setpoint()

    def _on_slider_moved(self, new_value: int):
        with self._unlinker():
            self._spinbox.setValue(new_value * _HUNDRED_PERCENT / _SLIDER_HALF_RANGE)

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

        # Updating the spinbox ranges and the initial value
        # WARNING!
        # The on-changed signal MUST be disconnected, otherwise we may end up emitting erroneous setpoints
        # while the values are being updated. Another problem with the signals is that they go through the slider,
        # if it is enabled, which breaks the value configured in the spin box. This is how it's happening (I had
        # to look into the Qt's sources in order to find this out):
        #       setRange() updates the limits. If the currently set value is outside of the limits, it is updated.
        #       Assuming that the old value doesn't fit the new limits, setRange() invokes setValue(), which, in turn,
        #       invokes the on-change event handler in this class. The on-change event handler then moves the slider,
        #       in order to keep it in sync with the value. If the value exceeds the range of the slider, the slider
        #       will silently clip it, and then set the clipped value back to the spinbox from its event handler.
        #       A catastrophe! We lost the proper value and ended up with a clipped one. This is how it happens, if
        #       we were to print() out the relevant values from handlers:
        #           CONFIGURING RANGE AND VALUE...
        #           SPINBOX CHANGED TO 678.52           <-- this is the correct value
        #           SLIDER MOVED TO 100%                <-- doesn't fit into the slider's range, so it gets clipped
        #           SPINBOX CHANGED TO 100.0            <-- the clipped value fed back (and sent to the device!)
        #           RANGE AND VALUE CONFIGURED
        # So we disconnect the signal before changing stuff, and then connect the signal back.
        assert cp.setpoint_range[1] > cp.setpoint_range[0]
        assert cp.setpoint_range[1] >= 0
        assert cp.setpoint_range[0] <= 0

        with self._unlinker():
            self._spinbox.setRange(*cp.setpoint_range)
            self._spinbox.setSingleStep(cp.setpoint_step)
            self._spinbox.setSuffix(f' {cp.unit}')

        # The spinbox has been configured, now we can apply the new value and it will be propagated to the slider
        self._spinbox.setValue(initial_value)

        # The slider is visible only for ratiometric modes.
        # We do not update its value explicitly here, it will be updated via the callback.
        self._slider.setVisible(cp.is_ratiometric)

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

    # noinspection PyUnresolvedReferences
    @contextmanager
    def _unlinker(self):
        self._slider.valueChanged.disconnect(self._on_slider_moved)
        self._spinbox.valueChanged[float].disconnect(self._on_spinbox_changed)
        yield
        self._slider.valueChanged.connect(self._on_slider_moved)
        self._spinbox.valueChanged[float].connect(self._on_spinbox_changed)


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

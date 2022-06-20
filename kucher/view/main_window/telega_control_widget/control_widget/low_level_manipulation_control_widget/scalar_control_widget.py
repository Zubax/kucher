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

from contextlib import contextmanager
from logging import getLogger
from PyQt5.QtWidgets import QWidget

from kucher.model.device_model import (
    Commander,
    LowLevelManipulationMode,
    GeneralStatusView,
    TaskID,
)
from kucher.view.utils import lay_out_horizontally, make_button
from kucher.view.widgets.spinbox_linked_with_slider import SpinboxLinkedWithSlider

from .base import LowLevelManipulationControlSubWidgetBase


_SEND_BUTTON_STYLESHEET_WHEN_ACTIVATED = (
    "QPushButton { background-color: #ff0; color: #330; font-weight: 600; }"
)


_logger = getLogger(__name__)


class Widget(LowLevelManipulationControlSubWidgetBase):
    # noinspection PyUnresolvedReferences
    def __init__(self, parent: QWidget, commander: Commander):
        super(Widget, self).__init__(parent)

        self._commander = commander
        self._event_suppression_depth = 0

        self._send_button = make_button(
            self,
            text="Execute",
            icon_name="send-up",
            tool_tip="Sends the command to the device; also, while this button is checked (pressed), "
            "commands will be sent automatically every time the controls are changed by the user.",
            checkable=True,
            checked=False,
            on_clicked=self._on_send_button_changed,
        )

        self._volt_per_hertz_control = SpinboxLinkedWithSlider(
            self,
            minimum=0.001,
            maximum=1.0,
            step=0.001,
            slider_orientation=SpinboxLinkedWithSlider.SliderOrientation.HORIZONTAL,
        )
        self._volt_per_hertz_control.spinbox_suffix = " V/Hz"
        self._volt_per_hertz_control.num_decimals = 3
        self._volt_per_hertz_control.tool_tip = "Amplitude, volt per hertz"
        self._volt_per_hertz_control.status_tip = self._volt_per_hertz_control.tool_tip
        self._volt_per_hertz_control.slider_visible = False

        self._target_frequency_control = SpinboxLinkedWithSlider(
            self,
            minimum=-9999.0,
            maximum=9999.0,
            step=10.0,
            slider_orientation=SpinboxLinkedWithSlider.SliderOrientation.HORIZONTAL,
        )
        self._target_frequency_control.spinbox_suffix = " Hz"
        self._target_frequency_control.tool_tip = "Target frequency, hertz"
        self._target_frequency_control.status_tip = (
            self._target_frequency_control.tool_tip
        )

        self._frequency_gradient_control = SpinboxLinkedWithSlider(
            self,
            minimum=0.0,
            maximum=999.0,
            step=1.0,
            slider_orientation=SpinboxLinkedWithSlider.SliderOrientation.HORIZONTAL,
        )
        self._frequency_gradient_control.spinbox_suffix = " Hz/s"
        self._frequency_gradient_control.tool_tip = (
            "Frequency gradient, hertz per second"
        )
        self._frequency_gradient_control.status_tip = (
            self._frequency_gradient_control.tool_tip
        )
        self._frequency_gradient_control.slider_visible = False

        # Initial values
        self._volt_per_hertz_control.value = 0.01
        self._target_frequency_control.value = 0.0
        self._frequency_gradient_control.value = 20.0

        # Having configured the values, connecting the events
        self._volt_per_hertz_control.value_change_event.connect(
            self._on_any_control_changed
        )
        self._target_frequency_control.value_change_event.connect(
            self._on_any_control_changed
        )
        self._frequency_gradient_control.value_change_event.connect(
            self._on_any_control_changed
        )

        self.setLayout(
            lay_out_horizontally(
                self._volt_per_hertz_control.spinbox,
                self._frequency_gradient_control.spinbox,
                self._target_frequency_control.spinbox,
                make_button(
                    self,
                    icon_name="clear-symbol",
                    tool_tip="Reset the target frequency to zero",
                    on_clicked=self._on_target_frequency_clear_button_clicked,
                ),
                self._target_frequency_control.slider,
                self._send_button,
            )
        )

    def get_widget_name_and_icon_name(self):
        return "Scalar control", "frequency-f"

    def stop(self):
        self.setEnabled(False)  # Safety first

        # This is not mandatory, but we do it anyway for extra safety.
        if self._send_button.isChecked():
            self._launch_async(self._commander.stop())

        # Restore the safest state by default (but don't touch any settings except target frequency)
        self._send_button.setChecked(False)
        self._send_button.setStyleSheet("")
        # This will not trigger any reaction from the callback because we're disabled already
        self._target_frequency_control.value = 0

    def on_general_status_update(self, timestamp: float, s: GeneralStatusView):
        with self._with_events_suppressed():
            if s.current_task_id in (
                TaskID.IDLE,
                TaskID.FAULT,
                TaskID.LOW_LEVEL_MANIPULATION,
            ):
                self.setEnabled(True)
            else:
                self.setEnabled(False)

    def _on_any_control_changed(self, *_):
        if self._event_suppression_depth > 0:
            return

        if not self.isEnabled():  # Safety feature
            return

        with self._with_events_suppressed():  # Paranoia
            if self._send_button.isChecked():
                vector = [
                    self._volt_per_hertz_control.value,
                    self._target_frequency_control.value,
                    self._frequency_gradient_control.value,
                ]
                _logger.debug("Sending scalar control command %r", vector)
                self._launch_async(
                    self._commander.low_level_manipulate(
                        LowLevelManipulationMode.SCALAR_CONTROL, *vector
                    )
                )

    def _on_send_button_changed(self):
        if self._send_button.isChecked():
            self._on_any_control_changed()
            self._send_button.setStyleSheet(_SEND_BUTTON_STYLESHEET_WHEN_ACTIVATED)
        else:
            self._send_button.setStyleSheet("")

    def _on_target_frequency_clear_button_clicked(self):
        self._target_frequency_control.value = 0

    @contextmanager
    def _with_events_suppressed(self):
        assert self._event_suppression_depth >= 0
        self._event_suppression_depth += 1
        yield
        self._event_suppression_depth -= 1
        assert self._event_suppression_depth >= 0

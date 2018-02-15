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
from PyQt5.QtWidgets import QWidget, QLabel, QCheckBox
from PyQt5.QtGui import QFont
from model.device_model import Commander, LowLevelManipulationMode, GeneralStatusView, TaskID
from view.utils import lay_out_horizontally, get_icon, make_button
from view.widgets.spinbox_linked_with_slider import SpinboxLinkedWithSlider
from .base import LowLevelManipulationControlSubWidgetBase


_HUNDRED_PERCENT = 100

_SEND_BUTTON_STYLESHEET_WHEN_ACTIVATED = 'QPushButton { background-color: #ff0; color: #330; font-weight: 600; }'


_logger = getLogger(__name__)


class Widget(LowLevelManipulationControlSubWidgetBase):
    # noinspection PyUnresolvedReferences
    def __init__(self,
                 parent:            QWidget,
                 commander:         Commander):
        super(Widget, self).__init__(parent)

        self._commander = commander
        self._event_suppression_depth = 0

        self._sync_checkbox = QCheckBox(self)
        self._sync_checkbox.setIcon(get_icon('link'))
        self._sync_checkbox.setChecked(True)
        self._sync_checkbox.stateChanged.connect(self._on_sync_checkbox_changed)
        self._sync_checkbox.setToolTip('Always same value for all phases')
        self._sync_checkbox.setStatusTip(self._sync_checkbox.toolTip())

        self._send_button = \
            make_button(self,
                        text='Execute',
                        icon_name='send-up',
                        tool_tip='Sends the command to the device; also, while this button is checked (pressed), '
                                 'commands will be send automatically every time the controls are changed by the user.',
                        checkable=True,
                        checked=False,
                        on_clicked=self._on_send_button_changed)

        self._phase_controls = [
            SpinboxLinkedWithSlider(self,
                                    minimum=0.0,
                                    maximum=100.0,
                                    step=1.0,
                                    slider_orientation=SpinboxLinkedWithSlider.SliderOrientation.HORIZONTAL)
            for _ in range(3)
        ]

        for pc in self._phase_controls:
            pc.spinbox_suffix = ' %'
            pc.value_change_event.connect(self._on_any_control_changed)

        def make_fat_label(text: str) -> QLabel:
            lbl = QLabel(text, self)
            font: QFont = lbl.font()
            font.setBold(True)
            lbl.setFont(font)
            return lbl

        top_layout_items = []

        for index, pc in enumerate(self._phase_controls):
            top_layout_items.append(lay_out_horizontally(
                make_fat_label('ABC'[index]),
                pc.spinbox,
                (pc.slider, 1),
            ))

        self.setLayout(
                lay_out_horizontally(*(top_layout_items + [self._send_button, self._sync_checkbox]))
        )

    def get_widget_name_and_icon_name(self):
        return 'Phase manipulation', 'sine'

    def stop(self):
        self.setEnabled(False)      # Safety first

        # This is not mandatory, but we do it anyway for extra safety.
        if self._send_button.isChecked():
            self._launch_async(self._commander.stop())

        with self._with_events_suppressed():
            # Events MUST be suppressed here, otherwise we will be receiving callbacks while the controls are being
            # changed, which may lead to emission of commands that can damage the hardware!
            for pc in self._phase_controls:
                pc.value = 0

            # Restore the safest state by default
            self._sync_checkbox.setChecked(True)
            self._send_button.setChecked(False)
            self._send_button.setStyleSheet('')

    def on_general_status_update(self, timestamp: float, s: GeneralStatusView):
        with self._with_events_suppressed():
            if s.current_task_id in (TaskID.IDLE,
                                     TaskID.FAULT,
                                     TaskID.LOW_LEVEL_MANIPULATION):
                self.setEnabled(True)
            else:
                self.setEnabled(False)

    def _on_any_control_changed(self, new_value: float):
        if self._event_suppression_depth > 0:
            return

        if not self.isEnabled():        # Safety feature
            return

        with self._with_events_suppressed():
            # Synchronize if necessary
            if self._sync_checkbox.isChecked():
                for pc in self._phase_controls:
                    pc.value = new_value

            if self._send_button.isChecked():
                vector = [(pc.value / _HUNDRED_PERCENT) for pc in self._phase_controls]
                for v in vector:
                    assert 0.0 <= v < 1.000001

                _logger.debug('Sending phase manipulation command %r', vector)
                self._launch_async(self._commander.low_level_manipulate(LowLevelManipulationMode.PHASE_MANIPULATION,
                                                                        *vector))

    def _on_sync_checkbox_changed(self):
        if self._sync_checkbox.isChecked():
            self._on_any_control_changed(0.0)   # Reset to zero to sync up

    def _on_send_button_changed(self):
        if self._send_button.isChecked():
            self._on_any_control_changed(self._phase_controls[0].value)
            self._send_button.setStyleSheet(_SEND_BUTTON_STYLESHEET_WHEN_ACTIVATED)
        else:
            self._send_button.setStyleSheet('')

    @contextmanager
    def _with_events_suppressed(self):
        assert self._event_suppression_depth >= 0
        self._event_suppression_depth += 1
        yield
        self._event_suppression_depth -= 1
        assert self._event_suppression_depth >= 0

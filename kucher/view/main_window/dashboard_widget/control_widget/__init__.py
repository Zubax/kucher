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
import asyncio
from logging import getLogger
from PyQt5.QtWidgets import QWidget, QToolBox, QSizePolicy
from view.device_model_representation import Commander, GeneralStatusView
from view.widgets.group_box_widget import GroupBoxWidget
from view.utils import make_button, lay_out_vertically, lay_out_horizontally, get_icon

from .base import SpecializedControlWidgetBase
from .run_control_widget import RunControlWidget
from .motor_identification_control_widget import MotorIdentificationControlWidget
from .hardware_test_control_widget import HardwareTestControlWidget
from .misc_control_widget import MiscControlWidget
from .low_level_manipulation_control_widget import LowLevelManipulationControlWidget


_logger = getLogger(__name__)


class ControlWidget(GroupBoxWidget):
    # noinspection PyArgumentList,PyUnresolvedReferences
    def __init__(self,
                 parent:    QWidget,
                 commander: Commander):
        super(ControlWidget, self).__init__(parent, 'Controls', 'adjust')

        self._commander: Commander = commander

        self._last_seen_timestamped_general_status: typing.Optional[typing.Tuple[float, GeneralStatusView]] = None

        self._run_widget = RunControlWidget(self, commander)
        self._motor_identification_widget = MotorIdentificationControlWidget(self, commander)
        self._hardware_test_widget = HardwareTestControlWidget(self, commander)
        self._misc_widget = MiscControlWidget(self, commander)
        self._low_level_manipulation_widget = LowLevelManipulationControlWidget(self, commander)

        self._panel = QToolBox(self)

        self._panel.addItem(self._run_widget, get_icon('running'), 'Run')
        self._panel.addItem(self._motor_identification_widget, get_icon('caliper'), 'Motor identification')
        self._panel.addItem(self._hardware_test_widget, get_icon('pass-fail'), 'Self-test')
        self._panel.addItem(self._misc_widget, get_icon('ellipsis'), 'Miscellaneous')
        self._panel.addItem(self._low_level_manipulation_widget, get_icon('ok-hand'), 'Low-level manipulation')

        self._current_widget: SpecializedControlWidgetBase = self._hardware_test_widget
        self._panel.setCurrentWidget(self._hardware_test_widget)

        # Configuring the event handler in the last order, because it might fire while we're configuring the widgets!
        self._panel.currentChanged.connect(self._on_current_widget_changed)

        self._stop_button =\
            make_button(self,
                        text='Stop',
                        icon_name='cancel',
                        tool_tip='Sends a regular stop command which instructs the controller to abandon the current'
                                 'task and activate the Idle task',
                        on_clicked=self._do_regular_stop)
        self._stop_button.setSizePolicy(QSizePolicy().MinimumExpanding,
                                        QSizePolicy().MinimumExpanding)

        self._emergency_button =\
            make_button(self,
                        text='EMERGENCY',
                        tool_tip='Stops the motor unconditionally and locks down the hardware until restarted',
                        on_clicked=self._do_emergency_stop)
        self._emergency_button.setSizePolicy(QSizePolicy().MinimumExpanding,
                                             QSizePolicy().MinimumExpanding)

        self._disable()
        self.setLayout(
            lay_out_vertically(
                (self._panel, 1),
                lay_out_horizontally(
                    (self._stop_button, 1),
                    (self._emergency_button, 1),
                )
            )
        )

    def on_connection_established(self):
        self._last_seen_timestamped_general_status = None
        self._enable()
        self._current_widget.start()

    def on_connection_loss(self):
        self._last_seen_timestamped_general_status = None
        self._current_widget.stop()
        self._disable()

    def on_general_status_update(self, timestamp: float, s: GeneralStatusView):
        self._last_seen_timestamped_general_status = timestamp, s
        self._current_widget.on_general_status_update(timestamp, s)

    def _on_current_widget_changed(self, new_widget_index: int):
        _logger.info(f'The user has changed the active widget. '
                     f'Stopping the previous widget, which was {self._current_widget!r}')
        self._current_widget.stop()

        self._current_widget = self._panel.currentWidget()
        assert isinstance(self._current_widget, SpecializedControlWidgetBase)

        _logger.info(f'Starting the new widget (at index {new_widget_index}), which is {self._current_widget!r}')
        self._current_widget.start()

        # We also make sure to always provide the newly activated widget with the latest known general status,
        # in order to let it actualize its state faster.
        if self._last_seen_timestamped_general_status is not None:
            self._current_widget.on_general_status_update(*self._last_seen_timestamped_general_status)

    def _enable(self):
        self.setEnabled(True)
        self._emergency_button.setStyleSheet('''QPushButton {
             background-color: #f00;
             font-weight: 600;
             color: #300;
        }''')

    def _disable(self):
        self.setEnabled(False)
        self._emergency_button.setStyleSheet('')

    def _do_regular_stop(self):
        self._launch(self._commander.stop())
        _logger.info('Stop button clicked')
        self.window().statusBar().showMessage('Stop command has been sent. '
                                              'The device may choose to disregard it, depending on the current task.')

    def _do_emergency_stop(self):
        for _ in range(3):
            self._launch(self._commander.emergency())

        _logger.warning('Emergency button clicked')
        self.window().statusBar().showMessage("DON'T PANIC. The hardware will remain unusable until restarted.")

    @staticmethod
    def _launch(coro: typing.Awaitable[None]):
        asyncio.get_event_loop().create_task(coro)

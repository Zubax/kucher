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
from view.device_model_representation import Commander
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
    # noinspection PyArgumentList
    def __init__(self,
                 parent:    QWidget,
                 commander: Commander):
        super(ControlWidget, self).__init__(parent, 'Controls', 'adjust')

        self._commander: Commander = commander

        self._panel = QToolBox(self)

        self._run_widget = RunControlWidget(self, commander)
        self._motor_identification_widget = MotorIdentificationControlWidget(self, commander)
        self._hardware_test_widget = HardwareTestControlWidget(self, commander)
        self._misc_widget = MiscControlWidget(self, commander)
        self._low_level_manipulation_widget = LowLevelManipulationControlWidget(self, commander)

        self._panel.addItem(self._run_widget, get_icon('running'), 'Run')
        self._panel.addItem(self._motor_identification_widget, get_icon('caliper'), 'Motor ID')
        self._panel.addItem(self._hardware_test_widget, get_icon('pass-fail'), 'Self-test')
        self._panel.addItem(self._misc_widget, get_icon('ellipsis'), 'Miscellaneous')
        self._panel.addItem(self._low_level_manipulation_widget, get_icon('ok-hand'), 'LL manipulation')

        self._panel.setCurrentWidget(self._hardware_test_widget)

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
                        text='EMERGENCY\nSTOP',
                        tool_tip='Stops the motor unconditionally and locks down the hardware until restarted',
                        on_clicked=self._do_emergency_stop)
        self._emergency_button.setSizePolicy(QSizePolicy().MinimumExpanding,
                                             QSizePolicy().MinimumExpanding)

        self.setEnabled(False)
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
        self.setEnabled(True)
        self._emergency_button.setStyleSheet('''QPushButton {
             background-color: #f33;
             border: 1px solid #800;
             font-weight: 600;
             color: #300;
        }''')

    def on_connection_loss(self):
        self.setEnabled(False)
        self._emergency_button.setStyleSheet('')

    def _do_regular_stop(self):
        pass

    def _do_emergency_stop(self):
        for _ in range(3):
            self._launch(self._commander.emergency())

        _logger.warning('Emergency button clicked')
        self.window().statusBar().showMessage("DON'T PANIC. The hardware will remain unusable until restarted.")

    @staticmethod
    def _launch(coro: typing.Awaitable[None]):
        asyncio.get_event_loop().create_task(coro)

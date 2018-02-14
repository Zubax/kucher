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

from PyQt5.QtWidgets import QWidget, QLabel
from view.device_model_representation import Commander, GeneralStatusView, TaskID
from .base import SpecializedControlWidgetBase
from view.utils import make_button, lay_out_vertically, lay_out_horizontally


class HardwareTestControlWidget(SpecializedControlWidgetBase):
    def __init__(self,
                 parent:    QWidget,
                 commander: Commander):
        super(HardwareTestControlWidget, self).__init__(parent)

        self._commander = commander

        self.setLayout(
            lay_out_vertically(
                QLabel('The motor must be connected in order for the self test to succeed.', self),
                lay_out_horizontally(
                    (None, 1),
                    make_button(self, text='Run self-test', icon_name='play', on_clicked=self._execute),
                    (None, 1),
                ),
                (None, 1),
            )
        )

    def start(self):
        pass

    def stop(self):
        self.setEnabled(False)

    def on_general_status_update(self, timestamp: float, s: GeneralStatusView):
        if s.current_task_id in (TaskID.RUNNING,
                                 TaskID.BEEPING,
                                 TaskID.HARDWARE_TEST,
                                 TaskID.LOW_LEVEL_MANIPULATION,
                                 TaskID.MOTOR_IDENTIFICATION):
            self.setEnabled(False)
        else:
            self.setEnabled(True)

    def _execute(self):
        self.setEnabled(False)
        self._launch_async(self._commander.begin_hardware_test())

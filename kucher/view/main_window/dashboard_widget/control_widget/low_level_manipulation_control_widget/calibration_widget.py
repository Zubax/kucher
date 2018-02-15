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

from logging import getLogger
from PyQt5.QtWidgets import QWidget, QLabel
from model.device_model import Commander, LowLevelManipulationMode, GeneralStatusView, TaskID
from view.utils import lay_out_vertically, lay_out_horizontally, make_button
from .base import LowLevelManipulationControlSubWidgetBase


_logger = getLogger(__name__)


class Widget(LowLevelManipulationControlSubWidgetBase):
    def __init__(self,
                 parent:            QWidget,
                 commander:         Commander):
        super(Widget, self).__init__(parent)
        self._commander = commander
        self.setLayout(
            lay_out_vertically(
                lay_out_horizontally(
                    QLabel('Calibrate the VSI hardware', self),
                    make_button(self,
                                text='Calibrate',
                                icon_name='scales',
                                on_clicked=self._execute),
                    (None, 1)
                ),
                (None, 1)
            )
        )

    def get_widget_name_and_icon_name(self):
        return 'Calibration', 'scales'

    def stop(self):
        pass

    def on_general_status_update(self, timestamp: float, s: GeneralStatusView):
        if s.current_task_id in (TaskID.IDLE,
                                 TaskID.FAULT):
            self.setEnabled(True)
        else:
            self.setEnabled(False)

    def _execute(self):
        _logger.info('Requesting calibration')
        self._launch_async(self._commander.low_level_manipulate(LowLevelManipulationMode.CALIBRATION))

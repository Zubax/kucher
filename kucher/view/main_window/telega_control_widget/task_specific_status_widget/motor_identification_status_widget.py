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

from PyQt5.QtWidgets import QWidget, QProgressBar

from kucher.view.device_model_representation import (
    GeneralStatusView,
    TaskSpecificStatusReport,
)
from kucher.view.utils import lay_out_vertically

from .base import StatusWidgetBase


class Widget(StatusWidgetBase):
    # noinspection PyArgumentList
    def __init__(self, parent: QWidget):
        super(Widget, self).__init__(parent)

        self._progress_bar = QProgressBar(self)
        self._progress_bar.setMinimum(0)
        self._progress_bar.setMaximum(100)

        self.setLayout(lay_out_vertically(self._progress_bar))

    def reset(self):
        self._progress_bar.setValue(0)

    def on_general_status_update(self, timestamp: float, s: GeneralStatusView):
        tssr = self._get_task_specific_status_report(
            TaskSpecificStatusReport.MotorIdentification, s
        )
        self._progress_bar.setValue(round(tssr.progress * 100))

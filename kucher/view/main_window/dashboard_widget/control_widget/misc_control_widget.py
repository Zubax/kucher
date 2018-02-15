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

from PyQt5.QtWidgets import QWidget, QDoubleSpinBox, QLabel
from view.device_model_representation import Commander, GeneralStatusView, TaskID
from view.utils import make_button, lay_out_horizontally, lay_out_vertically
from .base import SpecializedControlWidgetBase


class MiscControlWidget(SpecializedControlWidgetBase):
    def __init__(self,
                 parent:    QWidget,
                 commander: Commander):
        super(MiscControlWidget, self).__init__(parent)

        self._commander = commander

        self._frequency_input = QDoubleSpinBox(self)
        self._frequency_input.setRange(100, 15000)
        self._frequency_input.setValue(3000)
        self._frequency_input.setSuffix(' Hz')
        self._frequency_input.setToolTip('Beep frequency, in hertz')
        self._frequency_input.setStatusTip(self._frequency_input.toolTip())

        self._duration_input = QDoubleSpinBox(self)
        self._duration_input.setRange(0.01, 3)
        self._duration_input.setValue(0.5)
        self._duration_input.setSuffix(' s')
        self._duration_input.setToolTip('Beep duration, in seconds')
        self._duration_input.setStatusTip(self._duration_input.toolTip())

        self._go_button = make_button(self,
                                      text='Beep',
                                      icon_name='speaker',
                                      tool_tip='Sends a beep command to the device once',
                                      on_clicked=self._beep_once)

        self.setLayout(
            lay_out_vertically(
                lay_out_horizontally(
                    QLabel('Frequency', self),
                    self._frequency_input,
                    QLabel('Duration', self),
                    self._duration_input,
                    self._go_button,
                    (None, 1)
                ),
                (None, 1)
            )
        )

    def stop(self):
        pass

    def on_general_status_update(self, timestamp: float, s: GeneralStatusView):
        if s.current_task_id in (TaskID.BEEPING,
                                 TaskID.IDLE,
                                 TaskID.FAULT):
            self.setEnabled(True)
        else:
            self.setEnabled(False)

    def _beep_once(self):
        self._launch_async(self._commander.beep(frequency=self._frequency_input.value(),
                                                duration=self._duration_input.value()))

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

from PyQt5.QtWidgets import QWidget, QPushButton, QComboBox, QLabel
from view.device_model_representation import Commander, GeneralStatusView, TaskID, MotorIdentificationMode
from .base import SpecializedControlWidgetBase
from view.utils import get_icon, lay_out_vertically, lay_out_horizontally


class MotorIdentificationControlWidget(SpecializedControlWidgetBase):
    # noinspection PyUnresolvedReferences
    def __init__(self,
                 parent:    QWidget,
                 commander: Commander):
        super(MotorIdentificationControlWidget, self).__init__(parent)

        self._commander = commander

        self._mode_map = {
            _humanize(mid): mid for mid in MotorIdentificationMode
        }

        self._mode_selector = QComboBox(self)
        self._mode_selector.setEditable(False)
        # noinspection PyTypeChecker
        self._mode_selector.addItems(map(_humanize,
                                         sorted(MotorIdentificationMode,
                                                key=lambda x: x != MotorIdentificationMode.R_L_PHI)))

        go_button = QPushButton(get_icon('play'), 'Launch', self)
        go_button.clicked.connect(self._execute)

        self.setLayout(
            lay_out_vertically(
                lay_out_horizontally(
                    QLabel('Select parameters to estimate:', self),
                    self._mode_selector,
                    (None, 1),
                ),
                lay_out_horizontally(
                    QLabel('Then click', self),
                    go_button,
                    QLabel('and wait. The process will take a few minutes to complete.', self),
                    (None, 1),
                ),
                (None, 1)
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
        mid = self._mode_map[self._mode_selector.currentText().strip()]
        self._launch_async(self._commander.begin_motor_identification(mid))


def _humanize(mid: MotorIdentificationMode) -> str:
    try:
        return {
            MotorIdentificationMode.R_L:        'Resistance, Inductance',
            MotorIdentificationMode.PHI:        'Flux linkage',
            MotorIdentificationMode.R_L_PHI:    'Resistance, Inductance, Flux linkage',
        }[mid]
    except KeyError:
        return str(mid).upper().split('.')[-1].replace('_', ' ')

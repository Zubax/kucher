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

from PyQt5.QtWidgets import QWidget, QPushButton, QSizePolicy, QToolButton, QAction
from PyQt5.QtCore import Qt
from view.device_model_representation import Commander, GeneralStatusView, TaskID, MotorIdentificationMode
from .base import SpecializedControlWidgetBase
from view.utils import get_icon, lay_out_vertically, lay_out_horizontally


class MotorIdentificationControlWidget(SpecializedControlWidgetBase):
    def __init__(self,
                 parent:    QWidget,
                 commander: Commander):
        super(MotorIdentificationControlWidget, self).__init__(parent)

        self._commander = commander

        mode_button = QToolButton(self)
        mode_button.setText('Launch...')
        mode_button.setIcon(get_icon('play'))
        mode_button.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)
        mode_button.setPopupMode(QToolButton.InstantPopup)
        mode_button.setSizePolicy(QSizePolicy.MinimumExpanding,
                                  QSizePolicy.MinimumExpanding)

        # noinspection PyUnresolvedReferences
        def create(mid: MotorIdentificationMode):
            raw_name = str(mid).split('.')[-1]
            human_name = _humanize(mid)
            action = QAction(human_name, self)
            action.setToolTip(raw_name)
            action.setStatusTip(raw_name)
            action.triggered.connect(lambda *_: self._execute(mid))
            mode_button.addAction(action)

        # noinspection PyTypeChecker
        for motor_id_mode in sorted(MotorIdentificationMode,
                                    key=lambda x: x != MotorIdentificationMode.R_L_PHI):
            create(motor_id_mode)

        self.setLayout(
            lay_out_vertically(
                mode_button,
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

    def _execute(self, mid: MotorIdentificationMode):
        self.setEnabled(False)
        self._launch_async(self._commander.begin_motor_identification(mid))


def _humanize(mid: MotorIdentificationMode) -> str:
    try:
        return {
            MotorIdentificationMode.R_L:        'Resistance,\nInductance',
            MotorIdentificationMode.PHI:        'Flux\nlinkage',
            MotorIdentificationMode.R_L_PHI:    'Resistance, Inductance,\nFlux linkage',
        }[mid]
    except KeyError:
        return str(mid).upper().split('.')[-1].replace('_', ' ')

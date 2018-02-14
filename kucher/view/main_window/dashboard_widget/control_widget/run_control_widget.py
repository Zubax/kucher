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

import re
import typing
from PyQt5.QtWidgets import QWidget, QCheckBox, QToolButton, QAction, QSlider, QDoubleSpinBox, QSizePolicy, QLabel
from PyQt5.QtCore import Qt
from view.device_model_representation import Commander, GeneralStatusView, ControlMode
from view.utils import get_icon, lay_out_vertically, lay_out_horizontally
from .base import SpecializedControlWidgetBase


_CONTROL_MODES_AVAILABLE_IN_NON_GURU_MODE = [
    ControlMode.CURRENT,
    ControlMode.MECHANICAL_RPM,
    ControlMode.RATIOMETRIC_CURRENT,
    ControlMode.RATIOMETRIC_ANGULAR_VELOCITY,
]


class RunControlWidget(SpecializedControlWidgetBase):
    # noinspection PyUnresolvedReferences,PyArgumentList
    def __init__(self,
                 parent:    QWidget,
                 commander: Commander):
        super(RunControlWidget, self).__init__(parent)

        self._commander = commander

        self._control_modes_mapping: typing.Dict[str, ControlMode] = {}

        self._guru_mode_check_box = QCheckBox('Guru mode', self)
        self._guru_mode_check_box.setToolTip("The Guru Mode is dangerous! "
                                             "Use it only if you know what you're doing, and be ready for problems.")
        self._guru_mode_check_box.setStatusTip(self._guru_mode_check_box.toolTip())
        self._guru_mode_check_box.setIcon(get_icon('guru'))
        self._guru_mode_check_box.toggled.connect(self._on_guru_mode_toggled)

        self._spinbox = QDoubleSpinBox(self)
        self._spinbox.setMinimum(-100.0)
        self._spinbox.setMaximum(+100.0)
        self._spinbox.setValue(0.0)
        self._spinbox.setSingleStep(0.1)

        self._slider = QSlider(Qt.Horizontal, self)
        self._slider.setMinimum(-1000)
        self._slider.setMaximum(+1000)
        self._slider.setValue(0)
        self._slider.setTickInterval(1000)
        self._slider.setTickPosition(QSlider.TicksBothSides)

        mode_button = QToolButton(self)
        mode_button.setText('Launch...')
        mode_button.setIcon(get_icon('plot'))
        mode_button.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)
        mode_button.setPopupMode(QToolButton.InstantPopup)
        mode_button.setSizePolicy(QSizePolicy.MinimumExpanding,
                                  QSizePolicy.MinimumExpanding)

        self._actions_available_in_guru_mode_only: typing.List[QAction] = []

        for cm in ControlMode:
            pass

        self.setLayout(
            lay_out_vertically(
                lay_out_horizontally(
                    mode_button,
                    (None, 1),
                    self._guru_mode_check_box,
                ),
                lay_out_horizontally(
                    QLabel('Setpoint:', self),
                    (self._spinbox, 1),
                    QLabel('RPM', self),
                ),
                self._slider,
                (None, 1)
            )
        )

    def start(self):
        pass

    def stop(self):
        pass

    def on_general_status_update(self, timestamp: float, s: GeneralStatusView):
        pass

    def _on_guru_mode_toggled(self, active: bool):
        pass


class _ControlPolicy:
    def __init__(self, control_mode: ControlMode):
        self.control_mode: ControlMode = control_mode

        self.full_name: str  = _get_full_name(control_mode)
        self.short_name: str = _get_short_name(control_mode)

        self.guru_mode_required: bool = control_mode not in _CONTROL_MODES_AVAILABLE_IN_NON_GURU_MODE

        self.is_ratiometric = 'ratiometric' in str(control_mode).lower()


_REPLACEMENT_PATTERNS = {
    r'(\W?)RPM(\W?)': r'\1RPM\2',       # This regexp is glitchy and should be fixed
}


def _get_full_name(cm: ControlMode) -> str:
    name = str(cm).split('.')[-1].replace('_', ' ')
    name = name.capitalize()

    for pattern, replacement in _REPLACEMENT_PATTERNS.items():
        name = re.sub(pattern, replacement, name, flags=re.IGNORECASE)

    return name


def _get_short_name(cm: ControlMode) -> str:
    try:
        return {
            ControlMode.RATIOMETRIC_CURRENT:            'RIq',
            ControlMode.RATIOMETRIC_ANGULAR_VELOCITY:   'R\u03C9',
            ControlMode.RATIOMETRIC_VOLTAGE:            'RUq',
            ControlMode.CURRENT:                        'Iq',
            ControlMode.MECHANICAL_RPM:                 'RPM',
            ControlMode.VOLTAGE:                        'Uq',
        }[cm]
    except KeyError:
        return ''.join([x[0] for x in str(cm).split('.')[-1].split('_')])

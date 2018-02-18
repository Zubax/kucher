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

import math
import typing
from .base import StatusWidgetBase
from PyQt5.QtWidgets import QWidget, QLabel, QGridLayout, QFrame
from PyQt5.QtGui import QFont, QFontMetrics
from PyQt5.QtCore import Qt
from view.device_model_representation import GeneralStatusView, TaskSpecificStatusReport,\
    get_human_friendly_control_mode_name_and_its_icon_name
from view.utils import lay_out_vertically, lay_out_horizontally
from view.widgets.value_display_widget import ValueDisplayWidget


class Widget(StatusWidgetBase):
    # noinspection PyArgumentList
    def __init__(self, parent: QWidget):
        super(Widget, self).__init__(parent)

        self._stall_count_display =\
            self._make_display('Stall count',
                               'Number of times the rotor stalled since task activation')

        self._estimated_active_power_display =\
            self._make_display('Active power',
                               'For well-balanced systems, the estimated active power equals the DC power')

        self._demand_factor_display = \
            self._make_display('Demand factor',
                               'Percent of the maximum rated power output')

        self._mechanical_rpm_display = \
            self._make_display('M. RPM',
                               'Mechanical revolutions per minute')

        self._current_frequency_display = \
            self._make_display('Current frq.',
                               'Frequency of three-phase currents and voltages')

        self._dq_display = _DQDisplayWidget(self)

        self._control_mode_display = \
            self._make_display('Ctrl. mode',
                               'Control mode used by the controller',
                               True)

        self._reverse_flag_display = \
            self._make_display('Direction',
                               'Direction of rotation',
                               True)

        self._spinup_flag_display = \
            self._make_display('Started?',
                               'Whether the motor has started or still starting',
                               True)

        self._saturation_flag_display = \
            self._make_display('CSSW',
                               'Control System Saturation Warning',
                               True)

        self.setLayout(
            lay_out_horizontally(
                (lay_out_vertically(
                    self._mechanical_rpm_display,
                    self._current_frequency_display,
                    self._stall_count_display,
                    self._demand_factor_display,
                ), 1),
                _make_vertical_separator(self),
                (lay_out_vertically(
                    self._dq_display,
                    self._estimated_active_power_display,
                    (None, 1),
                ), 1),
                _make_vertical_separator(self),
                (lay_out_vertically(
                    self._control_mode_display,
                    self._reverse_flag_display,
                    self._spinup_flag_display,
                    self._saturation_flag_display,
                ), 1),
            )
        )

    def reset(self):
        num_reset = 0
        for ch in self.findChildren(ValueDisplayWidget):
            num_reset += 1
            ch.reset()

        assert num_reset > 7        # Simple paranoid check that PyQt is working as I expect it to

        self._dq_display.reset()

    def on_general_status_update(self, timestamp: float, s: GeneralStatusView):
        tssr = self._get_task_specific_status_report(TaskSpecificStatusReport.Running, s)

        self._stall_count_display.set(f'{tssr.stall_count}')

        self._demand_factor_display.set(f'{tssr.demand_factor * 100.0:.0f}%')

        self._mechanical_rpm_display.set(
            f'{_angular_velocity_to_rpm(tssr.mechanical_angular_velocity):.0f} RPM')

        self._current_frequency_display.set(
            f'{_angular_velocity_to_frequency(tssr.electrical_angular_velocity):.1f} Hz')

        self._display_estimated_active_power(tssr)

        self._dq_display.set(tssr.u_dq,
                             tssr.i_dq)

        cm_name, cm_icon_name = get_human_friendly_control_mode_name_and_its_icon_name(tssr.mode, short=True)
        self._control_mode_display.set(cm_name,
                                       comment=str(tssr.mode).split('.')[-1],
                                       icon_name=cm_icon_name)

        self._reverse_flag_display.set('Reverse' if tssr.rotation_reversed else 'Forward',
                                       icon_name='jog-reverse' if tssr.rotation_reversed else 'jog-forward')

        self._spinup_flag_display.set('Starting' if tssr.spinup_in_progress else 'Started',
                                      icon_name='warning' if tssr.spinup_in_progress else 'ok-strong')

        self._saturation_flag_display.set('Saturated' if tssr.controller_saturated else 'Not saturated',
                                          icon_name='control-saturation' if tssr.controller_saturated else 'ok-strong')

    def _display_estimated_active_power(self, tssr: TaskSpecificStatusReport.Running):
        # We consider this logic part of the view rather than model because it essentially
        # converts representation of existing data using well-known principles
        (u_d, u_q), (i_d, i_q) = tssr.u_dq, tssr.i_dq
        active_power = (u_d * i_d + u_q * i_q) * 3 / 2

        self._estimated_active_power_display.set(f'{active_power:.0f} W')

    def _make_display(self, title: str, tooltip: str, with_comment: bool=False) -> ValueDisplayWidget:
        return ValueDisplayWidget(self,
                                  title=title,
                                  with_comment=with_comment,
                                  tooltip=tooltip)


class _DQDisplayWidget(QWidget):
    # noinspection PyArgumentList
    def __init__(self, parent: QWidget):
        super(_DQDisplayWidget, self).__init__(parent)

        def make_label(text: str='') -> QLabel:
            w = QLabel(text, self)
            w.setAlignment(Qt.AlignVCenter | Qt.AlignRight)
            font = QFont()
            font.setBold(True)
            w.setFont(font)
            return w

        self._ud = make_label()
        self._uq = make_label()
        self._id = make_label()
        self._iq = make_label()

        self._ud.setToolTip('Direct axis voltage')
        self._uq.setToolTip('Quadrature axis voltage')
        self._id.setToolTip('Direct axis current')
        self._iq.setToolTip('Quadrature axis current')

        # 0  1  2
        # 1 Ud Uq
        # 2 Id Iq
        layout = QGridLayout(self)
        layout.addWidget(QLabel('Udq', self), 0, 0)
        layout.addWidget(QLabel('Idq', self), 1, 0)
        layout.addWidget(self._ud, 0, 1)
        layout.addWidget(self._uq, 0, 2)
        layout.addWidget(self._id, 1, 1)
        layout.addWidget(self._iq, 1, 2)
        layout.addWidget(make_label('V'), 0, 3)
        layout.addWidget(make_label('A'), 1, 3)
        layout.setColumnStretch(0, 4)
        layout.setColumnStretch(1, 2)
        layout.setColumnStretch(2, 2)
        layout.setColumnStretch(3, 1)
        layout.setContentsMargins(0, 0, 0, 0)
        self.setLayout(layout)

    def set(self,
            u_dq: typing.Tuple[float, float],
            i_dq: typing.Tuple[float, float]):
        def fmt(x: float) -> str:
            return f'{x:.1f}'

        self._ud.setText(fmt(u_dq[0]))
        self._uq.setText(fmt(u_dq[1]))
        self._id.setText(fmt(i_dq[0]))
        self._iq.setText(fmt(i_dq[1]))

    def reset(self):
        for w in (self._ud, self._uq, self._id, self._iq):
            w.setText('0')


_2PI = math.pi * 2


def _angular_velocity_to_rpm(radian_per_sec) -> float:
    return radian_per_sec * (60.0 / _2PI)


def _angular_velocity_to_frequency(radian_per_sec) -> float:
    return radian_per_sec / _2PI


# noinspection PyArgumentList
def _make_vertical_separator(parent: QWidget) -> QWidget:
    # https://stackoverflow.com/questions/10053839/how-does-designer-create-a-line-widget
    line = QFrame(parent)
    line.setFrameShape(QFrame.VLine)
    line.setStyleSheet('QFrame { color: palette(mid); };')
    line.setMinimumWidth(QFontMetrics(QFont()).width('__') * 2)
    return line

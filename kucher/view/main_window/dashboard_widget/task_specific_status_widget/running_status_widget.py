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
from .base import StatusWidgetBase
from PyQt5.QtWidgets import QWidget
from view.device_model_representation import GeneralStatusView, TaskSpecificStatusReport
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
            self._make_display('Mechanical RPM',
                               'Mechanical revolutions per minute')

        self._current_frequency_display = \
            self._make_display('Current frequency',
                               'Phase current/voltage frequency')

        self.setLayout(
            lay_out_vertically(
                lay_out_horizontally(self._mechanical_rpm_display,
                                     self._current_frequency_display,
                                     self._demand_factor_display,
                                     self._estimated_active_power_display,
                                     self._stall_count_display)
            )
        )

    def reset(self):
        num_reset = 0
        for ch in self.findChildren(ValueDisplayWidget):
            num_reset += 1
            ch.reset()

        assert num_reset > 4        # Simple paranoid check that PyQt is working as I expect it to

    def on_general_status_update(self, timestamp: float, s: GeneralStatusView):
        tssr = self._get_task_specific_status_report(TaskSpecificStatusReport.Running, s)

        self._stall_count_display.set(f'{tssr.stall_count}')

        self._estimated_active_power_display.set(f'{tssr.estimated_active_power:.0f} W')

        self._demand_factor_display.set(f'{tssr.demand_factor:.0f}%')

        self._mechanical_rpm_display.set(
            f'{_angular_velocity_to_rpm(tssr.mechanical_angular_velocity):.0f} RPM')

        self._current_frequency_display.set(
            f'{_angular_velocity_to_frequency(tssr.electrical_angular_velocity):.1f} Hz')

    def _make_display(self, title: str, tooltip: str) -> ValueDisplayWidget:
        return ValueDisplayWidget(self,
                                  title=title,
                                  tooltip=tooltip)


_2PI = math.pi * 2


def _angular_velocity_to_rpm(radian_per_sec) -> float:
    return radian_per_sec * (60.0 / _2PI)


def _angular_velocity_to_frequency(radian_per_sec) -> float:
    return radian_per_sec / _2PI

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

from dataclasses import dataclass
from PyQt5.QtWidgets import QWidget
from ..widgets.value_display_group_widget import ValueDisplayGroupWidget, ValueDisplayWidget


class HardwareFlagCountersWidget(ValueDisplayGroupWidget):
    @dataclass
    class FlagState:
        event_count:    int = 0
        active:         bool = False

    # noinspection PyArgumentList,PyCallingNonCallable
    def __init__(self, parent: QWidget):
        super(HardwareFlagCountersWidget, self).__init__(parent,
                                                         'Hardware flag counters',
                                                         'integrated-circuit',
                                                         with_comments=True)
        placeholder = '0'

        self._lvps_malfunction = self.create_value_display('LVPS malfunction',
                                                           placeholder,
                                                           tooltip='Low-voltage power supply malfunction')

        self._overload = self.create_value_display('Overload',
                                                   placeholder,
                                                   tooltip='Critical hardware overload or critical overheating')

        self._fault = self.create_value_display('Fault',
                                                placeholder,
                                                tooltip='Hardware fault flag')

    def set(self,
            lvps_malfunction: FlagState,
            overload:         FlagState,
            fault:            FlagState):
        self._display(lvps_malfunction, self._lvps_malfunction)
        self._display(overload, self._overload)
        self._display(fault, self._fault)

    @staticmethod
    def _display(state, display_target: ValueDisplayWidget):
        if state.active:
            style = ValueDisplayWidget.Style.ALERT_ERROR
            comment = 'Flag set'
            icon_name = 'flag-red'
        else:
            style = ValueDisplayWidget.Style.NORMAL
            comment = 'Not set'
            icon_name = 'ok'

        display_target.set(str(state.event_count),
                           style=style,
                           comment=comment,
                           icon_name=icon_name)

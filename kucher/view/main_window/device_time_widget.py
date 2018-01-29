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

import typing
import datetime
import decimal
from decimal import Decimal
from PyQt5.QtWidgets import QWidget
from ..widgets.value_display_group_widget import ValueDisplayGroupWidget


class DeviceTimeWidget(ValueDisplayGroupWidget):
    def __init__(self, parent: QWidget):
        super(DeviceTimeWidget, self).__init__(parent, 'Device time', 'clock')
        self._time_display = self.create_value_display('Since boot', 'N/A')

    def set(self, device_time: Decimal):
        as_string = _duration_to_string(device_time)
        self._time_display.set(as_string)


def _duration_to_string(dur: typing.Union[Decimal, float]) -> str:
    if isinstance(dur, Decimal):
        dur = int(dur.quantize(1, rounding=decimal.ROUND_05UP))
    else:
        dur = int(round(dur, 0))

    return str(datetime.timedelta(seconds=float(dur))).replace(' days,', 'd').replace(' day,', 'd')


def _unittest_duration_to_string():
    assert _duration_to_string(0) == '0:00:00'
    assert _duration_to_string(3600) == '1:00:00'
    assert _duration_to_string(86400) == '1d 0:00:00'
    assert _duration_to_string(2 * 86400 + 3600 + 60 + 7.123) == '2d 1:01:07'

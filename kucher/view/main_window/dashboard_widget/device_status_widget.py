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
from view.widgets.value_display_group_widget import ValueDisplayGroupWidget
from view.device_model_representation import TaskID, get_icon_name_for_task_id


class DeviceStatusWidget(ValueDisplayGroupWidget):
    def __init__(self, parent: QWidget):
        super(DeviceStatusWidget, self).__init__(parent, 'Device status', 'question-mark')
        self.setToolTip('Use the Task Statistics view for more information')

        self._task_display = self.create_value_display('Current task', 'N/A')

        self._monotonic_time_display = self.create_value_display('Monotonic time', 'N/A',
                                                                 'Time since boot')

    def set(self,
            current_task_id: TaskID,
            monotonic_device_time: Decimal):
        raw_task_name = str(current_task_id).split('.')[-1]
        task_name_words = raw_task_name.split('_')
        if len(task_name_words) > 1:
            short_task_name = ''.join([w[0].upper() for w in task_name_words])
        else:
            short_task_name = task_name_words[0].capitalize()

        self._task_display.set(short_task_name)
        self._task_display.setToolTip(raw_task_name)

        self._monotonic_time_display.set(_duration_to_string(monotonic_device_time))

        self.set_icon(get_icon_name_for_task_id(current_task_id))

    def reset(self):
        super(DeviceStatusWidget, self).reset()
        self.set_icon('question-mark')


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

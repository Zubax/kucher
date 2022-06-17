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

from kucher.view.widgets.value_display_group_widget import ValueDisplayGroupWidget
from kucher.view.device_model_representation import (
    TaskID,
    get_icon_name_for_task_id,
    get_human_friendly_task_name,
)


class DeviceStatusWidget(ValueDisplayGroupWidget):
    def __init__(self, parent: QWidget):
        super(DeviceStatusWidget, self).__init__(
            parent, "Device status", "question-mark"
        )
        self.setToolTip("Use the Task Statistics view for more information")

        self._task_display = self.create_value_display("Current task", "N/A")

        self._monotonic_time_display = self.create_value_display(
            "Mono clock", "N/A", "Steady monotonic clock measuring time since boot"
        )

        self.create_value_display(
            ""
        )  # Reserved/placeholder, needed for better alignment
        self.create_value_display(
            ""
        )  # Reserved/placeholder, needed for better alignment

    def set(self, current_task_id: TaskID, monotonic_device_time: Decimal):
        self._task_display.set(
            get_human_friendly_task_name(current_task_id, short=True)
        )
        self._task_display.setToolTip(str(current_task_id).split(".")[-1])
        self._task_display.setStatusTip(self._task_display.toolTip())

        self._monotonic_time_display.set(_duration_to_string(monotonic_device_time))

        self.set_icon(get_icon_name_for_task_id(current_task_id))

    def reset(self):
        super(DeviceStatusWidget, self).reset()
        self.set_icon("question-mark")


def _duration_to_string(dur: typing.Union[Decimal, float]) -> str:
    if isinstance(dur, Decimal):
        # Time must be always rounded towards zero for correct results!
        dur = int(dur.quantize(1, rounding=decimal.ROUND_FLOOR))
    else:
        dur = int(round(dur, 0))

    return (
        str(datetime.timedelta(seconds=float(dur)))
        .replace(" days,", "d")
        .replace(" day,", "d")
    )


def _unittest_duration_to_string():
    assert _duration_to_string(0) == "0:00:00"
    assert _duration_to_string(3600) == "1:00:00"
    assert _duration_to_string(86400) == "1d 0:00:00"
    assert _duration_to_string(2 * 86400 + 3600 + 60 + 7.123) == "2d 1:01:07"

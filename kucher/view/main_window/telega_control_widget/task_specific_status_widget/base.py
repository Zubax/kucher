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
from PyQt5.QtWidgets import QWidget
from view.device_model_representation import GeneralStatusView


_TSSRType = typing.TypeVar('TSSR')


class StatusWidgetBase(QWidget):
    # noinspection PyArgumentList
    def __init__(self, parent: QWidget):
        super(StatusWidgetBase, self).__init__(parent)

    def reset(self):
        raise NotImplementedError

    def on_general_status_update(self, timestamp: float, s: GeneralStatusView):
        raise NotImplementedError

    @staticmethod
    def _get_task_specific_status_report(expected_type: typing.Type[_TSSRType], s: GeneralStatusView) -> _TSSRType:
        if isinstance(s.task_specific_status_report, expected_type):
            return s.task_specific_status_report
        else:
            raise TypeError(f'task_specific_status_report was expected to be {expected_type!r}, '
                            f'got {type(s.task_specific_status_report)!r}')

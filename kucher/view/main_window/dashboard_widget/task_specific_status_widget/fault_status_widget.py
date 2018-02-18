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

from .base import StatusWidgetBase
from PyQt5.QtWidgets import QWidget, QLabel, QLineEdit
from PyQt5.QtGui import QFont, QFontMetrics
from PyQt5.QtCore import Qt
from view.device_model_representation import GeneralStatusView, TaskSpecificStatusReport, get_icon_name_for_task_id
from view.utils import lay_out_horizontally, lay_out_vertically, get_monospace_font, get_icon


class Widget(StatusWidgetBase):
    # noinspection PyArgumentList
    def __init__(self, parent: QWidget):
        super(Widget, self).__init__(parent)

        self._last_displayed: TaskSpecificStatusReport.Fault = None

        self._line_height = QFontMetrics(QFont()).height()

        self._task_icon_display = QLabel(self)
        self._task_name_display = self._make_display()

        self._error_code_dec = self._make_display('Exit code in decimal')
        self._error_code_hex = self._make_display('Same exit code in hexadecimal')
        self._error_code_bin = self._make_display('Same exit code in binary, for extra convenience')

        self._error_description_display = self._make_display()

        self.setLayout(
            lay_out_vertically(
                lay_out_horizontally(QLabel('The task', self),
                                     self._task_icon_display,
                                     (self._task_name_display, 3)),
                lay_out_horizontally(QLabel('has failed with exit code', self),
                                     (self._error_code_dec, 1),
                                     (self._error_code_hex, 1),
                                     (self._error_code_bin, 2),
                                     QLabel('which means:', self)),
                lay_out_horizontally((self._error_description_display, 1)),
                (None, 1),
            )
        )

    def reset(self):
        self._last_displayed = None
        self._task_icon_display.clear()
        self._task_name_display.clear()
        self._error_code_dec.clear()
        self._error_code_hex.clear()
        self._error_code_bin.clear()
        self._error_description_display.clear()

    def on_general_status_update(self, timestamp: float, s: GeneralStatusView):
        tssr = self._get_task_specific_status_report(TaskSpecificStatusReport.Fault, s)
        if tssr == self._last_displayed:
            return

        self._last_displayed = tssr

        icon = get_icon(get_icon_name_for_task_id(tssr.failed_task_id))
        self._task_icon_display.setPixmap(icon.pixmap(self._line_height, self._line_height))

        self._task_name_display.setText(str(tssr.failed_task_id).split('.')[-1])

        self._error_code_dec.setText(f'{tssr.failed_task_exit_code}')
        self._error_code_hex.setText(f'0x{tssr.failed_task_exit_code:02X}')
        self._error_code_bin.setText(f'0b{tssr.failed_task_exit_code:08b}')

        self._error_description_display.setText('(elaboration not available)')

    def _make_display(self, tool_tip: str=''):
        o = QLineEdit(self)
        o.setReadOnly(True)
        o.setFont(get_monospace_font())
        o.setAlignment(Qt.AlignCenter)
        o.setToolTip(tool_tip)
        return o

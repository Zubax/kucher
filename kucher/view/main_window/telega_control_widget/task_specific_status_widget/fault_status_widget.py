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

import os
import yaml

from PyQt5.QtWidgets import QWidget, QLabel, QLineEdit, QTextEdit
from PyQt5.QtGui import QFont, QFontMetrics
from PyQt5.QtCore import Qt

from kucher.view.utils import (
    lay_out_horizontally,
    lay_out_vertically,
    get_monospace_font,
    get_icon_pixmap,
)
from kucher.view.device_model_representation import (
    GeneralStatusView,
    TaskSpecificStatusReport,
    get_icon_name_for_task_id,
    get_human_friendly_task_name,
)
from kucher.resources import get_absolute_path

from .base import StatusWidgetBase


class Widget(StatusWidgetBase):
    # noinspection PyArgumentList
    def __init__(self, parent: QWidget):
        super(Widget, self).__init__(parent)

        self._last_displayed: TaskSpecificStatusReport.Fault = None

        self._line_height = QFontMetrics(QFont()).height()

        self._task_icon_display = QLabel(self)
        self._task_name_display = self._make_line_display()

        self._error_code_dec = self._make_line_display("Exit code in decimal")
        self._error_code_hex = self._make_line_display("Same exit code in hexadecimal")
        self._error_code_bin = self._make_line_display(
            "Same exit code in binary, for extra convenience"
        )

        self._error_description_display = self._make_line_display(
            "Error description", False
        )
        self._error_comment_display = self._make_text_display()

        self.setLayout(
            lay_out_vertically(
                lay_out_horizontally(
                    QLabel("The task", self),
                    self._task_icon_display,
                    (self._task_name_display, 3),
                ),
                lay_out_horizontally(
                    QLabel("has failed with exit code", self),
                    (self._error_code_dec, 1),
                    (self._error_code_hex, 1),
                    (self._error_code_bin, 2),
                    QLabel("which means:", self),
                ),
                lay_out_horizontally((self._error_description_display, 1)),
                lay_out_horizontally((self._error_comment_display, 1)),
                (None, 1),
            )
        )

    def reset(self):
        self._last_displayed = None
        self._task_icon_display.clear()
        self._task_name_display.clear()
        self._task_name_display.setToolTip("")
        self._error_code_dec.clear()
        self._error_code_hex.clear()
        self._error_code_bin.clear()
        self._error_description_display.clear()

    def on_general_status_update(self, timestamp: float, s: GeneralStatusView):
        tssr = self._get_task_specific_status_report(TaskSpecificStatusReport.Fault, s)
        if tssr == self._last_displayed:
            return

        self._last_displayed = tssr

        pixmap = get_icon_pixmap(
            get_icon_name_for_task_id(tssr.failed_task_id), self._line_height
        )
        self._task_icon_display.setPixmap(pixmap)

        self._task_name_display.setText(str(tssr.failed_task_id).split(".")[-1])
        self._task_name_display.setToolTip(
            get_human_friendly_task_name(tssr.failed_task_id)
        )

        self._error_code_dec.setText(f"{tssr.failed_task_exit_code}")
        self._error_code_hex.setText(f"0x{tssr.failed_task_exit_code:02X}")
        self._error_code_bin.setText(f"0b{tssr.failed_task_exit_code:08b}")

        file_name = get_absolute_path(
            "view",
            "main_window",
            "telega_control_widget",
            "task_specific_status_widget",
            f"error_codes.yml",
            check_existence=True,
        )
        with open(file_name, "r") as f:
            error_codes = yaml.safe_load(f)

        failed_task_name = str(tssr.failed_task_id).split(".")[-1]

        error = error_codes[failed_task_name].get(
            tssr.failed_task_exit_code, "unknown error"
        )
        error_description = (
            error.get("description", "unknown error")
            if isinstance(error, dict)
            else error
        )
        error_comment = error.get("comment", "") if isinstance(error, dict) else ""

        self._error_description_display.setText(error_description)
        self._error_comment_display.setText(error_comment)

    def _make_line_display(self, tool_tip: str = "", is_monospace: bool = True):
        o = QLineEdit(self)
        o.setReadOnly(True)
        if is_monospace:
            o.setFont(get_monospace_font())
        o.setAlignment(Qt.AlignCenter)
        o.setToolTip(tool_tip)
        return o

    def _make_text_display(self, tool_tip: str = ""):
        o = QTextEdit(self)
        o.setReadOnly(True)
        o.setLineWrapMode(True)
        o.setMaximumHeight(60)
        o.setToolTip(tool_tip)
        return o

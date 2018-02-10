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
from logging import getLogger
from PyQt5.QtWidgets import QWidget, QTableWidget, QTableWidgetItem, QVBoxLayout, QApplication
from PyQt5.QtGui import QKeyEvent, QKeySequence
from PyQt5.QtCore import Qt
from view.utils import get_monospace_font
from view.device_model_representation import BasicDeviceInfo
from view.widgets import WidgetBase


_logger = getLogger(__name__)


class LittleBobbyTablesWidget(WidgetBase):
    # noinspection PyArgumentList
    def __init__(self, parent: QWidget):
        super(LittleBobbyTablesWidget, self).__init__(parent)

        self._table = QTableWidget(self)
        self._table.setColumnCount(1)
        self._table.horizontalHeader().hide()
        self._table.setFont(get_monospace_font())
        self._table.horizontalHeader().setSectionResizeMode(self._table.horizontalHeader().ResizeToContents)
        self._table.horizontalHeader().setStretchLastSection(True)
        self._table.verticalHeader().setSectionResizeMode(self._table.verticalHeader().ResizeToContents)

        lay_on_macduff = QVBoxLayout()
        lay_on_macduff.addWidget(self._table)
        lay_on_macduff.setContentsMargins(0, 0, 0, 0)
        self.setLayout(lay_on_macduff)

    def set(self, device_info: BasicDeviceInfo):
        self.clear()

        sw_ver = device_info.software_version
        sw_string = f'{sw_ver.major}.{sw_ver.minor}.{sw_ver.vcs_commit_id:08x}.{sw_ver.image_crc:16x}'
        if sw_ver.dirty_build:
            sw_string += '-dirty'

        if not sw_ver.release_build:
            sw_string += '-debug'

        hw_ver = device_info.hardware_version

        self._assign_many([
            ('Device name',         device_info.name),
            ('Device description',  device_info.description),
            ('Software version',    sw_string),
            ('Software build time', sw_ver.build_timestamp_utc.isoformat()),
            ('Hardware version',    f'{hw_ver.major}.{hw_ver.minor}'),
            ('Unique ID',           device_info.globally_unique_id.hex()),
        ])

    def clear(self):
        self._table.setRowCount(0)

    def _assign_many(self, kv: list):
        for k, v in kv:
            self._assign(k, v)

    def _assign(self, name: str, value):
        def make_item(value):
            data = QTableWidgetItem(value)
            data.setFlags(Qt.ItemIsEnabled | Qt.ItemIsSelectable)
            return data

        row = self._table.rowCount()
        self._table.setRowCount(row + 1)
        self._table.setVerticalHeaderItem(row, make_item(name))
        self._table.setItem(row, 0, make_item(value))

    # noinspection PyArgumentList
    def keyPressEvent(self, event: QKeyEvent):
        if event.matches(QKeySequence.Copy):
            selected_rows = [x.row() for x in self._table.selectionModel().selectedIndexes()]
            _logger.info('Copying the following rows to the clipboard: %r', selected_rows)

            if len(selected_rows) == 1:
                out_strings = [self._table.item(selected_rows[0], 0).text()]
            else:
                out_strings = []
                for row in selected_rows:
                    header = self._table.verticalHeaderItem(row).text()
                    data = self._table.item(row, 0).text()
                    out_strings.append(f'{header}\t{data}')

            if out_strings:
                QApplication.clipboard().setText(os.linesep.join(out_strings))
        else:
            super(LittleBobbyTablesWidget, self).keyPressEvent(event)

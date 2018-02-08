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
from dataclasses import dataclass
from logging import getLogger
from PyQt5.QtWidgets import QWidget, QTableView, QLabel, QVBoxLayout, QHBoxLayout
from PyQt5.QtCore import Qt, QAbstractTableModel, QModelIndex, QVariant
from PyQt5.QtGui import QFontMetrics, QFont
from view.widgets import WidgetBase
from view.utils import gui_test, make_button, get_monospace_font


_DEFAULT_UPDATE_PERIOD = 2


_logger = getLogger(__name__)


class LogWidget(WidgetBase):
    # noinspection PyUnresolvedReferences,PyArgumentList
    def __init__(self, parent: QWidget):
        super(LogWidget, self).__init__(parent)
        self.setAttribute(Qt.WA_DeleteOnClose)                  # This is required to stop background timers!

        self._clear_button = make_button(self, 'Clear', 'delete-document', on_clicked=self._do_clear)
        self._status_display = QLabel(self)

        self._model = _TableModel(self)
        self._table_view = _TableView(self, self._model)

        # View setup
        controls_layout = QHBoxLayout()
        controls_layout.addWidget(self._clear_button)
        controls_layout.addStretch(1)
        controls_layout.addWidget(self._status_display)

        layout = QVBoxLayout()
        layout.addLayout(controls_layout)
        layout.addWidget(self._table_view, 1)
        self.setLayout(layout)

        self.setMinimumSize(400, 350)

    def _do_clear(self):
        self._model.clear()

    def append_lines(self, text_lines: typing.Iterable[str]):
        self._model.append_lines(text_lines)


class _TableView(QTableView):
    def __init__(self, parent, model: QAbstractTableModel):
        super(_TableView, self).__init__(parent)
        self.setModel(model)

        self.horizontalHeader().setSectionResizeMode(self.horizontalHeader().ResizeToContents)
        self.horizontalHeader().setStretchLastSection(True)

        self.verticalHeader().setDefaultSectionSize(QFontMetrics(QFont()).height())
        self.verticalHeader().setSectionResizeMode(self.verticalHeader().Fixed)

        self.setSortingEnabled(False)
        self.setSelectionMode(self.ExtendedSelection)
        self.setSelectionBehavior(self.SelectItems)
        self.setShowGrid(False)


# noinspection PyMethodOverriding
class _TableModel(QAbstractTableModel):
    # TODO: Print device time as well! That would require modifications to the device model classes.
    COLUMNS = [
        'Local time',
        'Text',
    ]

    @dataclass(frozen=True)
    class Entry:
        local_time:     datetime.datetime
        text:           str

    def __init__(self, parent: QWidget):
        super(_TableModel, self).__init__(parent)

        self._rows: typing.List[self.Entry] = []

        self._monospace_font = get_monospace_font()

    def rowCount(self, _parent=None):
        return len(self._rows)

    def columnCount(self, _parent=None):
        return len(self.COLUMNS)

    def headerData(self, section: int, orientation: int, role=None):
        if role == Qt.DisplayRole:
            if orientation == Qt.Horizontal:
                return self.COLUMNS[section]

        if role == Qt.TextAlignmentRole:
            return Qt.AlignCenter

        return QVariant()

    def data(self, index: QModelIndex, role=None):
        entry = self._rows[index.row()]
        column = index.column()

        if role == Qt.DisplayRole:
            if column == 0:
                return entry.local_time.strftime('%H:%M:%S')

            if column == 1:
                return entry.text

            raise ValueError(f'Invalid column index: {column}')

        if role == Qt.TextAlignmentRole:
            return Qt.AlignLeft + Qt.AlignVCenter

        if role == Qt.FontRole:
            if column == 1:
                return self._monospace_font

        return QVariant()

    # noinspection PyUnresolvedReferences
    def append_lines(self, text_lines: typing.Iterable[str]):
        self.layoutAboutToBeChanged.emit()

        # TODO: Better timestamping
        for text in text_lines:
            self._rows.append(self.Entry(local_time=datetime.datetime.now(),
                                         text=text.rstrip()))

        # Note that we do not invoke dataChanged because we do not change any data once it is added to the log
        self.layoutChanged.emit()

    # noinspection PyUnresolvedReferences
    def clear(self):
        self.layoutAboutToBeChanged.emit()
        self._rows.clear()
        self.layoutChanged.emit()


# noinspection PyArgumentList
@gui_test
def _unittest_log_widget():
    import time
    from PyQt5.QtWidgets import QApplication, QMainWindow

    app = QApplication([])
    win = QMainWindow()

    lw = LogWidget(win)

    win.setCentralWidget(lw)
    win.show()

    def go_go_go():
        for _ in range(1000):
            time.sleep(0.001)
            app.processEvents()

    for it in range(5):
        go_go_go()
        lw.append_lines([f'This is line number {it + 1}', 'Piggyback'])

    go_go_go()

    win.close()

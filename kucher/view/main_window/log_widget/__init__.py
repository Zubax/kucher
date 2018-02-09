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
from PyQt5.QtGui import QFontMetrics, QFont, QPalette
from view.widgets import WidgetBase
from view.utils import gui_test, make_button, get_monospace_font
from view.device_model_representation import BasicDeviceInfo


_MAX_LOG_LINES_TO_KEEP = 10000


_logger = getLogger(__name__)


class LogWidget(WidgetBase):
    # noinspection PyUnresolvedReferences,PyArgumentList
    def __init__(self, parent: QWidget):
        super(LogWidget, self).__init__(parent)
        self.setAttribute(Qt.WA_DeleteOnClose)                  # This is required to stop background timers!

        self._clear_button = make_button(self, 'Clear', 'delete-document', on_clicked=self._do_clear)
        self._status_display = QLabel(self)

        self._model = _TableModel(self)
        self._model.layoutChanged.connect(self._on_model_changed)

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

    def append_lines(self, text_lines: typing.Iterable[str]):
        self._model.append_lines(text_lines)

    def on_device_connected(self, di: BasicDeviceInfo):
        swv = di.software_version
        hwv = di.hardware_version

        sw_str = f'{swv.major}.{swv.minor}.{swv.vcs_commit_id:08x}'
        if not swv.release_build:
            sw_str += '-debug'

        if swv.dirty_build:
            sw_str += '-dirty'

        hw_str = f'{hwv.major}.{hwv.minor}'

        self._model.append_special_event(f'Connected to {di.name!r} SW v{sw_str} HW v{hw_str} '
                                         f'#{di.globally_unique_id.hex()}')

    def on_device_disconnected(self, reason: str):
        self._model.append_special_event(f'Disconnected: {reason}')

    def _do_clear(self):
        self._model.clear()

    def _on_model_changed(self):
        self._status_display.setText(f'{self._model.rowCount()} rows')


class _TableView(QTableView):
    # noinspection PyUnresolvedReferences
    def __init__(self, parent, model: '_TableModel'):
        super(_TableView, self).__init__(parent)
        self.setModel(model)

        model.layoutChanged.connect(self._do_scroll)

        self.horizontalHeader().setSectionResizeMode(self.horizontalHeader().ResizeToContents)
        self.horizontalHeader().setStretchLastSection(True)

        self.verticalHeader().setDefaultSectionSize(model.font_height)
        self.verticalHeader().setSectionResizeMode(self.verticalHeader().Fixed)

        self.setSortingEnabled(False)
        self.setSelectionMode(self.ExtendedSelection)
        self.setSelectionBehavior(self.SelectItems)
        self.setShowGrid(False)

    def _do_scroll(self):
        try:
            relative_scroll_position = self.verticalScrollBar().value() / self.verticalScrollBar().maximum()
        except ZeroDivisionError:
            relative_scroll_position = 1.0

        if relative_scroll_position > 0.99:
            self.scrollToBottom()


def _model_modifier(method):
    def decorator(self, *args, **kwargs):
        return self._modifier_decorator(lambda: method(self, *args, **kwargs))

    return decorator


# noinspection PyMethodOverriding
class _TableModel(QAbstractTableModel):
    # TODO: Print device time as well! That would require modifications to the device model classes.
    COLUMNS = [
        'Local time',
        'Text',
    ]

    @dataclass
    class Entry:
        local_time:         datetime.datetime
        text:               str
        line_is_terminated: bool
        is_special_event:   bool = False

    def __init__(self, parent: QWidget):
        super(_TableModel, self).__init__(parent)

        self._rows: typing.List[self.Entry] = []

        self._monospace_font = get_monospace_font()

        self._special_event_font = get_monospace_font()
        self._special_event_font.setItalic(True)

    @property
    def font_height(self):
        return max(QFontMetrics(self._monospace_font).height(),
                   QFontMetrics(self._special_event_font).height(),
                   QFontMetrics(QFont()).height())

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
            if column == (len(self.COLUMNS) - 1):
                if entry.is_special_event:
                    return self._special_event_font
                else:
                    return self._monospace_font

        if role == Qt.BackgroundRole:
            if entry.is_special_event:
                return QPalette().color(QPalette.AlternateBase)

        return QVariant()

    # noinspection PyUnresolvedReferences
    @_model_modifier
    def append_lines(self, text_lines: typing.Iterable[str]):
        # TODO: Better timestamping
        local_time = datetime.datetime.now()

        for text in text_lines:
            this_line_is_terminated = text.endswith('\n')

            if self._rows[-1].line_is_terminated:
                self._rows.append(self.Entry(local_time=local_time,
                                             text=text.rstrip(),
                                             line_is_terminated=this_line_is_terminated))
            else:
                self._rows[-1].text += text.rstrip()
                self._rows[-1].line_is_terminated = this_line_is_terminated
                # Reporting that the last row has changed
                index = self.index(self.rowCount() - 1,
                                   self.columnCount() - 1)
                self.dataChanged.emit(index, index)

    # noinspection PyUnresolvedReferences
    @_model_modifier
    def append_special_event(self, text: str):
        entry = self.Entry(local_time=datetime.datetime.now(),
                           text=text,
                           line_is_terminated=True,
                           is_special_event=True)
        self._rows.append(entry)

    # noinspection PyUnresolvedReferences
    @_model_modifier
    def clear(self):
        self._rows.clear()

    # noinspection PyUnresolvedReferences
    def _modifier_decorator(self, target_function):
        self.layoutAboutToBeChanged.emit()
        out = target_function()
        self._rows = self._rows[-_MAX_LOG_LINES_TO_KEEP:]
        self.layoutChanged.emit()
        return out


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

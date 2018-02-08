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
import asyncio
import datetime
from logging import getLogger
from PyQt5.QtWidgets import QWidget, QTableView, QHeaderView, QSpinBox, QCheckBox, QLabel, QVBoxLayout, QHBoxLayout
from PyQt5.QtCore import QTimer, Qt, QAbstractTableModel, QModelIndex, QVariant
from ..widgets import WidgetBase
from ..utils import gui_test
from ..device_model_representation import TaskStatisticsView


_DEFAULT_UPDATE_PERIOD = 2


_logger = getLogger(__name__)


class TaskStatisticsWidget(WidgetBase):
    # noinspection PyUnresolvedReferences,PyArgumentList
    def __init__(self,
                 parent: QWidget,
                 async_update_delegate: typing.Callable[[], typing.Awaitable[TaskStatisticsView]]):
        super(TaskStatisticsWidget, self).__init__(parent)
        self.setAttribute(Qt.WA_DeleteOnClose)                  # This is required to stop background timers!

        self._model = _TableModel(self)

        self._async_update_delegate = async_update_delegate

        task: asyncio.Task = None

        def launch_update_task():
            nonlocal task
            if task is None or task.done():
                task = asyncio.get_event_loop().create_task(self._do_update())
            else:
                self._display_status('Still updating...')
                _logger.warning('Update task not launched because the previous one has not completed yet')

        self._update_timer = QTimer(self)
        self._update_timer.timeout.connect(launch_update_task)

        self._update_interval_selector = QSpinBox(self)
        self._update_interval_selector.setMinimum(1)
        self._update_interval_selector.setMaximum(10)
        self._update_interval_selector.setValue(_DEFAULT_UPDATE_PERIOD)
        self._update_interval_selector.valueChanged.connect(
            lambda: self._update_timer.setInterval(self._update_interval_selector.value() * 1000))

        def on_update_enabler_toggled():
            if self._update_enabler.isChecked():
                self._display_status()      # Clear status
                self._model.clear()         # Remove obsolete data from the model (this will trigger view update later)
                launch_update_task()        # Request update ASAP
                self._table_view.setEnabled(True)
                self._update_interval_selector.setEnabled(True)
                self._update_timer.start(self._update_interval_selector.value() * 1000)
            else:
                self._display_status('Disabled')
                self._table_view.setEnabled(False)
                self._update_interval_selector.setEnabled(True)
                self._update_timer.stop()

        self._update_enabler = QCheckBox('Update every', self)
        self._update_enabler.setChecked(True)
        self._update_enabler.stateChanged.connect(on_update_enabler_toggled)

        self._status_display = QLabel(self)
        self._status_display.setWordWrap(True)

        self._table_view = _TableView(self, self._model)

        # Launch
        on_update_enabler_toggled()

        # View setup
        controls_layout = QHBoxLayout()
        controls_layout.addWidget(self._update_enabler)
        controls_layout.addWidget(self._update_interval_selector)
        controls_layout.addWidget(QLabel('seconds', self))
        controls_layout.addStretch(1)
        controls_layout.addWidget(self._status_display)

        layout = QVBoxLayout()
        layout.addLayout(controls_layout)
        layout.addWidget(self._table_view, 1)
        self.setLayout(layout)

    def _display_status(self, text=None):
        self._status_display.setText(text)

    async def _do_update(self):
        # noinspection PyBroadException
        try:
            self._display_status('Updating...')
            data = await self._async_update_delegate()
            self._model.set_data(data)
        except Exception as ex:
            _logger.exception('Update failed')
            self._display_status(f'Error: {ex}')
        else:
            self._display_status('OK')


# noinspection PyArgumentList
@gui_test
def _unittest_task_statistics_widget():
    from PyQt5.QtWidgets import QApplication, QMainWindow

    app = QApplication([])
    win = QMainWindow()
    win.resize(800, 600)

    async def update_delegate() -> TaskStatisticsView:
        print('UPDATE')
        return _make_test_data()

    widget = TaskStatisticsWidget(win, update_delegate)

    win.setCentralWidget(widget)
    win.show()

    async def run_events():
        for _ in range(1000):
            app.processEvents()
            await asyncio.sleep(0.005)

        win.close()

    asyncio.get_event_loop().run_until_complete(run_events())


class _TableView(QTableView):
    def __init__(self, parent, model: QAbstractTableModel):
        super(_TableView, self).__init__(parent)
        self.setModel(model)

        self.horizontalHeader().setSectionResizeMode(self.horizontalHeader().ResizeToContents)
        self.horizontalHeader().setStretchLastSection(True)

        self.verticalHeader().setSectionResizeMode(self.verticalHeader().Stretch)

        self.setSortingEnabled(False)
        self.setSelectionMode(self.NoSelection)


# noinspection PyMethodOverriding
class _TableModel(QAbstractTableModel):
    COLUMNS = [
        'Started',
        'Stopped',
        'Last run time',
        'Total run time',
        'Invocations',
        'Failures',
        'Last exit code',
    ]

    def __init__(self, parent: QWidget):
        super(_TableModel, self).__init__(parent)

        self._data: TaskStatisticsView = TaskStatisticsView()

    def rowCount(self, _parent=None):
        return len(self._data.entries)

    def columnCount(self, _parent=None):
        return len(self.COLUMNS)

    def headerData(self, section: int, orientation: int, role=None):
        if role == Qt.DisplayRole:
            if orientation == Qt.Horizontal:
                return self.COLUMNS[section]
            else:
                task_enum = list(self._data.entries.keys())[section]
                return ' '.join(map(str.capitalize, str(task_enum).split('.')[1].split('_')))
        else:
            return QVariant()

    def data(self, index: QModelIndex, role=None):
        if role != Qt.DisplayRole:
            return QVariant()

        task_enums = list(self._data.entries.keys())
        task_id = task_enums[index.row()]
        entry = self._data.entries[task_id]
        column = index.column()

        def duration(secs):
            return datetime.timedelta(seconds=float(secs))

        if column == 0:
            return str(duration(entry.last_started_at)) if entry.last_started_at > 0 else 'Never'

        if column == 1:
            return str(duration(entry.last_stopped_at)) if entry.last_stopped_at > 0 else 'Never'

        if column == 2:
            if entry.last_stopped_at >= entry.last_started_at:
                return str(duration(entry.last_stopped_at - entry.last_started_at))
            else:
                return 'Running'

        if column == 3:
            return str(duration(entry.total_run_time))

        if column == 4:
            return str(entry.number_of_times_started)

        if column == 5:
            return str(entry.number_of_times_failed)

        if column == 6:
            return str(entry.last_exit_code)

        raise ValueError(f'Invalid column index: {column}')

    # noinspection PyUnresolvedReferences
    def set_data(self, view: TaskStatisticsView):
        # Note that we never update the list of columns, so the horizontal header doesn't ever need to be updated
        number_of_columns_changed = False

        number_of_rows_changed = len(view.entries) != self.rowCount()

        layout_change_required = number_of_rows_changed or number_of_columns_changed
        if layout_change_required:
            self.layoutAboutToBeChanged.emit()

        self._data = view

        if layout_change_required:
            self.layoutChanged.emit()

        if number_of_columns_changed:
            self.headerDataChanged.emit(Qt.Horizontal, 0, self.columnCount())

        if number_of_rows_changed:
            self.headerDataChanged.emit(Qt.Vertical, 0, self.rowCount())

        self.dataChanged.emit(self.index(0, 0),
                              self.index(self.rowCount() - 1,
                                         self.columnCount() - 1))

    def clear(self):
        self.set_data(TaskStatisticsView())


# noinspection PyArgumentList
@gui_test
def _unittest_task_statistics_table_model():
    import time
    from PyQt5.QtWidgets import QApplication, QMainWindow

    app = QApplication([])
    win = QMainWindow()
    win.resize(800, 600)

    model = _TableModel(win)

    view = QTableView(win)
    view.setModel(model)
    view.setSortingEnabled(True)

    hh = QHeaderView(Qt.Horizontal, view)
    hh.setModel(model)
    hh.setVisible(True)

    view.setHorizontalHeader(hh)

    win.setCentralWidget(view)
    win.show()

    def go_go_go():
        for _ in range(1000):
            time.sleep(0.001)
            app.processEvents()

    go_go_go()

    model.set_data(_make_test_data())

    for _ in range(5):
        go_go_go()

    win.close()


def _make_test_data():
    from decimal import Decimal

    sample = {
        'entries':   [
            {'last_exit_code':          194,
             'last_started_at':         Decimal('3.017389'),
             'last_stopped_at':         Decimal('3.017432'),
             'number_of_times_failed':  2,
             'number_of_times_started': 2,
             'task_id':                 'idle',
             'total_run_time':          Decimal('0.000062')},
            {'last_exit_code':          0,
             'last_started_at':         Decimal('3.017432'),
             'last_stopped_at':         Decimal('3.017389'),
             'number_of_times_failed':  0,
             'number_of_times_started': 3,
             'task_id':                 'fault',
             'total_run_time':          Decimal('27.093250')},
            {'last_exit_code':          0,
             'last_started_at':         Decimal('0.000000'),
             'last_stopped_at':         Decimal('0.000000'),
             'number_of_times_failed':  0,
             'number_of_times_started': 0,
             'task_id':                 'beeping',
             'total_run_time':          Decimal('0.000000')},
            {'last_exit_code':          0,
             'last_started_at':         Decimal('0.000000'),
             'last_stopped_at':         Decimal('0.000000'),
             'number_of_times_failed':  0,
             'number_of_times_started': 0,
             'task_id':                 'running',
             'total_run_time':          Decimal('0.000000')},
            {'last_exit_code':          2,
             'last_started_at':         Decimal('0.016381'),
             'last_stopped_at':         Decimal('2.025321'),
             'number_of_times_failed':  1,
             'number_of_times_started': 1,
             'task_id':                 'hardware_test',
             'total_run_time':          Decimal('2.008939')},
            {'last_exit_code':          0,
             'last_started_at':         Decimal('0.000000'),
             'last_stopped_at':         Decimal('0.000000'),
             'number_of_times_failed':  0,
             'number_of_times_started': 0,
             'task_id':                 'motor_identification',
             'total_run_time':          Decimal('0.000000')},
            {'last_exit_code':          0,
             'last_started_at':         Decimal('0.000000'),
             'last_stopped_at':         Decimal('0.000000'),
             'number_of_times_failed':  0,
             'number_of_times_started': 0,
             'task_id':                 'low_level_manipulation',
             'total_run_time':          Decimal('0.000000')}],
        'timestamp': Decimal('29.114152')
    }

    return TaskStatisticsView.populate(sample)

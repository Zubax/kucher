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
from PyQt5.QtWidgets import QWidget, QTableView
from PyQt5.QtCore import QTimer, Qt, QAbstractTableModel, QModelIndex, QVariant
from ..widgets import WidgetBase
from ..utils import gui_test
from ..device_model_representation import TaskStatisticsView


_DEFAULT_UPDATE_PERIOD = 2


_logger = getLogger(__name__)


class TaskStatisticsWidget(WidgetBase):
    def __init__(self,
                 parent: QWidget,
                 async_update_delegate: typing.Callable[[], typing.Awaitable[TaskStatisticsView]]):
        super(TaskStatisticsWidget, self).__init__(parent)
        self.setAttribute(Qt.WA_DeleteOnClose)                  # This is required to stop background timers!

        self._async_update_delegate = async_update_delegate

        task: asyncio.Task = None

        def launch_update_task():
            nonlocal task
            if task is None or task.done():
                task = asyncio.get_event_loop().create_task(self._do_update)
            else:
                _logger.warning('Update task not launched because the previous one has not completed yet')

        self._update_timer = QTimer(self)
        self._update_timer.timeout.connect(launch_update_task)
        self._update_timer.start(_DEFAULT_UPDATE_PERIOD * 1000)

        self._table_view = QTableView(self)

    async def _do_update(self):
        pass


# noinspection PyMethodOverriding
class _TableModel(QAbstractTableModel):
    ROWS = [
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
        return len(self.ROWS)

    def columnCount(self, _parent=None):
        return len(self._data.entries)

    def headerData(self, section: int, orientation: int, _role=None):
        if orientation == Qt.Horizontal:
            task_enum = list(self._data.entries.keys())[section]
            return str(task_enum).split('.')[1]
        else:
            return self.ROWS[section]

    def data(self, index: QModelIndex, role=None):
        if role != Qt.DisplayRole:
            return QVariant()

        task_enums = list(self._data.entries.keys())
        task_id = task_enums[index.column()]
        entry = self._data.entries[task_id]
        row = index.row()

        def duration(secs):
            return datetime.timedelta(seconds=float(secs))

        if row == 0:
            return str(duration(entry.last_started_at)) if entry.last_started_at > 0 else 'Never'

        if row == 1:
            return str(duration(entry.last_stopped_at)) if entry.last_stopped_at > 0 else 'Never'

        if row == 2:
            if entry.last_stopped_at >= entry.last_started_at:
                return str(duration(entry.last_stopped_at - entry.last_started_at))
            else:
                return 'Running'

        if row == 3:
            return str(duration(entry.total_run_time))

        if row == 4:
            return str(entry.number_of_times_started)

        if row == 5:
            return str(entry.number_of_times_failed)

        if row == 6:
            return str(entry.last_exit_code)

        raise ValueError(f'Invalid row index: {row}')

    def set_data(self, view: TaskStatisticsView):
        self._data = view
        self.layoutChanged.emit()
        self.dataChanged.emit(self.index(0, 0),
                              self.index(self.rowCount() - 1,
                                         self.columnCount() - 1))


@gui_test
def _unittest_task_statistics_table_model():
    import time
    from decimal import Decimal
    from PyQt5.QtWidgets import QApplication, QMainWindow, QGroupBox, QGridLayout, QLabel, QSizePolicy

    app = QApplication([])
    win = QMainWindow()
    win.resize(800, 600)

    model = _TableModel(win)
    view = QTableView(win)
    view.setModel(model)

    win.setCentralWidget(view)
    win.show()

    def go_go_go():
        for _ in range(1000):
            time.sleep(0.005)
            app.processEvents()

    go_go_go()

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
             'task_id':                 'manual_control',
             'total_run_time':          Decimal('0.000000')}],
        'timestamp': Decimal('29.114152')
    }

    tsv = TaskStatisticsView.populate(sample)
    model.set_data(tsv)

    go_go_go()
    win.close()

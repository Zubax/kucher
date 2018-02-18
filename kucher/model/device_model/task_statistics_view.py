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
import dataclasses
from decimal import Decimal
from .general_status_view import TaskID, TASK_ID_MAPPING

__all__ = ['TaskStatisticsView']

_struct_view = dataclasses.dataclass(frozen=True)


@_struct_view
class SingleTaskStatistics:
    last_started_at:            Decimal
    last_stopped_at:            Decimal
    total_run_time:             Decimal
    number_of_times_started:    int
    number_of_times_failed:     int
    last_exit_code:             int

    @staticmethod
    def populate(msg: typing.Mapping) -> 'SingleTaskStatistics':
        return SingleTaskStatistics(
            last_started_at=msg['last_started_at'],
            last_stopped_at=msg['last_stopped_at'],
            total_run_time=msg['total_run_time'],
            number_of_times_started=msg['number_of_times_started'],
            number_of_times_failed=msg['number_of_times_failed'],
            last_exit_code=msg['last_exit_code'],
        )


@_struct_view
class TaskStatisticsView:
    timestamp:      Decimal = Decimal()
    entries:        typing.Dict[TaskID, SingleTaskStatistics] = dataclasses.field(default_factory=lambda: {})

    @staticmethod
    def populate(msg: typing.Mapping) -> 'TaskStatisticsView':
        return TaskStatisticsView(
            timestamp=msg['timestamp'],
            entries={
                TASK_ID_MAPPING[item['task_id']][0]: SingleTaskStatistics.populate(item) for item in msg['entries']
            },
        )


def _unittest_task_statistics_view():
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

    tsv = TaskStatisticsView.populate(sample)

    assert tsv.entries[TaskID.IDLE].last_exit_code == 194
    assert tsv.entries[TaskID.FAULT].last_exit_code == 0
    assert tsv.entries[TaskID.HARDWARE_TEST].last_exit_code == 2
    assert tsv.entries[TaskID.HARDWARE_TEST].number_of_times_started == 1
    assert tsv.entries[TaskID.HARDWARE_TEST].number_of_times_failed == 1
    assert tsv.entries[TaskID.HARDWARE_TEST].last_started_at == Decimal('0.016381')
    assert tsv.timestamp == Decimal('29.114152')

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

import enum
import struct
import decimal


Timestamp = decimal.Decimal         # Accurate timestamp in seconds


class TaskID(enum.IntEnum):
    """
    Task ID values defined by the communication protocol.
    """
    IDLE                    = 0
    FAULT                   = 1
    BEEPING                 = 2
    RUNNING                 = 3
    HARDWARE_TEST           = 4
    MOTOR_IDENTIFICATION    = 5
    MANUAL_CONTROL          = 6


class TaskStatusReportBase:
    @staticmethod
    def decode(task_id: TaskID, data: bytes):
        """
        Decodes a task status report struct from raw binary stream.
        """
        pass


class FaultStatusReport(TaskStatusReportBase):
    def __init__(self):
        self.failed_task_id = TaskID(0)
        self.failed_task_result = 0


class RunningStatusReport(TaskStatusReportBase):
    def __init__(self):
        self.stall_count                    = 0
        self.estimated_active_power         = 0.0
        self.demand_factor                  = 0.0
        self.electrical_angular_velocity    = 0.0
        self.spinup_in_progress             = False


class HardwareTestStatusReport(TaskStatusReportBase):
    def __init__(self):
        self.progress = 0.0


class MotorIdentificationStatusReport(TaskStatusReportBase):
    def __init__(self):
        self.progress = 0.0


class ManualControlStatusReport(TaskStatusReportBase):
    def __init__(self):
        self.sub_task_id = 0


_TASK_ID_STATUS_REPORT_MAP = {
    TaskID.IDLE:                    None,
    TaskID.FAULT:                   FaultStatusReport,
    TaskID.BEEPING:                 None,
    TaskID.RUNNING:                 RunningStatusReport,
    TaskID.HARDWARE_TEST:           HardwareTestStatusReport,
    TaskID.MOTOR_IDENTIFICATION:    MotorIdentificationStatusReport,
    TaskID.MANUAL_CONTROL:          ManualControlStatusReport,
}


class TimestampedTaskResult:
    def __init__(self):
        self.completed_at = Timestamp()
        self.exit_code = 0

    @staticmethod
    def decode(packed: bytes):
        try:
            number, = struct.unpack('<Q', packed)
        except struct.error:
            raise ValueError from struct.error

        out = TimestampedTaskResult()
        out.exit_code = (number >> 56) & 0xFF
        out.completed_at = Timestamp(number & (2**56 - 1)) * Timestamp('1e-6')
        return out


def _unittest_timestamped_task_result():
    from pytest import raises

    with raises(ValueError):
        TimestampedTaskResult.decode(bytes())

    with raises(ValueError):
        TimestampedTaskResult.decode(b'1234567')

    with raises(ValueError):
        TimestampedTaskResult.decode(b'123456789')

    ttr = TimestampedTaskResult.decode(bytes([0] * 8))
    assert ttr.completed_at == 0
    assert ttr.exit_code == 0

    ttr = TimestampedTaskResult.decode(bytes([0xDE, 0xAD, 0xBE, 0xEF, 0xA5, 0xCA, 0xFE, 123]))
    micros = 0xFE_CA_A5_EF_BE_AD_DE
    assert ttr.completed_at == Timestamp(micros) * Timestamp('1e-6')
    assert ttr.exit_code == 123

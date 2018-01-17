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
import math
import popcop
import typing
import struct
from .tasks import TaskID, Timestamp, TimestampedTaskResult, TaskStatusReportBase


class StatusFlags(enum.IntFlag):
    """
    Device status flags, as defined by the communication protocol.
    Status flags are carried in a 64-bit unsigned integer field.
    """
    # Alert flags are allocated at the bottom (from bit 0 upwards)
    DC_UNDERVOLTAGE                         = 1 << 0
    DC_OVERVOLTAGE                          = 1 << 1
    DC_UNDERCURRENT                         = 1 << 2
    DC_OVERCURRENT                          = 1 << 3

    CPU_COLD                                = 1 << 4
    CPU_OVERHEATING                         = 1 << 5
    VSI_COLD                                = 1 << 6
    VSI_OVERHEATING                         = 1 << 7
    MOTOR_COLD                              = 1 << 8
    MOTOR_OVERHEATING                       = 1 << 9

    HARDWARE_LVPS_MALFUNCTION               = 1 << 10
    HARDWARE_FAULT                          = 1 << 11
    HARDWARE_OVERLOAD                       = 1 << 12

    PHASE_CURRENT_MEASUREMENT_MALFUNCTION   = 1 << 13

    # Non-error flags are allocated at the top (from bit 63 downwards)
    UAVCAN_NODE_UP                          = 1 << 56
    CAN_DATA_LINK_UP                        = 1 << 57

    USB_CONNECTED                           = 1 << 58
    USB_POWER_SUPPLIED                      = 1 << 59

    RCPWM_SIGNAL_DETECTED                   = 1 << 60

    PHASE_CURRENT_AGC_HIGH_GAIN_SELECTED    = 1 << 61
    VSI_MODULATING                          = 1 << 62
    VSI_ENABLED                             = 1 << 63


class DeviceCapabilityFlags(enum.IntFlag):
    """
    Device capability flags, as defined by the communication protocol.
    Capability flags are carried in a 64-bit unsigned integer field.
    """
    DOUBLY_REDUNDANT_CAN_BUS                = 1 << 0
    BATTERY_ELIMINATOR_CIRCUIT              = 1 << 1


class MessageBase:
    # noinspection PyMethodMayBeStatic
    def encode(self) -> bytes:
        """Encodes the message instance for transmission over the wire"""
        raise TypeError('This message type cannot be encoded')


class GeneralStatusMessage(MessageBase):
    FRAME_TYPE_CODE = 0

    def __init__(self):
        self.current_task_id = TaskID(0)
        self.timestamp = Timestamp()

        # noinspection PyTypeChecker
        self.timestamped_task_results: typing.Dict[TaskID, TimestampedTaskResult] = {
            tid: TimestampedTaskResult() for tid in TaskID
        }

        self.status_flags = StatusFlags(0)

        self.cpu_temperature = 0.0
        self.vsi_temperature = 0.0
        self.motor_temperature = None   # Optional

        self.dc_voltage = 0.0
        self.dc_current = 0.0

        self.hardware_lvps_malfunction_event_count  = 0
        self.hardware_overload_event_count          = 0
        self.hardware_fault_event_count             = 0

        self.task_specific_status_report = TaskStatusReportBase()

    @staticmethod
    def decode(data: bytes):
        out = GeneralStatusMessage()

        current_task_id_with_timestamp, = struct.unpack('<Q', data[:8])
        out.current_task_id = TaskID((current_task_id_with_timestamp >> 56) & 0xFF)
        out.timestamp = Timestamp(current_task_id_with_timestamp & (2**56 - 1)) * Timestamp('1e-6')

        offset = 8
        # noinspection PyTypeChecker
        for tid in TaskID:
            block = data[offset:offset + TimestampedTaskResult.ENCODED_SIZE]
            out.timestamped_task_results[tid] = TimestampedTaskResult.decode(block)
            offset += TimestampedTaskResult.ENCODED_SIZE

        status_flags, \
            out.cpu_temperature, \
            out.vsi_temperature, \
            out.motor_temperature, \
            out.dc_voltage, \
            out.dc_current, \
            out.hardware_lvps_malfunction_event_count, \
            out.hardware_overload_event_count, \
            out.hardware_fault_event_count = struct.unpack('< Q fff ff LLL', data[offset:offset+40])
        offset += 40

        out.status_flags = StatusFlags(status_flags)

        # This field is not reported unless the motor temperature feedback is configured
        if math.isnan(out.motor_temperature):
            out.motor_temperature = None

        out.task_specific_status_report = TaskStatusReportBase.decode(out.current_task_id, data[offset:])

        return out


def _unittest_general_status_message_decode():
    data = bytearray([0] * 176)

    # Current task ID and timestamp
    data[0:  8] = bytes([0xDE, 0xAD, 0xBE, 0xEF, 0xA5, 0xCA, 0xFE, 5])

    # Task results
    data[8: 16] = bytes([0xDE, 0xAD, 0xBE, 0xEF, 0x10, 0xCA, 0x00, 10])
    data[16:24] = bytes([0xDE, 0xAD, 0xBE, 0xEF, 0x11, 0xCA, 0x01, 11])
    data[24:32] = bytes([0xDE, 0xAD, 0xBE, 0xEF, 0x12, 0xCA, 0x02, 12])
    data[32:40] = bytes([0xDE, 0xAD, 0xBE, 0xEF, 0x13, 0xCA, 0x03, 13])
    data[40:48] = bytes([0xDE, 0xAD, 0xBE, 0xEF, 0x14, 0xCA, 0x04, 14])
    data[48:56] = bytes([0xDE, 0xAD, 0xBE, 0xEF, 0x15, 0xCA, 0x05, 15])
    data[56:64] = bytes([0xDE, 0xAD, 0xBE, 0xEF, 0x16, 0xCA, 0x06, 16])
    data[64:72] = bytes([0xDE, 0xAD, 0xBE, 0xEF, 0x17, 0xCA, 0x07, 17])

    out = GeneralStatusMessage.decode(bytes(data))

    assert out.current_task_id == 5
    assert out.timestamp == Timestamp(0xFE_CA_A5_EF_BE_AD_DE) * Timestamp('1e-6')

    assert out.timestamped_task_results[TaskID(0)].completed_at == Timestamp(0x00_CA_10_EF_BE_AD_DE) * Timestamp('1e-6')
    assert out.timestamped_task_results[TaskID(1)].completed_at == Timestamp(0x01_CA_11_EF_BE_AD_DE) * Timestamp('1e-6')
    assert out.timestamped_task_results[TaskID(2)].completed_at == Timestamp(0x02_CA_12_EF_BE_AD_DE) * Timestamp('1e-6')
    assert out.timestamped_task_results[TaskID(3)].completed_at == Timestamp(0x03_CA_13_EF_BE_AD_DE) * Timestamp('1e-6')
    assert out.timestamped_task_results[TaskID(4)].completed_at == Timestamp(0x04_CA_14_EF_BE_AD_DE) * Timestamp('1e-6')
    assert out.timestamped_task_results[TaskID(5)].completed_at == Timestamp(0x05_CA_15_EF_BE_AD_DE) * Timestamp('1e-6')
    assert out.timestamped_task_results[TaskID(6)].completed_at == Timestamp(0x06_CA_16_EF_BE_AD_DE) * Timestamp('1e-6')

    # noinspection PyTypeChecker
    for tid in TaskID:
        assert out.timestamped_task_results[tid].exit_code == int(tid) + 10

    # TODO: add tests


class DeviceCharacteristicsMessage(MessageBase):
    FRAME_TYPE_CODE = 1


class SetpointCommandMessage(MessageBase):
    FRAME_TYPE_CODE = 2


def decode(frame: popcop.transport.ReceivedFrame) -> typing.Optional[MessageBase]:
    pass


def encode(message: MessageBase) -> typing.Tuple:
    pass

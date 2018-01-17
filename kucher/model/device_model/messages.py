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
import popcop
import typing
import decimal
import unittest
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
    pass


class GeneralStatusMessage(MessageBase):
    FRAME_TYPE_CODE = 0

    def __init__(self):
        self.current_task_id = TaskID(0)
        self.timestamp = Timestamp()

        # noinspection PyTypeChecker
        self.timestamped_task_results = {
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
        pass


class DeviceCharacteristicsMessage(MessageBase):
    FRAME_TYPE_CODE = 1


class SetpointCommandMessage(MessageBase):
    FRAME_TYPE_CODE = 2


def decode(frame: popcop.transport.ReceivedFrame) -> typing.Optional[MessageBase]:
    pass


def encode(message: MessageBase) -> typing.Tuple:
    pass

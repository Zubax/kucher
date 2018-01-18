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
import decimal
import construct as con

# Convenient type aliases - we only use little-endian byte order!
U8  = con.Int8ul
U16 = con.Int16ul
U32 = con.Int32ul
U56 = con.BytesInteger(7, signed=False, swapped=True)
U64 = con.Int64ul
F32 = con.Float32l


# noinspection PyClassHasNoInit
class OptionalFloatAdapter(con.Adapter):
    """
    Floats can be optional; if no value is provided, they may be set to NaN.
    This adapter replaces NaN with None and vice versa.
    """
    def _encode(self, obj, context):
        return float('nan') if obj is None else float(obj)

    def _decode(self, obj, context):
        return None if math.isnan(obj) else float(obj)


# noinspection PyClassHasNoInit
class TimeAdapter(con.Adapter):
    """
    Converts time representation between integral number of microseconds and a Decimal number of seconds.
    """
    MULTIPLIER = decimal.Decimal('1e6')

    def _encode(self, obj, context):
        return int(obj * self.MULTIPLIER)

    def _decode(self, obj, context):
        return decimal.Decimal(obj) / self.MULTIPLIER


StatusFlagsFormat = con.FlagsEnum(
    U64,

    # Alert flags are allocated at the bottom (from bit 0 upwards)
    dc_undervoltage=1 << 0,
    dc_overvoltage=1 << 1,
    dc_undercurrent=1 << 2,
    dc_overcurrent=1 << 3,

    cpu_cold=1 << 4,
    cpu_overheating=1 << 5,
    vsi_cold=1 << 6,
    vsi_overheating=1 << 7,
    motor_cold=1 << 8,
    motor_overheating=1 << 9,

    hardware_lvps_malfunction=1 << 10,
    hardware_fault=1 << 11,
    hardware_overload=1 << 12,

    phase_current_measurement_malfunction=1 << 13,

    # Non-error flags are allocated at the top (from bit 63 downwards)
    uavcan_node_up=1 << 56,
    can_data_link_up=1 << 57,

    usb_connected=1 << 58,
    usb_power_supplied=1 << 59,

    rcpwm_signal_detected=1 << 60,

    phase_current_agc_high_gain_selected=1 << 61,
    vsi_modulating=1 << 62,
    vsi_enabled=1 << 63,
)


TaskIDFormat = con.Enum(
    U8,
    idle=0,
    fault=1,
    running=2,
    beeping=3,
    hardware_test=4,
    motor_identification=5,
    manual_control=6,
)


TaskSpecificStatusReportFormat = con.Switch(con.this.current_task_id, {
    'fault': con.Struct(
        failed_task_id=TaskIDFormat,
        failed_task_result=U8,
    ),
    'running': con.Struct(
        stall_count=U32,
        estimated_active_power=F32,
        demand_factor=F32,
        electrical_angular_velocity=F32,
        spinup_in_progress=con.Flag,
    ),
    'hardware_test': con.Struct(
        progress=F32,
    ),
    'motor_identification': con.Struct(
        progress=F32,
    ),
    'manual_control': con.Struct(
        sub_task_id=U8,
    ),
}, default=con.Pass)


GeneralStatusMessageFormatV1 = con.Struct(
    timestamp=TimeAdapter(U56),
    current_task_id=TaskIDFormat,
    timestamped_task_results=con.Array(8, con.Struct(
        completed_at=TimeAdapter(U56),
        exit_code=U8,
    )),
    status_flags=StatusFlagsFormat,
    temperature=con.Struct(
        cpu=F32,
        vsi=F32,
        motor=OptionalFloatAdapter(F32),
    ),
    dc=con.Struct(
        voltage=F32,
        current=F32,
    ),
    hardware_flag_edge_counters=con.Struct(
        lvps_malfunction=U32,
        overload=U32,
        fault=U32,
    ),
    task_specific_status_report=TaskSpecificStatusReportFormat,
)


def _unittest_general_status_message_v1():
    import binascii
    import pprint
    sample_idle = binascii.unhexlify('407e190900000000000000000000000000000000000000000b613e00000000000000000000000000'
                                     '19cc350000000000000000000000000000000000000000000000000000000000000000000000002c'
                                     '798d9943ebf095430000000036486e4100000000000000000000000000000000')
    container = GeneralStatusMessageFormatV1.parse(sample_idle)
    pprint.pprint(container)
    assert container.current_task_id == 'idle'
    assert container.task_specific_status_report is None
    assert container['status_flags']['phase_current_agc_high_gain_selected']
    assert not container.status_flags.can_data_link_up
    assert sample_idle == GeneralStatusMessageFormatV1.build(container)


class MessageType(enum.Enum):
    GENERAL_STATUS = enum.auto()
    DEVICE_CAPABILITIES = enum.auto()
    SETPOINT = enum.auto()


class Codec:
    """
    Use this class to encode and decode messages.
    It uses software version numbers to determine which message formats to use.
    """
    def __init__(self):
        self._software_version: typing.Tuple[int, int] = (0, 0)

    @property
    def software_version(self) -> typing.Tuple[int, int]:
        return self._software_version

    @software_version.setter
    def software_version(self, major_minor: typing.Tuple[int, int]):
        if len(major_minor) != 2:
            raise TypeError('Expected an iterable of size 2')

        mj, mn = map(int, major_minor)
        self._software_version = mj, mn

    def decode(self, frame: popcop.transport.ReceivedFrame) -> typing.Tuple[MessageType, con.Container]:
        pass

    def encode(self, message_type: MessageType, fields: typing.MappingView) -> typing.Tuple[int, bytes]:
        pass

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


DeviceCapabilityFlagsFormat = con.FlagsEnum(
    U64,

    doubly_redundant_can_bus=1 << 0,
    battery_eliminator_circuit=1 << 1,
)


MathRangeFormat = con.Struct(
    min=F32,
    max=F32,
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


ControlModeFormat = con.Enum(
    U8,

    ratiometric_current=0,
    ratiometric_angular_velocity=0,
    ratiometric_voltage=0,
    current=0,
    mechanical_rpm=0,
    voltage=0,
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
    _reserved=con.Padding(4),
    pwm_state=con.Struct(
        period=F32,
        dead_time=F32,
        upper_limit=F32,
    ),
    hardware_flag_edge_counters=con.Struct(
        lvps_malfunction=U32,
        overload=U32,
        fault=U32,
    ),
    task_specific_status_report=TaskSpecificStatusReportFormat,
)


def _unittest_general_status_message_v1():
    from binascii import unhexlify
    from pprint import pprint
    sample_idle = unhexlify('01b9e30000000000000000000000000000000000000000005b623e0000000000000000000000000093cd350000'
                            '000000000000000000000000000000000000000000000000000000000000000000002f78c99a439af796430000'
                            '000044866e410000000000000000ae7db23795bfd633f2eb613f000000000000000000000000')
    container = GeneralStatusMessageFormatV1.parse(sample_idle)
    pprint(container)
    assert container.current_task_id == 'idle'
    assert container.task_specific_status_report is None
    assert container['status_flags']['phase_current_agc_high_gain_selected']
    assert container.status_flags.can_data_link_up
    assert sample_idle == GeneralStatusMessageFormatV1.build(container)


DeviceCharacteristicsMessageFormatV1 = con.Struct(
    capability_flags=DeviceCapabilityFlagsFormat,
    board_parameters=con.Struct(
        vsi_resistance_per_phase=con.Array(3, con.Struct(
            high=F32,
            low=F32,
        )),
        vsi_gate_ton_toff_imbalance=F32,
        phase_current_measurement_error_variance=F32,
        limits=con.Struct(
            measurement_range=con.Struct(
                vsi_dc_voltage=MathRangeFormat,
            ),
            safe_operating_area=con.Struct(
                vsi_dc_voltage=MathRangeFormat,
                vsi_dc_current=MathRangeFormat,
                vsi_phase_current=MathRangeFormat,
                cpu_temperature=MathRangeFormat,
                vsi_temperature=MathRangeFormat,
            ),
            phase_current_transducers_zero_bias_limit=con.Struct(
                low_gain=F32,
                high_gain=F32,
            ),
        ),
    ),
)


def _unittest_device_characteristics_message_v1():
    from binascii import unhexlify
    from pprint import pprint
    from pytest import approx
    sample = unhexlify('03000000000000006f12833b4260e53b6f12833b4260e53b6f12833b6f12833b83fa3cb20000803f00008040f62878'
                       '420000304100004c420000c8c10000c8410000f0c10000f04166266c433393b143662669433313b343000000400000'
                       '003f')
    container = DeviceCharacteristicsMessageFormatV1.parse(sample)
    pprint(container)
    assert container.board_parameters.vsi_resistance_per_phase[0].low == approx(7e-3)
    assert container.board_parameters.vsi_resistance_per_phase[2].high == approx(4e-3)
    assert container.board_parameters.vsi_gate_ton_toff_imbalance == approx(-11e-9)
    assert container.board_parameters.limits.phase_current_transducers_zero_bias_limit.low_gain == approx(2)
    assert sample == DeviceCharacteristicsMessageFormatV1.build(container)


SetpointMessageFormatV1 = con.Struct(
    value=F32,
    mode=ControlModeFormat,
    _reserved=con.Padding(3),
)


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
        self._version: typing.Tuple[int, int] = (0, 0)

    @property
    def version(self) -> typing.Tuple[int, int]:
        return self._version

    @version.setter
    def version(self, major_minor: typing.Tuple[int, int]):
        if len(major_minor) != 2:
            raise TypeError('Expected an iterable of size 2')

        mj, mn = map(int, major_minor)
        self._version = mj, mn

    def decode(self, frame: popcop.transport.ReceivedFrame) -> typing.Tuple[MessageType, con.Container]:
        pass

    def encode(self, message_type: MessageType, fields: typing.MappingView) -> typing.Tuple[int, bytes]:
        pass

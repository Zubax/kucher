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
from .exceptions import CommunicatorException

# Convenient type aliases - we only use little-endian byte order!
U8  = con.Int8ul
U16 = con.Int16ul
U32 = con.Int32ul
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
    beeping=2,
    running=3,
    hardware_test=4,
    motor_identification=5,
    low_level_manipulation=6,
)


ControlModeFormat = con.Enum(
    U8,

    ratiometric_current=0,
    ratiometric_angular_velocity=1,
    ratiometric_voltage=2,
    current=3,
    mechanical_rpm=4,
    voltage=5,
)


MotorIdentificationModeFormat = con.Enum(
    U8,

    r_l=0,
    phi=1,
    r_l_phi=2,
)


LowLevelManipulationModeFormat = con.Enum(
    U8,

    calibration=0,
    phase_manipulation=1,
    scalar_control=2,
)


# Observe that by default we use padding of one byte rather than an empty sequence.
# This is because the firmware reports empty task-specific structures as a zeroed-out byte sequence of length one byte.
# The firmware does that because in the world of C/C++ a sizeof() cannot be zero.
# noinspection PyUnresolvedReferences
TaskSpecificStatusReportFormat = con.Switch(con.this.current_task_id, {
    'fault': con.Struct(
        'failed_task_id'                / TaskIDFormat,
        'failed_task_exit_code'         / U8,
    ),
    'running': con.Struct(
        'stall_count'                   / U32,
        'estimated_active_power'        / F32,
        'demand_factor'                 / F32,
        # Velocity
        'electrical_angular_velocity'   / F32,
        'mechanical_angular_velocity'   / F32,
        # Rotating system parameters
        'u_dq'                          / con.Array(2, F32),
        'i_dq'                          / con.Array(2, F32),
        # State flags
        'spinup_in_progress'            / con.Flag,
        'rotation_reversed'             / con.Flag,
        'controller_saturated'          / con.Flag,
        # Final padding to 4 bytes
        con.Padding(1),
    ),
    'hardware_test': con.Struct(
        'progress'                      / F32,
    ),
    'motor_identification': con.Struct(
        'progress'                      / F32,
    ),
    'low_level_manipulation': con.Struct(
        'sub_task_id'                   / U8,
    ),
}, default=con.Padding(1))


# noinspection PyUnresolvedReferences
GeneralStatusMessageFormatV1 = con.Struct(
    'timestamp' / TimeAdapter(U64),
    'status_flags' / StatusFlagsFormat,
    'current_task_id' / TaskIDFormat,
    con.Padding(3),
    'temperature' / con.Struct(
        'cpu'   / F32,
        'vsi'   / F32,
        'motor' / OptionalFloatAdapter(F32),
    ),
    'dc' / con.Struct(
        'voltage' / F32,
        'current' / F32,
    ),
    'pwm' / con.Struct(
        'period'        / F32,
        'dead_time'     / F32,
        'upper_limit'   / F32,
    ),
    'hardware_flag_edge_counters' / con.Struct(
        'lvps_malfunction'  / U32,
        'overload'          / U32,
        'fault'             / U32,
    ),
    'task_specific_status_report' / TaskSpecificStatusReportFormat,
    con.Terminated      # Every message format should be terminated! This enables format mismatch detection.
)


def _unittest_general_status_message_v1():
    from binascii import unhexlify
    from pprint import pprint
    sample_idle = unhexlify('b0ec8b2300000000000000000000002c0000000063be9a4365d89643000000002a59ae4100000000ae7db23795'
                            'bfd633f2eb613f00000000000000000000000000')
    container = GeneralStatusMessageFormatV1.parse(sample_idle)
    pprint(container)
    assert container.current_task_id == 'idle'
    assert container.task_specific_status_report is None
    assert container['status_flags']['phase_current_agc_high_gain_selected']
    assert not container.status_flags.can_data_link_up
    assert sample_idle == GeneralStatusMessageFormatV1.build(container)


# noinspection PyUnresolvedReferences
DeviceCharacteristicsMessageFormatV1 = con.Struct(
    'capability_flags'  / DeviceCapabilityFlagsFormat,
    'vsi_model' / con.Struct(
        'resistance_per_phase' / con.Array(3, ('high' / F32 + 'low' / F32)),
        'gate_ton_toff_imbalance'                   / F32,
        'phase_current_measurement_error_variance'  / F32,
    ),
    'limits' / con.Struct(
        'measurement_range' / con.Struct(
            'vsi_dc_voltage'        / MathRangeFormat,
        ),
        'safe_operating_area' / con.Struct(
            'vsi_dc_voltage'        / MathRangeFormat,
            'vsi_dc_current'        / MathRangeFormat,
            'vsi_phase_current'     / MathRangeFormat,
            'cpu_temperature'       / MathRangeFormat,
            'vsi_temperature'       / MathRangeFormat,
        ),
        'phase_current_zero_bias_limit' / ('low_gain' / F32 + 'high_gain' / F32),
    ),
    con.Terminated      # Every message format should be terminated! This enables format mismatch detection.
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
    assert container.vsi_model.resistance_per_phase[0].low == approx(7e-3)
    assert container.vsi_model.resistance_per_phase[2].high == approx(4e-3)
    assert container.vsi_model.gate_ton_toff_imbalance == approx(-11e-9)
    assert container.limits.phase_current_zero_bias_limit.low_gain == approx(2)
    assert sample == DeviceCharacteristicsMessageFormatV1.build(container)


# noinspection PyUnresolvedReferences
CommandMessageFormatV1 = con.Struct(
    'task_id'                   / TaskIDFormat,
    con.Padding(3),
    'task_specific_command'     / con.Switch(con.this.task_id, {
        'idle': con.Struct(),
        'fault': con.Struct(
            'magic'             / U32,
        ),
        'beeping': con.Struct(
            'frequency'         / F32,
            'duration'          / F32,
        ),
        'running': con.Struct(
            'mode'              / ControlModeFormat,
            con.Padding(3),
            'value'             / F32,
        ),
        'hardware_test': con.Struct(),
        'motor_identification': con.Struct(
            'mode'              / MotorIdentificationModeFormat,
        ),
        'low_level_manipulation': con.Struct(
            'mode'              / LowLevelManipulationModeFormat,
            con.Padding(3),
            'parameters'        / con.Array(4, F32),
        ),
    }),
    con.Terminated      # This is only meaningful for parsing, but we add it anyway for consistency.
)


# noinspection PyUnresolvedReferences
TaskStatisticsEntryFormatV1 = con.Struct(
    'last_started_at'           / TimeAdapter(U64),
    'last_stopped_at'           / TimeAdapter(U64),
    'total_run_time'            / TimeAdapter(U64),
    'number_of_times_started'   / U64,
    'number_of_times_failed'    / U64,
    con.Padding(6),
    'last_exit_code'            / U8,
    'task_id'                   / TaskIDFormat,
)


# noinspection PyUnresolvedReferences
TaskStatisticsMessageFormatV1 = con.Struct(
    'timestamp' / TimeAdapter(U64),
    'entries' / TaskStatisticsEntryFormatV1[7:8],
    con.Terminated      # Every message format should be terminated! This enables format mismatch detection.
)


def _unittest_task_statistics_message_v1():
    from binascii import unhexlify
    from pprint import pprint
    # One task per line below
    sample = unhexlify(
        '283fbc0100000000'
        'ad0a2e0000000000d80a2e00000000003e0000000000000002000000000000000200000000000000000000000000c200'
        'd80a2e0000000000ad0a2e000000000002699d0100000000030000000000000000000000000000000000000000000001'
        '000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000002'
        '000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000003'
        'fd3f00000000000069e71e00000000006ba71e0000000000010000000000000001000000000000000000000000000204'
        '000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000005'
        '000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000006')
    container = TaskStatisticsMessageFormatV1.parse(sample)
    pprint(container)


class MessageType(enum.Enum):
    GENERAL_STATUS = enum.auto()
    DEVICE_CHARACTERISTICS = enum.auto()
    COMMAND = enum.auto()
    TASK_STATISTICS = enum.auto()


class MessagingException(CommunicatorException):
    pass


class UnsupportedVersionException(MessagingException):
    """
    This exception is thrown when the Codec class detects that it doesn't know how to communicate with the
    given firmware version.
    """
    pass


class UnknownMessageException(MessagingException):
    """
    This exception is thrown when the Codec class is asked to encode or decode a message it doesn't know about.
    """
    pass


class InvalidFieldsException(MessagingException):
    """
    This exception is thrown when the Codec class is asked to encode fields that don't fit the message type.
    """
    pass


class InvalidPayloadException(MessagingException):
    """
    This exception is thrown when the Codec class is asked to decode an incorrect message.
    """
    pass


class Message:
    """
    Simple container type for messages. Contains type information and the message fields.
    Note that the type is read-only, whereas the fields can be changed.
    """
    def __init__(self,
                 message_type: MessageType,
                 fields: typing.Optional[typing.Mapping]=None,
                 timestamp: typing.Optional[float]=None):
        if not isinstance(message_type, MessageType):
            raise TypeError('Expected MessageType not %r' % message_type)

        self._type = message_type
        self._fields = con.Container(fields or {})
        self._timestamp = float(timestamp or 0)

    @property
    def type(self) -> MessageType:
        return self._type

    @property
    def fields(self) -> con.Container:
        return self._fields

    @property
    def timestamp(self) -> float:
        return self._timestamp

    def __str__(self):
        return '%s:%s' % (self.type, self.fields)

    def __repr__(self):
        return '%r:%r' % (self.type, self.fields)


class Codec:
    """
    Use this class to encode and decode messages.
    It uses software version numbers to determine which message formats to use.
    """
    def __init__(self, version_major_minor: typing.Tuple[int, int]):
        if len(version_major_minor) != 2:
            raise TypeError('Expected an iterable of size 2')

        # Currently we don't do much here. In the future we may want to add additional logic that would be
        # adjusting the behavior of the class by swapping the available message definitions.
        # Some messages may also encode version information individually within themselves.
        self._version: typing.Tuple[int, int] = tuple(map(int, version_major_minor))

        if self._version[0] > 1:
            raise UnsupportedVersionException('Cannot communicate with version %r' % self._version)

        # We could add lists of formats, e.g. using construct.Select, that could be tried consecutively
        # until the first working format is found.
        # E.g. con.Select(GeneralStatusMessageFormatV1, GeneralStatusMessageFormatV2)
        # http://construct.readthedocs.io/en/latest/misc.html#select
        # Beware that this will only work if message types are terminated, i.e. contain construct.Terminated at the end!
        # Therefore all message types must be terminated in order to facilitate this approach!
        self._type_mapping: typing.Dict[MessageType, typing.Tuple[int, con.Struct]] = {
            MessageType.GENERAL_STATUS:         (0, GeneralStatusMessageFormatV1),
            MessageType.DEVICE_CHARACTERISTICS: (1, DeviceCharacteristicsMessageFormatV1),
            MessageType.COMMAND:                (2, CommandMessageFormatV1),
            MessageType.TASK_STATISTICS:        (3, TaskStatisticsMessageFormatV1),
        }

    def decode(self, frame: popcop.transport.ReceivedFrame) -> Message:
        for mt, (frame_type_code, formatter) in self._type_mapping.items():
            if frame_type_code == frame.frame_type_code:
                break
        else:
            raise UnknownMessageException('Unknown frame type code when decoding: %r' % frame.frame_type_code)

        try:
            if frame.payload:
                fields = formatter.parse(frame.payload)
            else:
                fields = con.Container()
        except Exception as ex:
            raise InvalidPayloadException('Cannot decode message') from ex

        return Message(mt, fields, frame.timestamp)

    def encode(self, message: typing.Union[Message, MessageType]) -> typing.Tuple[int, bytes]:
        if isinstance(message, MessageType):
            message = Message(message)

        try:
            frame_type_code, formatter = self._type_mapping[message.type]
        except KeyError:
            raise UnknownMessageException('Unknown message type when encoding: %r' % message.type)

        try:
            if len(message.fields):
                encoded = formatter.build(message.fields)
            else:
                encoded = bytes()
        except Exception as ex:
            raise InvalidFieldsException('Cannot encode message') from ex

        return frame_type_code, encoded


def _unittest_codec():
    from binascii import hexlify
    import time

    c = Codec((1, 2))

    msg = Message(MessageType.COMMAND)
    msg.fields.task_id = 'running'
    msg.fields.task_specific_command = {
        'mode': 'current',
        'value': 123.456,
    }

    ftp, payload = c.encode(msg)
    print(ftp)
    print(hexlify(payload))

    msg = c.decode(popcop.transport.ReceivedFrame(ftp, payload, time.monotonic()))
    print(msg)

    ftp, payload = c.encode(Message(MessageType.COMMAND))
    assert len(payload) == 0

    msg = c.decode(popcop.transport.ReceivedFrame(ftp, payload, time.monotonic()))
    assert len(msg.fields) == 0

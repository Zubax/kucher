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

import math
import numpy
import typing
from logging import getLogger
from view.device_model_representation import Register
from view.utils import cached


MAX_LINE_LENGTH = 40


_logger = getLogger(__name__)


def display_value(value, type_id: Register.ValueType) -> str:
    """
    Converts a register value to human-readable text.
    """
    if value is None:
        return ''
    elif isinstance(value, (str, bytes)):
        return str(value)
    else:
        if isinstance(value, (int, float, bool)):
            value = [value]

        if (len(value) == 1) and not isinstance(value[0], float):
            return str(value[0])

        dtype = Register.get_numpy_type(type_id)
        if dtype is None:
            raise ValueError(f'Unknown type ID: {type_id!r}')

        return _display_array_of_scalars(value, dtype)


def _display_array_of_scalars(value, dtype: numpy.dtype) -> str:
    # TODO: Format as rectangular arrays whenever possible

    # Actual formatting is mostly done by Numpy
    text = numpy.array2string(numpy.array(value, dtype=dtype),
                              max_line_width=MAX_LINE_LENGTH,
                              formatter=_get_numpy_formatter(dtype),
                              separator=', ',
                              threshold=10000)
    text = text.strip('[]').replace('\n ', '\n')
    return text


@cached
def _get_numpy_formatter(dtype: numpy.dtype) -> dict:
    """Formatter construction can be very slow, we optimize it by caching the results"""
    try:
        if dtype == numpy.bool_:
            return {
                'bool': '{:d}'.format       # Formatting as integer to conserve space
            }
        else:
            info = numpy.iinfo(dtype)
            item_length = max(len(str(info.max)), len(str(info.min)))
            return {
                'int_kind': ('{' + f':{item_length}' + '}').format
            }
    except ValueError:
        decimals = int(abs(math.log10(numpy.finfo(dtype).resolution)) + 0.5)
        return {
            'float_kind': '{:#.@g}'.replace('@', str(decimals)).format
        }


def _unittest_display_value():
    tid = Register.ValueType
    assert display_value(True, tid.BOOLEAN) == 'True'
    assert display_value(False, tid.BOOLEAN) == 'False'
    assert display_value([True, False, True], tid.BOOLEAN) == '1, 0, 1'

    assert display_value(123, tid.U8) == '123'
    assert display_value([-1, +12, -123], tid.I8) == '  -1,   12, -123'
    assert display_value(123.456789, tid.F32) == '123.457'
    assert display_value([123.456789, -12e-34], tid.F32) == '123.457, -1.20000e-33'

    assert display_value(list(range(9)), tid.F64) == '''
0.00000000000000, 1.00000000000000,
2.00000000000000, 3.00000000000000,
4.00000000000000, 5.00000000000000,
6.00000000000000, 7.00000000000000,
8.00000000000000
'''.strip()

    assert display_value(list(range(9)), tid.F32) == '''
0.00000, 1.00000, 2.00000, 3.00000,
4.00000, 5.00000, 6.00000, 7.00000,
8.00000
'''.strip()


def parse_value(text: str, type_id: Register.ValueType):
    """
    Inverse to @ref display_value().
    """
    value = _parse_value_impl(text, type_id)
    _logger.info('Value parser [with type %r]: %r --> %r', type_id, text, value)
    return value


def _parse_value_impl(text: str, type_id: Register.ValueType):
    if type_id == Register.ValueType.EMPTY:
        return None

    if type_id == Register.ValueType.STRING:
        return text

    if type_id == Register.ValueType.UNSTRUCTURED:
        return text.encode('latin1')

    def parse_scalar(x: str) -> typing.Union[int, float]:
        try:
            return int(x, 0)        # Supporting standard radix prefixes: 0x, 0b, 0o
        except ValueError:
            return float(x)         # Couldn't parse int, try float

    # Normalize the case, resolve some special values, normalize separators
    text = text.lower().replace('true', '1').replace('false', '0').replace(',', ' ').strip()

    return [parse_scalar(x) for x in text.split()]


def _unittest_parse_value():
    from pytest import approx
    tid = Register.ValueType
    assert parse_value('', tid.EMPTY) is None
    assert parse_value('Arbitrary', tid.EMPTY) is None
    assert parse_value('Arbitrary', tid.STRING) == 'Arbitrary'
    assert parse_value('\x01\x02\x88\xFF', tid.UNSTRUCTURED) == bytes([1, 2, 0x88, 0xFF])
    assert parse_value('0', tid.BOOLEAN) == [False]
    assert parse_value('True, false', tid.BOOLEAN) == [True, False]
    assert parse_value('true, False', tid.I8) == [1, 0]
    assert parse_value('0.123, 56.45', tid.F32) == [approx(0.123), approx(56.45)]
    assert parse_value('0.123, 56.45, 123', tid.F64) == [approx(0.123), approx(56.45), 123]

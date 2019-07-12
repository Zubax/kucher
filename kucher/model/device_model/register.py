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
import time
import numpy
import typing
import itertools
from decimal import Decimal
from popcop.standard.register import ValueType, Flags, ValueKind, VALUE_TYPE_TO_KIND, SCALAR_VALUE_TYPE_TO_NUMPY_TYPE
from kucher.utils import Event


StrictValueTypeAnnotation = typing.Union[
    str,
    bytes,
    typing.List[bool],
    typing.List[int],
    typing.List[float],
]

RelaxedValueTypeAnnotation = typing.Union[
    StrictValueTypeAnnotation,
    bool,
    int,
    float,
]

SetGetCallback = typing.Callable[[typing.Optional[StrictValueTypeAnnotation]],
                                 typing.Awaitable[typing.Tuple[StrictValueTypeAnnotation,   # Value
                                                               Decimal,                     # Device timestamp
                                                               float]]]                     # Monotonic timestamp


class Register:
    """
    Representation of a device register.
    None of the fields can be changed, except Value. When a new value is written, the class will
    attempt to coerce the new value into the required type. If a coercion cannot be performed or
    is ambiguous, an exception will be thrown.
    Note that this type is hashable and can be used in mappings like dict.
    """
    ValueType = ValueType
    ValueKind = ValueKind

    def __init__(self,
                 name:                          str,
                 value:                         StrictValueTypeAnnotation,
                 default_value:                 typing.Optional[StrictValueTypeAnnotation],
                 min_value:                     typing.Optional[StrictValueTypeAnnotation],
                 max_value:                     typing.Optional[StrictValueTypeAnnotation],
                 type_id:                       ValueType,
                 flags:                         Flags,
                 update_timestamp_device_time:  Decimal,
                 set_get_callback:              SetGetCallback,
                 update_timestamp_monotonic:    float = None):
        self._name = str(name)
        self._cached_value = value
        self._default_value = default_value
        self._min_value = min_value
        self._max_value = max_value
        self._type_id = ValueType(type_id)
        self._update_ts_device_time = Decimal(update_timestamp_device_time)
        self._update_ts_monotonic = float(update_timestamp_monotonic or time.monotonic())
        self._flags = flags
        self._set_get_callback = set_get_callback

        self._update_event = Event()

    @property
    def name(self) -> str:
        return self._name

    @property
    def cached_value(self) -> StrictValueTypeAnnotation:
        return self._cached_value

    @property
    def default_value(self) -> typing.Optional[StrictValueTypeAnnotation]:
        return self._default_value

    @property
    def has_default_value(self) -> bool:
        return self._default_value is not None

    @property
    def cached_value_is_default_value(self) -> bool:
        if not self.has_default_value:
            return False

        if self.type_id in (ValueType.F32,
                            ValueType.F64):
            # Absolute tolerance equals the epsilon as per IEEE754
            absolute_tolerance = {
                ValueType.F32: 1e-6,
                ValueType.F64: 1e-15,
            }[self.type_id]

            # Relative tolerance is roughly the epsilon multiplied by 10...100
            relative_tolerance = {
                ValueType.F32: 1e-5,
                ValueType.F64: 1e-13,
            }[self.type_id]

            return all(map(lambda args: math.isclose(*args, rel_tol=relative_tolerance, abs_tol=absolute_tolerance),
                           itertools.zip_longest(self.cached_value, self.default_value)))
        else:
            return self.cached_value == self.default_value

    @property
    def min_value(self) -> typing.Optional[StrictValueTypeAnnotation]:
        return self._min_value

    @property
    def max_value(self) -> typing.Optional[StrictValueTypeAnnotation]:
        return self._max_value

    @property
    def has_min_and_max_values(self) -> bool:
        return self._min_value is not None and self._max_value is not None

    @property
    def type_id(self) -> ValueType:
        return self._type_id

    @property
    def kind(self) -> ValueKind:
        return VALUE_TYPE_TO_KIND[self.type_id]

    @property
    def update_timestamp_device_time(self) -> Decimal:
        return self._update_ts_device_time

    @property
    def update_timestamp_monotonic(self) -> float:
        return self._update_ts_monotonic

    @property
    def mutable(self) -> bool:
        return self._flags.mutable

    @property
    def persistent(self) -> bool:
        return self._flags.persistent

    @property
    def update_event(self) -> Event:
        """
        Event arguments:
            Reference to the emitting Register instance.
        """
        return self._update_event

    async def write_through(self, value: RelaxedValueTypeAnnotation) -> StrictValueTypeAnnotation:
        """
        Sets the provided value to the device, then requests the new value from the device,
        at the same time updating the cache with the latest state once the response is received.
        The new value is returned, AND an update event is generated.
        Beware that the cache may remain inconsistent until the response is received.
        """
        value = self._stricten(value)
        # Should we update the cache before the new value has been confirmed? Probably not.
        v, dt, mt = await self._set_get_callback(value)
        self._sync(v, dt, mt)
        return v

    async def read_through(self) -> StrictValueTypeAnnotation:
        """
        Requests the value from the device, at the same time updating the cache with the latest state.
        The new value is returned, AND an update event is generated.
        """
        v, dt, mt = await self._set_get_callback(None)
        self._sync(v, dt, mt)
        return v

    @staticmethod
    def get_numpy_type(type_id: ValueType) -> typing.Optional[numpy.dtype]:
        try:
            return SCALAR_VALUE_TYPE_TO_NUMPY_TYPE[type_id]
        except KeyError:
            return None

    def _sync(self,
              value:            RelaxedValueTypeAnnotation,
              device_time:      Decimal,
              monotonic_time:   float):
        """This method is invoked from the Connection instance."""
        self._cached_value = value
        self._update_ts_device_time = Decimal(device_time)
        self._update_ts_monotonic = float(monotonic_time)
        self._emit_update_event()

    def _emit_update_event(self):
        self._update_event.emit(self)

    @staticmethod
    def _stricten(value: RelaxedValueTypeAnnotation) -> StrictValueTypeAnnotation:
        scalars = int, float, bool
        if isinstance(value, scalars):
            return [value]
        elif isinstance(value, (str, bytes)):
            return value
        else:
            try:
                return [x for x in value]   # Coerce to list
            except TypeError:
                raise TypeError(f'Invalid type of register value: {type(value)!r}')

    def __str__(self):
        # Monotonic timestamps are imprecise, so we print them with a low number of decimal places.
        # Device-provided timestamps are extremely accurate (sub-microsecond resolution and precision).
        # We use "!s" with the enum, otherwise it prints as int (quite surprising).
        out = f'name={self.name!r}, type_id={self.type_id!s}, ' \
              f'cached={self.cached_value!r}, default={self.default_value!r}, ' \
              f'min={self.min_value!r}, max={self.max_value!r}, ' \
              f'mutable={self.mutable}, persistent={self.persistent}, ' \
              f'ts_device={self.update_timestamp_device_time:.9f}, ts_mono={self.update_timestamp_monotonic:.3f}'

        return f'Register({out})'

    __repr__ = __str__

    def __hash__(self):
        return hash(self.name + str(self.type_id))

    def __eq__(self, other):
        if isinstance(other, Register):
            return (self.name == other.name) and (self.type_id == other.type_id)
        else:
            return NotImplemented

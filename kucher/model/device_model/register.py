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

import time
import typing
from decimal import Decimal
from popcop.standard.register import ValueType, Flags
from utils import Event


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
    """
    ValueType = ValueType

    def __init__(self,
                 name:                          str,
                 value:                         StrictValueTypeAnnotation,
                 type_id:                       ValueType,
                 flags:                         Flags,
                 update_timestamp_device_time:  Decimal,
                 set_get_callback:              SetGetCallback,
                 update_timestamp_monotonic:    float=None):
        self._name = str(name)
        self._cached_value = value
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
    def type_id(self) -> ValueType:
        return self._type_id

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
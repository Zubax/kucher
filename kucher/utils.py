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
from logging import getLogger


def synchronized(method):
    """
    Simple decorator that can be used to make object methods thread-safe.
    The decorator requires that the target object contains an attribute "_lock" which is a recursive mutex.
    The decorator will fail with an AttributeError if the lock attribute does not exist.
    Some theory:
        https://stackoverflow.com/questions/29402606/
        https://github.com/GrahamDumpleton/wrapt/blob/develop/blog/07-the-missing-synchronized-decorator.md
        https://github.com/GrahamDumpleton/wrapt/blob/develop/blog/08-the-synchronized-decorator-as-context-manager.md
    """
    def decorator(self, *arg, **kws):
        with self._lock:
            return method(self, *arg, **kws)

    return decorator


class Event:
    def __init__(self):
        self._handlers: typing.Set[typing.Callable] = set()
        self._logger = getLogger(__name__ + f'.Event[{self}]')

    def connect(self, handler: typing.Callable) -> 'Event':
        self._logger.debug('Adding new handler %r', handler)
        self._handlers.add(handler)
        return self

    def disconnect(self, handler: typing.Callable) -> 'Event':
        self._logger.debug('Removing handler %r', handler)
        try:
            self._handlers.remove(handler)
        except LookupError:
            raise ValueError(f'Handler {handler} is not registered') from None

        return self

    def emit(self, *args, **kwargs):
        for handler in self._handlers:
            try:
                handler(*args, **kwargs)
            except Exception as ex:
                self._logger.exception('Unhandled exception %r in the handler %r', ex, handler)

    @property
    def num_handlers(self):
        return len(self._handlers)

    def __len__(self):
        return len(self._handlers)

    def __iadd__(self, other: typing.Callable):
        return self.connect(other)

    def __isub__(self, other: typing.Callable):
        return self.disconnect(other)

    def __call__(self, *args, **kwargs):
        return self.emit(*args, **kwargs)


def _unittest_event():
    from pytest import raises

    e = Event()
    assert e.num_handlers == 0
    e()
    e(123, '456')

    acc = ''

    def acc_add(*s):
        nonlocal acc
        acc += ''.join(s)

    e += acc_add
    e('123', 'abc')
    e('def')
    e()
    assert len(e) == 1
    assert acc == '123abcdef'

    with raises(ValueError):
        e -= lambda a: None

    e -= acc_add
    assert len(e) == 0
    e(123, '456')

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
import weakref
import inspect
import functools
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

    # noinspection PyUnusedLocal
    def connect_weak(self, instance, unbound_method: 'type(Event.connect)') -> 'Event':
        """
        Adds a weak handler that points to a method. This callback will be automatically removed when
        the pointed-to object is garbage collected. Observe that we require a reference to an instance
        here, and not just a bound method, because bound methods are dedicated objects themselves, and
        therefore if we were to keep a weak reference to that, our bound method instance would be immediately
        garbage collected. Weak-referenced bound methods, like lambdas, are always dead on arrival. More info:
          https://stackoverflow.com/questions/599430/why-doesnt-the-weakref-work-on-this-bound-method
          https://stackoverflow.com/questions/5394772/why-are-my-weakrefs-dead-in-the-water-when-they-point-to-a-method
        """
        weak_instance = weakref.ref(instance)
        instance_as_str = repr(instance)    # We're formatting it right now because we can't keep strong references
        instance = None                     # Erase to prevent accidental re-use

        if inspect.ismethod(unbound_method):
            raise TypeError(f'Usage of bound methods, lambdas, and proxy functions as weak handlers is not '
                            f'possible, because these are dedicated objects themselves and they will be '
                            f'garbage collected immediately after the last strong reference is removed. '
                            f'You should use unbound methods instead. '
                            f'Here are the arguments that you tried to use: {instance}, {unbound_method}')

        # noinspection PyShadowingNames
        @functools.wraps(unbound_method)
        def proxy(*args, **kwargs):
            instance = weak_instance()
            if instance is not None:
                return unbound_method(instance, *args, **kwargs)
            else:
                self._logger.info('Weak reference has died: %r', instance_as_str)
                self.disconnect(proxy)

        return self.connect(proxy)

    def disconnect(self, handler: typing.Callable) -> 'Event':
        self._logger.debug('Removing handler %r', handler)
        try:
            self._handlers.remove(handler)
        except LookupError:
            raise ValueError(f'Handler {handler} is not registered') from None

        return self

    def emit(self, *args, **kwargs):
        for handler in list(self._handlers):        # The invocation list can be modified from callbacks!
            try:
                handler(*args, **kwargs)
            except Exception as ex:
                self._logger.exception('Unhandled exception %r in the handler %r', ex, handler)

    @property
    def num_handlers(self):
        return len(self._handlers)

    def __len__(self):
        return len(self._handlers)

    def __call__(self, *args, **kwargs):
        return self.emit(*args, **kwargs)


def _unittest_event():
    import gc
    from pytest import raises

    e = Event()
    assert e.num_handlers == 0
    e()
    e(123, '456')

    acc = ''

    def acc_add(*s):
        nonlocal acc
        acc += ''.join(s)

    e.connect(acc_add)
    e('123', 'abc')
    e('def')
    e()
    assert len(e) == 1
    assert acc == '123abcdef'

    with raises(ValueError):
        e.disconnect(lambda a: None)

    e.disconnect(acc_add)
    assert len(e) == 0
    e(123, '456')

    # noinspection PyMethodMayBeStatic
    class Holder:
        def __init__(self, evt: Event):
            evt.connect_weak(self, Holder.receiver)

        def receiver(self, *args):
            nonlocal acc
            acc += ''.join(args)

    assert len(e) == 0
    holder = Holder(e)
    assert len(e) == 1
    e(' Weak')
    assert len(e) == 1
    del holder
    gc.collect()

    assert len(e) == 1
    e('Dead x_x')
    assert len(e) == 0

    assert acc == '123abcdef Weak'

    holder = Holder(e)
    assert len(e) == 1

    with raises(TypeError):
        e.connect_weak(holder, holder.receiver)

    del holder
    gc.collect()

    assert len(e) == 1
    e('Dead x_x')
    assert len(e) == 0
    assert acc == '123abcdef Weak'

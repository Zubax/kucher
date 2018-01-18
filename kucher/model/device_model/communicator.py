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
import popcop
import typing
from logging import getLogger
import threading
from ..utils import synchronized
from .messages import MessageType, Message, Codec

__all__ = ['Communicator']

MAX_PAYLOAD_SIZE = 1024
FRAME_TIMEOUT = 0.5


_logger = getLogger(__name__)


class CommunicatorException(Exception):
    pass


class Canceller:
    """
    This instance is returned from communicator's subscribing methods. It can be used to cancel subscriptions.
    Storing this object is not mandatory at all.
    """
    def __init__(self, impl):
        self._impl = impl

    def cancel(self):
        # noinspection PyBroadException
        try:
            self._impl()
            return True
        except Exception:
            return False


class Communicator:
    def __init__(self,
                 port_name: str,
                 raw_data_handler_callback: typing.Callable):
        self._lock = threading.RLock()
        self._ch = popcop.physical.serial_multiprocessing.Channel(port_name=port_name,
                                                                  max_payload_size=MAX_PAYLOAD_SIZE,
                                                                  frame_timeout=FRAME_TIMEOUT)
        self._raw_data_sink = raw_data_handler_callback
        self._codec: Codec = None

        self._subscriptions: typing.List[typing.Callable] = []

        self._timed_callbacks: typing.List[typing.Tuple[float, typing.Callable]] = []

    @staticmethod
    def _match_message(msg_type: typing.Union[MessageType,
                                              popcop.standard.MessageBase,
                                              typing.Type[popcop.standard.MessageBase]],
                       msg: typing.Union[Message, popcop.standard.MessageBase]):
        if isinstance(msg_type, popcop.standard.MessageBase):
            msg_type = type(msg_type)   # We were supplied with a prototype instead; resolve it

        if isinstance(msg, Message) and isinstance(msg_type, MessageType):
            return msg.type == msg_type
        elif isinstance(msg, popcop.standard.MessageBase) and isinstance(msg_type, type):
            return isinstance(msg, msg_type)

        return False

    @synchronized
    def send(self,
             message_or_type: typing.Union[Message,
                                           popcop.standard.MessageBase,
                                           typing.Type[popcop.standard.MessageBase]],
             timeout: typing.Optional[typing.Union[float, int]]=None,
             callback: typing.Optional[typing.Callable]=None,
             predicate: typing.Optional[typing.Callable]=None) -> Canceller:
        # Sending the message
        if isinstance(message_or_type, Message):
            if self._codec is None:
                raise CommunicatorException('Codec is not yet initialized, cannot send application-specific message')

            frame_type_code, payload = self._codec.encode(message_or_type)
            self._ch.send_application_specific(frame_type_code, payload)
        else:
            self._ch.send_standard(message_or_type)

        # Setting up the response handler after the message is sent
        predicate = predicate if predicate is not None else (lambda *_: True)

        def handler(msg: typing.Union[Message, popcop.standard.MessageBase]):
            if self._match_message(message_or_type, msg):
                if predicate(msg):
                    do_cancel()
                    callback(msg)

        def timeout_handler():
            do_cancel()
            callback(None)

        def do_cancel():
            if handler in self._subscriptions:
                self._subscriptions.remove(handler)

            if timed_callback_entry in self._timed_callbacks:
                self._timed_callbacks.remove(timed_callback_entry)

        timed_callback_entry = None     # Default
        if callback is not None:
            self._subscriptions.append(handler)
            if timeout is not None and timeout > 0:
                timed_callback_entry = (time.monotonic() + timeout, timeout_handler)
                self._timed_callbacks.append(timed_callback_entry)

        # We return a canceller even if no response was requested, for the sake of consistency.
        # In that case, the dummy canceller does nothing useful.
        return Canceller(do_cancel)

    @synchronized
    def subscribe(self,
                  message_type: typing.Union[MessageType, typing.Type[popcop.standard.MessageBase]],
                  callback: typing.Callable,
                  predicate: typing.Optional[typing.Callable]=None) -> Canceller:
        predicate = predicate if predicate is not None else (lambda *_: True)

        def handler(msg: typing.Union[Message, popcop.standard.MessageBase]):
            if self._match_message(message_type, msg):
                if predicate(msg):
                    callback(msg)

        def do_cancel():
            if handler in self._subscriptions:
                self._subscriptions.remove(handler)

        self._subscriptions.append(handler)
        return Canceller(do_cancel)

    def _call_raw_data_sink(self, item):
        try:
            self._raw_data_sink(item)
        except Exception as ex:
            _logger.error('Unhandled exception in raw data sink callback; data: %r', item, ex, exc_info=True)

    def _call_subscriptions(self, item: typing.Union[popcop.transport.ReceivedFrame,
                                                     popcop.standard.MessageBase]):
        if isinstance(item, popcop.transport.ReceivedFrame):
            if self._codec is None:
                _logger.warning('Cannot decode frame because the codec is not yet initialized: %r', item)
                return

            # noinspection PyBroadException
            try:
                message = self._codec.decode(item)
            except Exception:
                _logger.warning('Could not decode frame: %r', item, exc_info=True)
                return
        elif isinstance(item, popcop.standard.MessageBase):
            message = item
        else:
            raise TypeError("Don't know how to handle this item: %r" % item)

        for sub in self._subscriptions:
            try:
                sub(message)
            except Exception as ex:
                _logger.error('Unhandled exception in subscription callback %r: %r', sub, ex, exc_info=True)

    @synchronized
    def poll(self):
        """Handles ALL enqueued messages non-blockingly, then returns."""
        while True:
            ret = self._ch.receive()
            if isinstance(ret, (bytes, bytearray)):
                self._call_raw_data_sink(ret)
            elif ret is not None:
                self._call_subscriptions(ret)
            else:
                break

        # Process timed callbacks
        for item in self._timed_callbacks[:]:
            deadline, callback = item
            if time.monotonic() >= deadline:
                try:
                    callback()
                except Exception as ex:
                    _logger.error('Unhandled exception in timed callback %r: %r', item, ex, exc_info=True)
                finally:
                    self._timed_callbacks.remove(item)

    @synchronized
    def close(self):
        self._ch.close()


def _unittest_communicator():       # TODO: Write tests
    pass

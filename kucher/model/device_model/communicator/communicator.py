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
import asyncio
import threading
from logging import getLogger
from .messages import MessageType, Message, Codec
from .exceptions import CommunicatorException
from popcop.standard import MessageBase as StandardMessageBase
from popcop.transport import ReceivedFrame

__all__ = ['Communicator', 'CommunicationChannelClosedException', 'LOOPBACK_PORT_NAME']

MAX_PAYLOAD_SIZE = 1024
FRAME_TIMEOUT = 0.5
LOOPBACK_PORT_NAME = 'loop://'
STATE_CHECK_INTERVAL = 0.1

AnyMessage = typing.Union[Message, StandardMessageBase]
StandardMessageType = typing.Type[StandardMessageBase]

_logger = getLogger(__name__)


class CommunicationChannelClosedException(CommunicatorException):
    pass


class Communicator:
    """
    Asynchronous communicator class. This class is not thread-safe!

    The constructor is not async-friendly (it is blocking).
    The factory method new() should be used in async contexts.
    """

    IO_WORKER_ERROR_LIMIT = 100

    def __init__(self,
                 port_name: str,
                 event_loop: asyncio.AbstractEventLoop):
        """The constructor is blocking. Use the factory method new() in async contexts instead."""
        self._event_loop = event_loop
        self._ch = popcop.physical.serial_multiprocessing.Channel(port_name=port_name,
                                                                  max_payload_size=MAX_PAYLOAD_SIZE,
                                                                  frame_timeout=FRAME_TIMEOUT)
        self._codec: Codec = None

        self._log_queue = asyncio.Queue(loop=event_loop)
        self._message_queue = asyncio.Queue(loop=event_loop)

        self._pending_requests: typing.Set[typing.Tuple[typing.Callable, asyncio.Future]] = set()

        self._thread_handle = threading.Thread(target=self._thread_entry,
                                               name='communicator_io_worker',
                                               daemon=True)
        self._thread_handle.start()

    def __del__(self):
        try:
            if self.is_open:
                self._ch.close()
        except AttributeError:
            pass

    @staticmethod
    async def new(port_name: str,
                  event_loop: asyncio.AbstractEventLoop) -> 'Communicator':
        """
        Use this method to create new instances of this class from async contexts.
        """
        return await event_loop.run_in_executor(None, lambda: Communicator(port_name=port_name,
                                                                           event_loop=event_loop))

    def _thread_entry(self):
        # This thread is NOT allowed to invoke any methods of this class, for thread safety reasons!
        # The only field the thread is allowed to access is the communicatoin channel instance (which is thread safe).
        # Instead, we rely on call_soon_threadsafe() defined by the event loop.
        error_counter = 0
        while self._ch.is_open:
            # noinspection PyBroadException
            try:
                ret = self._ch.receive(STATE_CHECK_INTERVAL)
                if isinstance(ret, bytes):
                    ts = time.monotonic()
                    log_str = ret.decode(encoding='utf8', errors='replace')
                    _logger.debug('Received log string at %r: %r', ts, log_str)
                    self._event_loop.call_soon_threadsafe(self._log_queue.put_nowait, (ts, log_str))
                elif ret is not None:
                    _logger.debug('Received item: %r', ret)
                    self._event_loop.call_soon_threadsafe(self._process_received_item, ret)
            except popcop.physical.serial_multiprocessing.ChannelClosedException as ex:
                _logger.info('Stopping the IO worker thread because the channel is closed. Error: %r', ex)
                break
            except Exception as ex:
                error_counter += 1
                _logger.exception(f'Unhandled exception in IO worker thread '
                                  f'({error_counter} of {self.IO_WORKER_ERROR_LIMIT}): {ex}')
                if error_counter > self.IO_WORKER_ERROR_LIMIT:
                    _logger.error('Too many errors, stopping!')
                    break
            else:
                error_counter = 0

        _logger.info('IO worker thread is stopping')
        # noinspection PyBroadException
        try:
            self._ch.close()
        except Exception:
            _logger.exception('Could not close the channel properly')

        # This is required to un-block the waiting coroutines, if any.
        self._event_loop.call_soon_threadsafe(self._message_queue.put_nowait, None)
        self._event_loop.call_soon_threadsafe(self._log_queue.put_nowait, None)

    def _process_received_item(self, item: typing.Union[ReceivedFrame, StandardMessageBase]) -> None:
        if isinstance(item, StandardMessageBase):
            message = item
        elif isinstance(item, ReceivedFrame):
            if self._codec is None:
                _logger.warning('Cannot decode application-specific frame because the codec is not yet initialized: %r',
                                item)
                return
            # noinspection PyBroadException
            try:
                message = self._codec.decode(item)
            except Exception:
                _logger.warning('Could not decode frame: %r', item, exc_info=True)
                return
        else:
            raise TypeError(f"Don't know how to handle this item: {item}")

        at_least_one_match = False
        for predicate, future in self._pending_requests:
            if not future.done() and predicate(message):
                at_least_one_match = True
                _logger.debug('Matching response: %r %r', item, future)
                future.set_result(message)

        if not at_least_one_match:
            self._message_queue.put_nowait(message)

    async def _do_send(self, message_or_type: typing.Union[Message, StandardMessageBase, StandardMessageType]):
        """
        This function is made async, but the current implementation does not require awaiting -
        we simply dump the message into the channel's queue non-blockingly and then return immediately.
        This implementation detail may be changed in the future, but the API won't be affected.
        """
        try:
            if isinstance(message_or_type, (Message, MessageType)):
                if self._codec is None:
                    raise CommunicatorException('Codec is not yet initialized, '
                                                'cannot send application-specific message')

                frame_type_code, payload = self._codec.encode(message_or_type)
                self._ch.send_application_specific(frame_type_code, payload)

            elif isinstance(message_or_type, (StandardMessageBase, type)):
                self._ch.send_standard(message_or_type)

            else:
                raise TypeError(f'Invalid message or message type {type(message_or_type)}: {message_or_type}')
        except popcop.physical.serial_multiprocessing.ChannelClosedException as ex:
            raise CommunicationChannelClosedException from ex

    @staticmethod
    def _match_message(reference: typing.Union[Message,
                                               MessageType,
                                               StandardMessageBase,
                                               StandardMessageType],
                       candidate: AnyMessage) -> bool:
        # Eliminate prototypes
        if isinstance(reference, StandardMessageBase):
            reference = type(reference)
        elif isinstance(reference, Message):
            reference = reference.type

        if isinstance(candidate, Message) and isinstance(reference, MessageType):
            return candidate.type == reference
        elif isinstance(candidate, StandardMessageBase) and isinstance(reference, type):
            return isinstance(candidate, reference)

    def set_protocol_version(self, major_minor: typing.Tuple[int, int]):
        """
        Sets the current protocol version, which defines which message formats to use.
        The protocol versions can be swapped at any time.
        By default, no protocol version is set, so only standard messages can be used.
        The user is required to assign a protocol version before using application-specific messages.
        """
        self._codec = Codec(major_minor)

    async def send(self, message: AnyMessage):
        """
        Simply emits the specified message asynchronously.
        """
        await self._do_send(message)

    async def request(self,
                      message_or_type: typing.Union[Message, MessageType, StandardMessageBase, StandardMessageType],
                      timeout: typing.Optional[typing.Union[float, int]]=None,
                      predicate: typing.Optional[typing.Callable[[AnyMessage], bool]]=None) ->\
            typing.Optional[AnyMessage]:
        """
        Sends a message, then awaits for a matching response.
        If no matching response was received before the timeout has expired, returns None.
        """
        timeout = float(timeout or popcop.standard.DEFAULT_STANDARD_REQUEST_TIMEOUT)
        if timeout <= 0:
            raise ValueError('A positive timeout is required')

        await self._do_send(message_or_type)

        def super_predicate(item: AnyMessage) -> bool:
            if predicate is not None:
                try:
                    return predicate(item)
                except Exception as ex:
                    _logger.exception('Unhandled exception in response predicate for message %r: %r',
                                      message_or_type, ex)
            else:
                return self._match_message(message_or_type, item)

        future = self._event_loop.create_future()
        entry = super_predicate, future
        try:
            self._pending_requests.add(entry)
            return await asyncio.wait_for(future, timeout, loop=self._event_loop)
        except asyncio.TimeoutError:
            return None
        finally:
            self._pending_requests.remove(entry)

    async def receive(self) -> AnyMessage:
        """
        Awaits for messages from the connected node.
        Throws CommunicationChannelClosedException if the channel is closed or becomes closed while waiting.
        """
        if self.is_open or not self._message_queue.empty():
            out = await self._message_queue.get()
            if out is not None:
                return out

        raise CommunicationChannelClosedException

    async def read_log(self) -> typing.Tuple[float, str]:
        """
        Awaits for log data from the connected node.
        Throws CommunicationChannelClosedException if the channel is closed or becomes closed while waiting.
        """
        if self.is_open or not self._log_queue.empty():
            out = await self._log_queue.get()
            if out is not None:
                return out

        raise CommunicationChannelClosedException

    async def close(self):
        await asyncio.gather(self._event_loop.run_in_executor(None, self._thread_handle.join),
                             self._event_loop.run_in_executor(None, self._ch.close),
                             loop=self._event_loop)
        # This is required to un-block the waiting coroutines, if any.
        self._message_queue.put_nowait(None)
        self._log_queue.put_nowait(None)

    @property
    def is_open(self):
        return self._ch.is_open


# noinspection PyProtectedMember
def _unittest_communicator_message_matcher():
    from popcop.standard import NodeInfoMessage

    mm = Communicator._match_message
    mt = MessageType

    assert mm(mt.GENERAL_STATUS, Message(mt.GENERAL_STATUS))
    assert not mm(Message(mt.GENERAL_STATUS), Message(mt.COMMAND))
    assert not mm(mt.COMMAND, NodeInfoMessage())
    assert not mm(Message(mt.COMMAND), NodeInfoMessage())
    assert mm(Message(mt.DEVICE_CHARACTERISTICS), Message(mt.DEVICE_CHARACTERISTICS))
    assert mm(NodeInfoMessage, NodeInfoMessage())
    assert mm(NodeInfoMessage(), NodeInfoMessage())
    assert not mm(NodeInfoMessage(), popcop.standard.MessageBase())


async def _async_unittest_communicator_loopback():
    from pytest import raises, approx

    loop = asyncio.get_event_loop()
    com = await Communicator.new(LOOPBACK_PORT_NAME, loop)

    # noinspection PyProtectedMember
    async def sender():
        com._ch.send_raw(b'Hello world!')
        with raises(CommunicatorException):
            await com.send(Message(MessageType.COMMAND, {'task_id': 'hardware_test', 'task_specific_command': {}}))

        com.set_protocol_version((1, 2))
        print('Sending COMMAND...')
        await com.send(Message(MessageType.COMMAND, {'task_id': 'hardware_test', 'task_specific_command': {}}))

        print('Requesting GENERAL_STATUS...')
        status_response = await com.request(Message(MessageType.GENERAL_STATUS), 1)
        print('GENERAL_STATUS response:', status_response)
        assert isinstance(status_response, Message)
        assert status_response.type == MessageType.GENERAL_STATUS
        assert not status_response.fields
        assert status_response.timestamp > 0

        with raises(CommunicationChannelClosedException):
            await com.receive()

    async def receiver():
        # This receiver will receive all messages that were not claimed by request() calls
        msg = await com.receive()
        print('Received:', msg)
        assert isinstance(msg, Message)
        assert msg.type == MessageType.COMMAND
        assert msg.fields.task_id == 'hardware_test'
        assert msg.fields.task_specific_command == {}

    async def log_reader():
        accumulator = ''
        while True:
            try:
                accumulator += (await com.read_log())[1]
            except CommunicationChannelClosedException:
                break

            print('Log accumulator:', accumulator)
            assert 'Hello world!'.startswith(accumulator)

        with raises(CommunicationChannelClosedException):
            await com.read_log()

    async def closer():
        assert com.is_open
        await asyncio.sleep(5, loop=loop)
        assert com.is_open
        await com.close()
        assert not com.is_open

        # Testing that close() is idempotent
        await com.close()

        with raises(CommunicationChannelClosedException):
            await com.send(Message(MessageType.COMMAND, {'task_id': 'hardware_test', 'task_specific_command': {}}))

        with raises(CommunicationChannelClosedException):
            await com.read_log()

        with raises(CommunicationChannelClosedException):
            await com.receive()

        # Testing idempotency again
        await com.close()
        await asyncio.sleep(1, loop=loop)
        await com.close()

    assert com.is_open
    await asyncio.gather(sender(),
                         receiver(),
                         log_reader(),
                         closer(),
                         loop=loop)


def _unittest_communicator_loopback():
    asyncio.get_event_loop().run_until_complete(_async_unittest_communicator_loopback())


async def _async_unittest_communicator_disconnect_detection():
    from pytest import raises

    loop = asyncio.get_event_loop()
    com = await Communicator.new(LOOPBACK_PORT_NAME, loop)

    async def receiver():
        with raises(CommunicationChannelClosedException):
            await com.receive()

    async def log_reader():
        with raises(CommunicationChannelClosedException):
            await com.read_log()

    # noinspection PyProtectedMember
    async def closer():
        assert com.is_open
        await asyncio.sleep(1, loop=loop)
        assert com.is_open

        com._ch.close()         # Simulate failure of the serial connection

        assert not com.is_open
        await asyncio.sleep(1, loop=loop)

        with raises(CommunicationChannelClosedException):
            await com.send(popcop.standard.NodeInfoMessage())

        with raises(CommunicationChannelClosedException):
            await com.read_log()

        with raises(CommunicationChannelClosedException):
            await com.receive()

        # Testing that close() is idempotent
        await com.close()

        # And again, because why not
        await com.close()
        await asyncio.sleep(1, loop=loop)
        await com.close()

    assert com.is_open
    await asyncio.gather(receiver(),
                         log_reader(),
                         closer(),
                         loop=loop)


def _unittest_communicator_disconnect_detection():
    asyncio.get_event_loop().run_until_complete(_async_unittest_communicator_disconnect_detection())

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

import popcop
import typing
import asyncio
from .communicator import Communicator, MessageType, Message, CommunicationChannelClosedException
from .device_info_view import DeviceInfoView
from .general_status_view import GeneralStatusView
from logging import getLogger


_logger = getLogger(__name__)


class ConnectionException(Exception):
    pass


class ConnectionNotEstablishedException(ConnectionException):
    pass


class ConnectionLostException(ConnectionNotEstablishedException):
    pass


class ConnectionAttemptFailedException(ConnectionException):
    pass


class IncompatibleDeviceException(ConnectionAttemptFailedException):
    pass


class Connection:
    """
    The connection object is assumed to be always connected as long as it exists.
    If it is detected that the connection is loss, a callback will be invoked.
    """

    def __init__(self,
                 event_loop:                    asyncio.AbstractEventLoop,
                 communicator:                  Communicator,
                 device_info:                   DeviceInfoView,
                 general_status_with_ts:        typing.Tuple[float, GeneralStatusView],
                 on_connection_loss:            typing.Callable[[typing.Union[str, Exception]], None],
                 on_general_status_update:      typing.Callable[[float, GeneralStatusView], None],
                 on_log_line:                   typing.Callable[[float, str], None],
                 general_status_update_period:  float):
        self._event_loop = event_loop
        self._com: Communicator = communicator
        self._device_info = device_info
        self._last_general_status_with_timestamp = general_status_with_ts
        self._general_status_update_period = general_status_update_period

        self._on_connection_loss = on_connection_loss
        self._on_general_status_update = on_general_status_update
        self._on_log_line = on_log_line

        self._launch_task(self._log_reader_task_entry_point)
        self._launch_task(self._receiver_task_entry_point)
        self._launch_task(self._status_monitoring_task_entry_point)

    @property
    def device_info(self) -> DeviceInfoView:
        return self._device_info

    @property
    def last_general_status_with_timestamp(self) -> typing.Tuple[float, GeneralStatusView]:
        return self._last_general_status_with_timestamp

    async def disconnect(self):
        self._on_connection_loss = lambda *_: None     # Suppress further reporting

        # noinspection PyBroadException
        try:
            await self._com.close()
        except Exception:
            _logger.exception('Could not properly close the communicator. '
                              'The communicator is a big boy and should be able to sort its stuff out on its own. '
                              'Hey communicator, you suck!')

    async def send(self, message: typing.Union[Message, popcop.standard.MessageBase]):
        try:
            await self._com.send(message)
        except CommunicationChannelClosedException as ex:
            raise ConnectionNotEstablishedException('Could not send the message because the communication channel is '
                                                    'closed') from ex

    async def request(self,
                      message_or_type: typing.Union[Message,
                                                    MessageType,
                                                    popcop.standard.MessageBase,
                                                    typing.Type[popcop.standard.MessageBase]],
                      timeout: typing.Optional[typing.Union[float, int]]=None,
                      predicate: typing.Optional[typing.Callable[[typing.Union[Message,
                                                                               popcop.standard.MessageBase]],
                                                                 bool]]=None) ->\
            typing.Union[Message, popcop.standard.MessageBase]:
        try:
            return await self._com.request(message_or_type,
                                           timeout=timeout,
                                           predicate=predicate)
        except CommunicationChannelClosedException as ex:
            raise ConnectionNotEstablishedException('Could not complete the request because the communication channel '
                                                    'is closed') from ex

    async def _handle_connection_loss(self, reason: typing.Union[str, Exception]):
        # noinspection PyBroadException
        try:
            self._on_connection_loss(reason)
        except Exception:
            _logger.exception('Unhandled exception in the connection loss callback')

        await self.disconnect()

    async def _status_monitoring_task_entry_point(self):
        while True:
            await asyncio.sleep(self._general_status_update_period, loop=self._event_loop)

            response = await self._com.request(MessageType.GENERAL_STATUS)
            if not response:
                raise ConnectionLostException('General status request has timed out')

            assert isinstance(response, Message)
            assert response.type == MessageType.GENERAL_STATUS

            prev = self._last_general_status_with_timestamp[1]
            new = GeneralStatusView.populate(response.fields)
            if prev.timestamp > new.timestamp:
                raise ConnectionLostException('Device has been restarted, connection lost')

            self._last_general_status_with_timestamp = response.timestamp, new
            self._on_general_status_update(*self._last_general_status_with_timestamp)

    async def _receiver_task_entry_point(self):
        while True:
            item = await self._com.receive()
            _logger.info('Unattended message: %r', item)

    async def _log_reader_task_entry_point(self):
        while True:
            timestamp, text = await self._com.read_log()
            for line in text.splitlines(keepends=True):
                self._on_log_line(timestamp, line)

    def _launch_task(self, target):
        async def proxy():
            _logger.info('Starting task %r', target)
            # noinspection PyBroadException
            try:
                await target()
            except CommunicationChannelClosedException as ex:
                _logger.info('Task %r is stopping because the communication channel is closed: %r', target, ex)
                await self._handle_connection_loss(ex)
            except Exception as ex:
                _logger.exception('Unhandled exception in the task %r', target)
                await self._handle_connection_loss(ex)
            else:
                _logger.error('Unexpected termination of the task %r', target)
                await self._handle_connection_loss('Unknown reason')    # Should never happen!
            finally:
                _logger.info('Task %r has stopped', target)

        self._event_loop.create_task(proxy())


async def connect(event_loop:                   asyncio.AbstractEventLoop,
                  port_name:                    str,
                  on_connection_loss:           typing.Callable[[typing.Union[str, Exception]], None],
                  on_general_status_update:     typing.Callable[[float, GeneralStatusView], None],
                  on_log_line:                  typing.Callable[[float, str], None],
                  on_progress_report:           typing.Optional[typing.Callable[[str, float], None]],
                  general_status_update_period: float) -> Connection:
    def report(stage: str, progress: float):
        _logger.info('Connection process on port %r reached the new stage %r', port_name, stage)
        # noinspection PyTypeChecker
        assert 0.0 <= progress <= 1.0
        if on_progress_report:
            on_progress_report(stage, progress)

    report('I/O initialization', 0.1)
    com = await Communicator.new(port_name, event_loop)

    try:
        report('Device detection', 0.2)
        node_info = await com.request(popcop.standard.NodeInfoMessage)

        _logger.info('Node info of the connected device: %r', node_info)
        if not node_info:
            raise ConnectionAttemptFailedException('Node info request has timed out')

        assert isinstance(node_info, popcop.standard.NodeInfoMessage)
        if node_info.node_name != 'com.zubax.telega':
            raise IncompatibleDeviceException(f'The connected device is not compatible with this software: '
                                              f'{node_info}')

        if node_info.mode == popcop.standard.NodeInfoMessage.Mode.BOOTLOADER:
            raise IncompatibleDeviceException('The connected device is in the bootloader mode. '
                                              'This mode is not yet supported (but soon will be).')

        if node_info.mode != popcop.standard.NodeInfoMessage.Mode.NORMAL:
            raise IncompatibleDeviceException(f'The connected device is in a wrong mode: {node_info.mode}')

        # Configuring the communicator to use a specific version of the protocol.
        # From now on, we can use the application-specific messages, since the communicator knows how to
        # encode and decode them.
        sw_major_minor = node_info.software_version_major, node_info.software_version_minor
        com.set_protocol_version(sw_major_minor)

        report('Device identification', 0.4)
        characteristics = await com.request(MessageType.DEVICE_CHARACTERISTICS)
        _logger.info('Device characteristics: %r', characteristics)
        if not characteristics:
            raise ConnectionAttemptFailedException('Device capabilities request has timed out')

        report('Device status request', 0.6)
        general_status = await com.request(MessageType.GENERAL_STATUS)
        _logger.info('General status: %r', general_status)
        if not general_status:
            raise ConnectionAttemptFailedException('General status request has timed out')

        device_info = DeviceInfoView.populate(node_info_message=node_info,
                                              characteristics_message=characteristics.fields)
        _logger.info('Populated device info view: %r', device_info)

        report('Completed successfully', 1.0)
    except Exception:
        await com.close()
        raise

    return Connection(event_loop=event_loop,
                      communicator=com,
                      device_info=device_info,
                      general_status_with_ts=(general_status.timestamp,
                                              GeneralStatusView.populate(general_status.fields)),
                      on_connection_loss=on_connection_loss,
                      on_general_status_update=on_general_status_update,
                      on_log_line=on_log_line,
                      general_status_update_period=general_status_update_period)


def _unittest_connection():
    import os
    import pytest
    import glob
    import asyncio

    port_glob = os.environ.get('KUCHER_TEST_PORT', None)
    if not port_glob:
        pytest.skip('Skipping because the environment variable KUCHER_TEST_PORT is not set. '
                    'In order to test the device connection, set that variable to a name or a glob of a serial port. '
                    'If a glob is used, it must evaluate to exactly one port, otherwise the test will fail.')

    port = glob.glob(port_glob)
    assert len(port) == 1, f'The glob was supposed to resolve to exactly one port; got {len(port)} ports.'
    port = port[0]

    loop = asyncio.get_event_loop()

    # noinspection PyProtectedMember
    async def run():
        num_connection_loss_notifications = 0
        num_status_reports = 0

        def on_connection_loss(reason):
            nonlocal num_connection_loss_notifications
            num_connection_loss_notifications += 1
            print(f'Connection lost! Reason: {reason}')

        def on_general_status_update(ts, rep):
            nonlocal num_status_reports
            num_status_reports += 1
            print(f'Status report at {ts}:\n{rep}')

        assert num_status_reports == 0
        assert num_connection_loss_notifications == 0

        print('Connecting...')
        con = await connect(event_loop=loop,
                            port_name=port,
                            on_connection_loss=on_connection_loss,
                            on_general_status_update=on_general_status_update,
                            on_log_line=lambda *args: print('Log line:', *args),
                            on_progress_report=lambda *args: print('Progress report:', *args),
                            general_status_update_period=0.5)
        print('Connected successfully')

        assert num_status_reports == 0
        assert num_connection_loss_notifications == 0

        await asyncio.sleep(con._general_status_update_period * 2 + 0.4, loop=loop)

        assert num_status_reports == 2
        assert num_connection_loss_notifications == 0

        assert 'zubax' in con.device_info.name
        assert con.device_info.characteristics.vsi_model.resistance_per_phase[1].high > 0
        assert con.last_general_status_with_timestamp[0] > 0
        assert con.last_general_status_with_timestamp[1].timestamp > 0

        # Simulate failure of the underlying port
        con._com._ch.close()

        await asyncio.sleep(1, loop=loop)

        assert num_status_reports == 2
        assert num_connection_loss_notifications == 1

    loop.run_until_complete(run())

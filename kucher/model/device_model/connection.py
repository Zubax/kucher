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


class ConnectionAttemptFailedException(ConnectionException):
    pass


class IncompatibleDeviceException(ConnectionAttemptFailedException):
    pass


class Connection:
    def __init__(self,
                 event_loop:                asyncio.AbstractEventLoop,
                 communicator:              Communicator,
                 device_info:               DeviceInfoView,
                 general_status_with_ts:    typing.Tuple[float, GeneralStatusView],
                 on_connection_lost:        typing.Callable[[], None],
                 on_general_status_update:  typing.Callable[[float, GeneralStatusView], None],
                 on_log_line:               typing.Callable[[float, str], None]):
        self._event_loop = event_loop
        self._com: Communicator = communicator
        self._device_info = device_info
        self._last_general_status_with_timestamp = general_status_with_ts

        self._on_connection_lost = on_connection_lost
        self._on_general_status_update = on_general_status_update
        self._on_log_line = on_log_line

        # TODO: Launch the tasks

    @property
    def device_info(self) -> DeviceInfoView:
        return self._device_info

    @property
    def last_general_status_with_timestamp(self) -> typing.Tuple[float, GeneralStatusView]:
        return self._last_general_status_with_timestamp

    async def disconnect(self):
        self._on_connection_lost = lambda: None     # Suppress further reporting

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

    async def _handle_connection_loss(self):
        # noinspection PyBroadException
        try:
            self._on_connection_lost()
        except Exception:
            _logger.exception('Unhandled exception in the connection loss callback')

        await self.disconnect()

    async def _background_task_entry_point(self):
        # noinspection PyBroadException
        try:
            while True:
                pass

        except CommunicationChannelClosedException as ex:
            _logger.info('Background task is stopping because the communication channel is closed: %r', ex)
        except Exception:
            _logger.exception('Unhandled exception in the background task')
        finally:
            self._handle_connection_loss()

    async def _log_reader_entry_point(self):
        # noinspection PyBroadException
        try:
            while True:
                timestamp, text = await self._com.read_log()
                for line in text.splitlines(keepends=True):
                    self._on_log_line(timestamp, line)

        except CommunicationChannelClosedException as ex:
            _logger.info('Log reader task is stopping because the communication channel is closed: %r', ex)
        except Exception:
            _logger.exception('Unhandled exception in the log reader task')
        finally:
            self._handle_connection_loss()


async def connect(event_loop:                  asyncio.AbstractEventLoop,
                  port_name:                   str,
                  on_connection_lost:          typing.Callable[[], None],
                  on_general_status_update:    typing.Callable[[float, GeneralStatusView], None],
                  on_log_line:                 typing.Callable[[float, str], None],
                  on_progress_report:          typing.Optional[typing.Callable[[str], None]]) -> Connection:
    def report(stage: str):
        _logger.info('Connection process on port %r reached the new stage %r', port_name, stage)
        if on_progress_report:
            on_progress_report(stage)

    report('I/O initialization')
    com = await Communicator.new(port_name, event_loop)

    try:
        report('Device detection')
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

        report('Device identification')
        characteristics = await com.request(MessageType.DEVICE_CHARACTERISTICS)
        _logger.info('Device characteristics: %r', characteristics)
        if not characteristics:
            raise ConnectionAttemptFailedException('Device capabilities request has timed out')

        report('Device status request')
        general_status = await com.request(MessageType.GENERAL_STATUS)
        _logger.info('General status: %r', general_status)
        if not general_status:
            raise ConnectionAttemptFailedException('General status request has timed out')

        device_info = DeviceInfoView.populate(node_info_message=node_info,
                                              characteristics_message=characteristics.fields)
        _logger.info('Populated device info view: %r', device_info)

        report('Completed successfully')
    except Exception:
        await com.close()
        raise

    return Connection(event_loop=event_loop,
                      communicator=com,
                      device_info=device_info,
                      general_status_with_ts=(general_status.timestamp,
                                              GeneralStatusView.populate(general_status.fields)),
                      on_connection_lost=on_connection_lost,
                      on_general_status_update=on_general_status_update,
                      on_log_line=on_log_line)

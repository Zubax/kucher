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
from .communicator import Communicator, MessageType, Message
from .device_info_view import DeviceInfoView
from .general_status_view import GeneralStatusView
from ..utils import Event
from logging import getLogger


_logger = getLogger(__name__)


class DeviceModelException(Exception):
    pass


class InvalidStateException(DeviceModelException):
    pass


class ConnectionFailedException(DeviceModelException):
    pass


class IncompatibleDeviceException(ConnectionFailedException):
    pass


class ControlMode(enum.Enum):
    RATIOMETRIC_CURRENT          = enum.auto()
    RATIOMETRIC_ANGULAR_VELOCITY = enum.auto()
    RATIOMETRIC_VOLTAGE          = enum.auto()
    CURRENT                      = enum.auto()
    MECHANICAL_RPM               = enum.auto()
    VOLTAGE                      = enum.auto()


class DeviceModel:
    def __init__(self, event_loop: asyncio.AbstractEventLoop):
        self._event_loop = event_loop

        self._evt_device_status_update = Event()
        self._evt_log_message = Event()
        self._evt_connection_status_change = Event()

        # Inner variable states
        self._com: Communicator = None
        self._device_info = None
        self._last_general_status = None

    @property
    def device_status_update_event(self):
        return self._evt_device_status_update

    @property
    def log_message_event(self):
        """
        This event is invoked when a new log message is received from the device.
        The arguments are local monotonic timestamp in seconds and an str.
        """
        return self._evt_log_message

    @property
    def connection_status_change_event(self):
        """
        The only argument passed to the event handler is an optional DeviceInfoView.
        The argument is None if the connection was lost, and non-none otherwise.
        """
        return self._evt_connection_status_change

    def _ensure_connected(self):
        if not self.is_connected:
            raise InvalidStateException('The requested operation could not be performed because the device '
                                        'connection is not established')

    async def connect(self,
                      port_name: str,
                      progress_report_handler: typing.Optional[typing.Callable[[str], None]]=None):
        def report(stage: str):
            _logger.info('Connection process on port %r reached the new stage %r', port_name, stage)
            if progress_report_handler:
                progress_report_handler(stage)

        # We must wait for completion before establishing a new connection because the new connection could be
        # referring to the same port as the old one.
        await self.disconnect()
        assert not self._device_info

        try:
            report('I/O initialization')
            assert not self._com
            self._com = await Communicator.new(port_name, self._event_loop)

            report('Device detection')
            node_info = await self._com.request(popcop.standard.NodeInfoMessage)

            _logger.info('Node info of the connected device: %r', node_info)
            assert isinstance(node_info, popcop.standard.NodeInfoMessage)
            if not node_info:
                raise ConnectionFailedException('Node info request has timed out')

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
            self._com.set_protocol_version(sw_major_minor)

            report('Device identification')
            characteristics = await self._com.request(MessageType.DEVICE_CHARACTERISTICS)
            _logger.info('Device characteristics: %r', characteristics)
            if not characteristics:
                raise ConnectionFailedException('Device capabilities request has timed out')

            report('Device status request')
            general_status = await self._com.request(MessageType.GENERAL_STATUS)
            _logger.info('General status: %r', general_status)
            if not general_status:
                raise ConnectionFailedException('General status request has timed out')

            device_info = DeviceInfoView.populate(node_info_message=node_info,
                                                  characteristics_message=characteristics.fields)
            _logger.info('Populated device info view: %r', device_info)

            report('Completed successfully')
        except Exception:
            await self.disconnect()
            raise

        self._last_general_status = general_status
        self._device_info = device_info

        self._evt_connection_status_change(self._device_info)
        self._evt_device_status_update(self._last_general_status)

        # TODO: Launch a background task now

    async def disconnect(self):
        if self._device_info:
            self._evt_connection_status_change(None)

        self._device_info = None
        self._last_general_status = None

        if self._com:
            # noinspection PyBroadException
            try:
                await self._com.close()
            except Exception:
                _logger.exception('Could not properly close the old communicator instance; continuing anyway. '
                                  'The communicator is a big boy and should be able to sort its stuff out on its own. '
                                  'Hey communicator, you suck!')
        self._com = None

    @property
    def is_connected(self) -> bool:
        return self._device_info is not None

    @property
    def device_info(self) -> DeviceInfoView:
        return self._device_info or DeviceInfoView()

    @property
    def last_general_status(self) -> GeneralStatusView:
        return self._last_general_status or GeneralStatusView()

    async def set_setpoint(self, value: float, mode: ControlMode):
        self._ensure_connected()

        try:
            converted_mode = {
                ControlMode.RATIOMETRIC_CURRENT:          'ratiometric_current',
                ControlMode.RATIOMETRIC_ANGULAR_VELOCITY: 'ratiometric_angular_velocity',
                ControlMode.RATIOMETRIC_VOLTAGE:          'ratiometric_voltage',
                ControlMode.CURRENT:                      'current',
                ControlMode.MECHANICAL_RPM:               'mechanical_rpm',
                ControlMode.VOLTAGE:                      'voltage',
            }[mode]
        except KeyError:
            raise ValueError(f'Unsupported control mode: {mode}') from None

        await self._com.send(Message(MessageType.SETPOINT, {
            'value': float(value),
            'mode': converted_mode
        }))

    async def stop(self):
        await self.set_setpoint(0, ControlMode.CURRENT)


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

    async def run():
        dm = DeviceModel(loop)

        num_connection_change_notifications = 0
        num_status_reports = 0

        def on_connection_status_changed(device_info):
            nonlocal num_connection_change_notifications
            num_connection_change_notifications += 1
            print(f'Connection status changed! Device info:\n{device_info}')

        def on_status_report(rep):
            nonlocal num_status_reports
            num_status_reports += 1
            print(f'Status report:\n{rep}')

        dm.connection_status_change_event.connect(on_connection_status_changed)
        dm.device_status_update_event.connect(on_status_report)

        assert not dm.is_connected
        assert num_status_reports == 0
        assert num_connection_change_notifications == 0

        await dm.connect(port, lambda *args: print('Progress report:', *args))

        assert dm.is_connected
        assert num_status_reports == 1
        assert num_connection_change_notifications == 1

        await dm.disconnect()

        assert not dm.is_connected
        assert num_status_reports == 1
        assert num_connection_change_notifications == 2

    loop.run_until_complete(run())

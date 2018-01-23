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
import asyncio
import enum
from .communicator import Communicator, MessageType, Message
from .device_info_view import DeviceInfoView
from .general_status_view import GeneralStatusView
from ..utils import Event
from logging import getLogger

__all__ = ['DeviceModel', 'DeviceModelException', 'InvalidDeviceModelStateException']

_logger = getLogger(__name__)


class DeviceModelException(Exception):
    pass


class InvalidDeviceModelStateException(DeviceModelException):
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
        self._com: Communicator = None
        self._device_info = None
        self._last_general_status = None
        self._connected = False

        self._evt_device_status_update = Event()
        self._evt_log_message = Event()
        self._evt_connection_status_change = Event()

    @property
    def device_status_update_event(self):
        return self._evt_device_status_update

    @property
    def log_message_event(self):
        return self._evt_log_message

    @property
    def connection_status_change_event(self):
        return self._evt_connection_status_change

    def _ensure_connected(self):
        if not self._connected:
            raise InvalidDeviceModelStateException('The requested operation could not be performed because the device '
                                                   'connection is not established')

    async def connect(self,
                      port_name: str,
                      progress_report_handler: typing.Optional[typing.Callable[[float, str], None]]):
        progress_report_handler = progress_report_handler if progress_report_handler is not None else (lambda *_: None)

        # We must wait for completion before establishing a new connection because the new connection could be
        # referring to the same port as the old one.
        await self.disconnect()

        _logger.info('Creating new communicator instance for port %r', port_name)
        self._com = await Communicator.new(port_name, self._event_loop)

    async def disconnect(self):
        self._connected = False

        if self._com:
            # noinspection PyBroadException
            try:
                await self._com.close()
            except Exception:
                _logger.exception('Could not properly close the old communicator instance')
            finally:
                self._com = None

        self._com = None
        self._device_info = None

    @property
    def is_connected(self) -> bool:
        return self._connected

    @property
    def device_info(self) -> DeviceInfoView:
        return self._device_info or DeviceInfoView()

    @property
    def last_general_status(self) -> GeneralStatusView:
        return self._last_general_status or GeneralStatusView()

    async def set_setpoint(self, value: float, mode: ControlMode):
        pass

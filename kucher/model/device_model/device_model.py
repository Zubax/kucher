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

import asyncio
from popcop.standard import NodeInfoMessage
from .communicator import Communicator
from .messages import MessageType, Message
from logging import getLogger

__all__ = ['DeviceModel', 'DeviceModelException', 'InvalidDeviceModelStateException', 'DeviceInfo', 'GeneralStatus']

_logger = getLogger(__name__)


class DeviceModelException(Exception):
    pass


class InvalidDeviceModelStateException(DeviceModelException):
    pass


class DeviceInfo:
    class SoftwareVersion:
        def __init__(self, prototype: NodeInfoMessage):
            self.major = prototype.software_version_major
            self.minor = prototype.software_version_minor

    class HardwareVersion:
        pass

    class Capabilities:
        pass

    def __init__(self):
        self._node_info = NodeInfoMessage()
        self._caps = DeviceInfo.Capabilities()

    @property
    def software_version(self) -> SoftwareVersion:
        return self.SoftwareVersion(self._node_info)

    @property
    def capabilities(self) -> Capabilities:
        return self._caps


class GeneralStatus:
    def __init__(self):
        pass


class DeviceModel:
    def __init__(self, event_loop: asyncio.AbstractEventLoop):
        self._event_loop = event_loop
        self._com: Communicator = None
        self._device_info = None
        self._connected = False

    async def _reset(self):
        if self._com:
            # noinspection PyBroadException
            try:
                # We must wait for completion before creating a new instance because the new instance could be
                # referring to the same port as the old one.
                await self._com.close()
            except Exception:
                _logger.error('Could not properly close the old communicator instance', exc_info=True)
            finally:
                self._com = None

        self._com = None
        self._device_info = None

    @property
    def is_connected(self) -> bool:
        return self._connected

    @property
    def device_info(self) -> DeviceInfo:
        if self.is_connected:
            return self._device_info

        raise InvalidDeviceModelStateException('Cannot provide device info because no device is connected')

    async def connect(self, port_name: str):
        await self._reset()
        _logger.info('Creating new communicator instance for port %r', port_name)
        self._com = await Communicator.new(port_name, self._event_loop)

        # TODO: initialization sequence

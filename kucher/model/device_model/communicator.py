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
import threading
from ..utils import synchronized
from .messages import MessageType, Message, Codec

__all__ = ['Communicator']

MAX_PAYLOAD_SIZE = 1024
FRAME_TIMEOUT = 0.5


class Communicator:
    def __init__(self,
                 port_name: str,
                 raw_data_handler_callback: typing.Callable):
        self._lock = threading.RLock()
        self._ch = popcop.physical.serial_multiprocessing.Channel(port_name=port_name,
                                                                  max_payload_size=MAX_PAYLOAD_SIZE,
                                                                  frame_timeout=FRAME_TIMEOUT)
        self._raw_data_sink = raw_data_handler_callback
        self._codec: Codec

    @synchronized
    def send(self,
             message_or_type: typing.Union[Message,
                                           popcop.standard.MessageBase,
                                           typing.Type[popcop.standard.MessageBase]],
             timeout: typing.Optional[typing.Union[float, int]]=None,
             callback: typing.Optional[typing.Callable]=None,
             predicate: typing.Optional[typing.Callable]=None):
        pass

    @synchronized
    def subscribe(self,
                  message_type,
                  callback: typing.Callable,
                  predicate: typing.Optional[typing.Callable]=None):
        pass

    @synchronized
    def poll(self):
        pass

    @synchronized
    def close(self):
        self._ch.close()

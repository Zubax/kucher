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
from kucher.utils import Event
from logging import getLogger
from .communicator import MessageType, Message
from .connection import connect, Connection, ConnectionNotEstablishedException
from .device_info_view import DeviceInfoView
from .general_status_view import GeneralStatusView, TaskID, TaskSpecificStatusReport,\
    ControlMode, MotorIdentificationMode, LowLevelManipulationMode
from .task_statistics_view import TaskStatisticsView
from .commander import Commander
from .register import Register

DEFAULT_GENERAL_STATUS_UPDATE_PERIOD = 0.333


_logger = getLogger(__name__)


class DeviceModelException(Exception):
    pass


class RequestTimedOutException(DeviceModelException):
    pass


class DeviceModel:
    def __init__(self, event_loop: asyncio.AbstractEventLoop):
        self._event_loop = event_loop

        self._conn: Connection = None

        async def send_command(msg: Message):
            self._ensure_connected()
            await self._conn.send(msg)

        self._commander = Commander(send_command)

        self._evt_device_status_update = Event()
        self._evt_log_line = Event()
        self._evt_connection_status_change = Event()
        self._evt_consolidated_register_update = Event()

    @property
    def commander(self) -> Commander:
        return self._commander

    @property
    def device_status_update_event(self) -> Event:
        """
        This event is invoked when a new general status message is obtained from the device.
        The arguments are local monotonic timestamp in seconds and an instance of GeneralStatusView.
        """
        return self._evt_device_status_update

    @property
    def log_line_reception_event(self) -> Event:
        """
        This event is invoked when a new log line is received from the device.
        The arguments are local monotonic timestamp in seconds and an str.
        The new line character at the end of each line, if present, is preserved.
        Note that incomplete lines may be reported as well, e.g.: "Hello ", then "world\n"; the reason is
        that the class attempts to minimize the latency of the data that passes through it.
        The receiver can easily check whether the line is complete or not by checking if there are any of the
        following characters at the end of it (see https://docs.python.org/3/library/stdtypes.html#str.splitlines):
            \n              Line Feed
            \r              Carriage Return
            \r\n            Carriage Return + Line Feed
            \v or \x0b      Line Tabulation
            \f or \x0c      Form Feed
            \x1c            File Separator
            \x1d            Group Separator
            \x1e            Record Separator
            \x85            Next Line (C1 Control Code)
            \u2028          Line Separator
            \u2029          Paragraph Separator
        """
        return self._evt_log_line

    @property
    def connection_status_change_event(self) -> Event:
        """
        The only argument passed to the event handler is a union of either:
            - DeviceInfoView - when connection established;
            - Exception - when connection failed, with the exception object containing the relevant information;
            - str - like above, but the relevant information will be contained in a human-readable string.
        """
        return self._evt_connection_status_change

    @property
    def consolidated_register_update_event(self) -> Event:
        """
        The event argument is a reference to the register instance that has been updated.
        """
        return self._evt_consolidated_register_update

    @property
    def registers(self) -> typing.Dict[str, Register]:
        """
        All known registers with cached values reported by the currently connected device.
        The value cache is fully managed by the device model class.
        If we're not connected, the dict will be empty.
        The contents of the dict is guaranteed to never change as long as the current connection is active.
        """
        return self._conn.registers if self.is_connected else {}

    async def connect(
            self,
            port_name: str,
            on_progress_report: typing.Optional[typing.Callable[[str, float], None]] = None) -> DeviceInfoView:
        await self.disconnect()
        assert not self._conn

        self._conn = await connect(event_loop=self._event_loop,
                                   port_name=port_name,
                                   on_connection_loss=self._on_connection_loss,
                                   on_general_status_update=self._evt_device_status_update,
                                   on_log_line=self._evt_log_line,
                                   on_progress_report=on_progress_report,
                                   general_status_update_period=DEFAULT_GENERAL_STATUS_UPDATE_PERIOD)

        # Connect all registers to the consolidated event handler
        for r in self._conn.registers.values():
            r.update_event.connect(self._evt_consolidated_register_update)

        # noinspection PyTypeChecker
        self._evt_connection_status_change(self._conn.device_info)
        self._evt_device_status_update(*self._conn.last_general_status_with_timestamp)

        return self._conn.device_info

    async def disconnect(self, reason: str = None):
        _logger.info('Explicit disconnect request; reason: %r', reason)
        if self._conn:
            # noinspection PyTypeChecker
            self._evt_connection_status_change(reason or 'Explicit disconnection')
            try:
                await self._conn.disconnect()
            finally:
                self._conn = None

    @property
    def is_connected(self) -> bool:
        return self._conn is not None

    @property
    def device_info(self) -> typing.Optional[DeviceInfoView]:
        if self._conn:
            return self._conn.device_info

    @property
    def last_general_status_with_timestamp(self) -> typing.Optional[typing.Tuple[float, GeneralStatusView]]:
        if self._conn:
            return self._conn.last_general_status_with_timestamp

    async def get_task_statistics(self) -> TaskStatisticsView:
        self._ensure_connected()
        out = await self._conn.request(MessageType.TASK_STATISTICS)
        if out is not None:
            return TaskStatisticsView.populate(out.fields)
        else:
            raise RequestTimedOutException('Task statistics request has timed out')

    def _on_connection_loss(self, reason: typing.Union[str, Exception]):
        _logger.info('Connection instance reported connection loss; reason: %r', reason)
        # The Connection instance will terminate itself, so we don't have to do anything, just clear the reference
        self._conn = None
        # noinspection PyTypeChecker
        self._evt_connection_status_change(reason)

    def _ensure_connected(self):
        if not self.is_connected:
            raise ConnectionNotEstablishedException('The requested operation could not be performed because '
                                                    'the device connection is not established')


def _unittest_device_model_connection():
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

        def on_connection_status_changed(info):
            nonlocal num_connection_change_notifications
            num_connection_change_notifications += 1
            print(f'Connection status changed! Info:\n{info}')

        def on_status_report(ts, rep):
            nonlocal num_status_reports
            num_status_reports += 1
            print(f'Status report at {ts}:\n{rep}')

        dm.connection_status_change_event.connect(on_connection_status_changed)
        dm.device_status_update_event.connect(on_status_report)

        assert not dm.is_connected
        assert num_status_reports == 0
        assert num_connection_change_notifications == 0

        await dm.connect(port, lambda *args: print('Progress report:', *args))

        assert dm.is_connected
        assert num_status_reports == 1
        assert num_connection_change_notifications == 1

        print('Task statistics:')
        print(await dm.get_task_statistics())

        await dm.disconnect()

        with pytest.raises(ConnectionNotEstablishedException):
            await dm.get_task_statistics()

        assert not dm.is_connected
        assert num_status_reports == 1
        assert num_connection_change_notifications == 2

    loop.run_until_complete(run())

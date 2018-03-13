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
import functools
from logging import getLogger
import model.device_model
from model.device_model import DeviceModel, DeviceInfoView, ConnectionNotEstablishedException
from view.main_window import MainWindow
import view.device_model_representation


_logger = getLogger(__name__)


class Fuhrer:
    def __init__(self):
        self._device_model: DeviceModel = DeviceModel(asyncio.get_event_loop())

        self._main_window = MainWindow(on_close=self._on_main_window_close,
                                       on_connection_request=self._on_connection_request,
                                       on_disconnection_request=self._on_disconnection_request,
                                       on_task_statistics_request=_return_none_if_not_connected(
                                           self._device_model.get_task_statistics),
                                       commander=self._device_model.commander)
        self._main_window.show()

        self._device_model.device_status_update_event.connect(self._main_window.on_general_status_update)
        self._device_model.connection_status_change_event.connect(self._on_connection_status_change)
        self._device_model.log_line_reception_event.connect(self._main_window.on_log_line_reception)

        self._should_stop = False

    def _on_main_window_close(self):
        _logger.info('The main window is closing, asking the controller task to stop')
        self._should_stop = True

    def _on_connection_status_change(self, device_info_or_error: typing.Union[DeviceInfoView, str, Exception]):
        if isinstance(device_info_or_error, DeviceInfoView):
            self._main_window.on_connection_established(_make_view_basic_device_info(device_info_or_error),
                                                        list(self._device_model.registers.values()))
        elif isinstance(device_info_or_error, (str, Exception)):
            reason = str(device_info_or_error) or repr(device_info_or_error)    # Some exceptions may not contain text
            self._main_window.on_connection_loss(reason)
        else:
            raise TypeError(f'Invalid argument: {type(device_info_or_error)}')

    async def _on_connection_request(self, port: str) -> view.device_model_representation.BasicDeviceInfo:
        assert not self._device_model.is_connected

        def on_progress_report(stage_description: str, progress: float):
            self._main_window.on_connection_initialization_progress_report(stage_description, progress)

        device_info = await self._device_model.connect(port_name=port, on_progress_report=on_progress_report)

        return _make_view_basic_device_info(device_info)

    async def _on_disconnection_request(self) -> None:
        await self._device_model.disconnect('User request')

    async def run(self):
        # noinspection PyBroadException
        try:
            while not self._should_stop:
                await asyncio.sleep(1)
        except Exception:
            _logger.exception('Unhandled exception in controller task')
        else:
            _logger.info('Controller task is stopping normally')


def _return_none_if_not_connected(target: typing.Callable):
    @functools.wraps(target)
    async def decorator(*args, **kwargs):
        try:
            return await target(*args, **kwargs)
        except ConnectionNotEstablishedException:
            return None

    return decorator


def _make_view_basic_device_info(di: model.device_model.DeviceInfoView) ->\
        view.device_model_representation.BasicDeviceInfo:
    """
    Decouples the model-specific device info representation from the view-specific device info representation.
    """
    return view.device_model_representation.BasicDeviceInfo(
        name=di.name,
        description=di.description,
        build_environment_description=di.build_environment_description,
        runtime_environment_description=di.runtime_environment_description,
        globally_unique_id=di.globally_unique_id,
        software_version=view.device_model_representation.SoftwareVersion(
            major=di.software_version.major,
            minor=di.software_version.minor,
            image_crc=di.software_version.image_crc,
            vcs_commit_id=di.software_version.vcs_commit_id,
            dirty_build=di.software_version.dirty_build,
            release_build=di.software_version.release_build,
            build_timestamp_utc=di.software_version.build_timestamp_utc,
        ),
        hardware_version=view.device_model_representation.HardwareVersion(
            major=di.hardware_version.major,
            minor=di.hardware_version.minor,
        ),
    )

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
from logging import getLogger
from model.device_model import DeviceModel
from view.main_window import MainWindow


_logger = getLogger(__name__)


class Controller:
    def __init__(self):
        self._device_model = DeviceModel(asyncio.get_event_loop())

        self._main_window = MainWindow(self._on_main_window_close)
        self._main_window.show()

        self._should_stop = False

    def _on_main_window_close(self):
        _logger.info('The main window is closing, asking the controller task to stop')
        self._should_stop = True

    async def run(self):
        # noinspection PyBroadException
        try:
            while not self._should_stop:
                await asyncio.sleep(1)
        except Exception:
            _logger.exception('Unhandled exception in controller task')
        else:
            _logger.info('Controller task is stopping normally')

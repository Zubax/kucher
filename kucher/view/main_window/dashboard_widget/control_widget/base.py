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
from PyQt5.QtWidgets import QWidget
from view.device_model_representation import GeneralStatusView


class SpecializedControlWidgetBase(QWidget):
    # noinspection PyArgumentList
    def __init__(self, parent: QWidget):
        super(SpecializedControlWidgetBase, self).__init__(parent)

    def start(self):
        """
        This method is invoked once when the current widget becomes activated.
        """
        raise NotImplementedError

    def stop(self):
        """
        This method is invoked when any event of the listed below happens:

            - The user clicks the STOP button, and the current widget is the active one.
              In this case, the outer container (the piece of logic that calls this method) will invoke the
              STOP command on the device automatically, so the widget doesn't need to worry about that.

            - The current widget is being replaced with a different one.

            - The device connection becomes lost.

        In all cases, the widget shall bring itself back into its default, SAFE state. That means that whichever
        control sliders it has must be returned back to the safe state, e.g. setpoint control slider should be
        set to zero, and so on. This is required to ensure that when the widget gets re-activated again, it will
        be by default in a safe state and won't cause any unexpected activity on the device.
        """
        raise NotImplementedError

    def on_general_status_update(self, timestamp: float, s: GeneralStatusView):
        """
        Invoked whenever the model provides a new status structure received from the device.
        This method is guaranteed to be invoked periodically as long as the device is connected.
        """
        raise NotImplementedError

    @staticmethod
    def _launch_async(coro: typing.Awaitable[None]):
        asyncio.get_event_loop().create_task(coro)

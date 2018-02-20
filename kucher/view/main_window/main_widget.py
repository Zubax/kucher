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

from PyQt5.QtWidgets import QTabWidget, QWidget
from PyQt5.QtGui import QResizeEvent
from ..utils import get_icon
from ..device_model_representation import GeneralStatusView, BasicDeviceInfo, Commander

from .device_management_widget import DeviceManagementWidget,\
    ConnectionRequestCallback, DisconnectionRequestCallback
from .telega_control_widget import TelegaControlWidget
from utils import Event


class MainWidget(QTabWidget):
    def __init__(self,
                 parent:                    QWidget,
                 on_connection_request:     ConnectionRequestCallback,
                 on_disconnection_request:  DisconnectionRequestCallback,
                 commander:                 Commander):
        super(MainWidget, self).__init__(parent)

        self._resize_event = Event()

        self._device_management_widget =\
            DeviceManagementWidget(self,
                                   on_connection_request=on_connection_request,
                                   on_disconnection_request=on_disconnection_request)

        self._telega_control_widget = TelegaControlWidget(self, commander)

        self.addTab(self._device_management_widget, get_icon('connector'), 'Device management')
        self.addTab(self._telega_control_widget, get_icon('wagon'), 'Telega control panel')

        self.setCurrentWidget(self._device_management_widget)

    @property
    def resize_event(self) -> Event:
        return self._resize_event

    def on_connection_established(self, device_info: BasicDeviceInfo):
        self._telega_control_widget.on_connection_established()
        self.setCurrentWidget(self._telega_control_widget)

    def on_connection_loss(self, reason: str):
        self.setCurrentWidget(self._device_management_widget)
        self._device_management_widget.on_connection_loss(reason)
        self._telega_control_widget.on_connection_loss()

    def on_connection_initialization_progress_report(self,
                                                     stage_description: str,
                                                     progress: float):
        self.setCurrentWidget(self._device_management_widget)
        self._device_management_widget.on_connection_initialization_progress_report(stage_description, progress)

    def on_general_status_update(self, timestamp: float, status: GeneralStatusView):
        self._telega_control_widget.on_general_status_update(timestamp, status)

    def resizeEvent(self, event: QResizeEvent):
        super(MainWidget, self).resizeEvent(event)
        self._resize_event.emit()

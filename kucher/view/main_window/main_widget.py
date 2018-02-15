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
from ..utils import get_icon
from ..device_model_representation import GeneralStatusView, BasicDeviceInfo, Commander

from .connection_management_widget import ConnectionManagementWidget,\
    ConnectionRequestCallback, DisconnectionRequestCallback
from .dashboard_widget import DashboardWidget


class MainWidget(QTabWidget):
    def __init__(self,
                 parent:                    QWidget,
                 on_connection_request:     ConnectionRequestCallback,
                 on_disconnection_request:  DisconnectionRequestCallback,
                 commander:                 Commander):
        super(MainWidget, self).__init__(parent)

        self._connection_management_widget =\
            ConnectionManagementWidget(self,
                                       on_connection_request=on_connection_request,
                                       on_disconnection_request=on_disconnection_request)

        self._dashboard_widget = DashboardWidget(self, commander)

        self.addTab(self._connection_management_widget, get_icon('connector'), 'Device management')
        self.addTab(self._dashboard_widget, get_icon('wagon'), 'Telega control panel')

        self.setCurrentWidget(self._connection_management_widget)

    def on_connection_established(self, device_info: BasicDeviceInfo):
        self._dashboard_widget.on_connection_established()
        self.setCurrentWidget(self._dashboard_widget)

    def on_connection_loss(self, reason: str):
        self.setCurrentWidget(self._connection_management_widget)
        self._connection_management_widget.on_connection_loss(reason)
        self._dashboard_widget.on_connection_loss()

    def on_connection_initialization_progress_report(self,
                                                     stage_description: str,
                                                     progress: float):
        self.setCurrentWidget(self._connection_management_widget)
        self._connection_management_widget.on_connection_initialization_progress_report(stage_description, progress)

    def on_general_status_update(self, timestamp: float, status: GeneralStatusView):
        self._dashboard_widget.on_general_status_update(timestamp, status)

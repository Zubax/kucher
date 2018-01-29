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
from PyQt5.QtWidgets import QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QAction
from PyQt5.QtGui import QKeySequence, QDesktopServices, QCloseEvent
from PyQt5.QtCore import QUrl
from ..utils import get_application_icon, get_icon
from .connection_management_widget import ConnectionManagementWidget, ConnectionRequestCallback, \
                                          DisconnectionRequestCallback
from .dc_quantities_widget import DCQuantitiesWidget
from .temperature_widget import TemperatureWidget
from .hardware_flag_counters_widget import HardwareFlagCountersWidget
from .device_time_widget import DeviceTimeWidget
from .vsi_status_widget import VSIStatusWidget
from ..monitored_quantity import MonitoredQuantity
from data_dir import LOG_DIR

# This is an undesirable coupling, but it allows us to avoid excessive code duplication.
# We keep it this way while the codebase is new and fluid. In the future we may want to come up with an
# independent state representation in View, and add a converter into Fuhrer.
from model.device_model import GeneralStatusView


class MainWindow(QMainWindow):
    # noinspection PyCallByClass,PyUnresolvedReferences,PyArgumentList
    def __init__(self,
                 on_close: typing.Callable[[], None],
                 on_connection_request: ConnectionRequestCallback,
                 on_disconnection_request: DisconnectionRequestCallback):
        super(MainWindow, self).__init__()
        self.setWindowTitle('Zubax Kucher')
        self.setWindowIcon(get_application_icon())

        self.statusBar().show()

        self._on_close = on_close

        self._connection_management_widget = \
            ConnectionManagementWidget(self,
                                       on_connection_request=on_connection_request,
                                       on_disconnection_request=on_disconnection_request)

        self._dc_quantities_widget = DCQuantitiesWidget(self)
        self._temperature_widget = TemperatureWidget(self)
        self._hardware_flag_counters_widget = HardwareFlagCountersWidget(self)
        self._device_time_widget = DeviceTimeWidget(self)
        self._vsi_status_widget = VSIStatusWidget(self)

        self._configure_menu()

        # Layout
        central_widget = QWidget(self)

        main_layout = QVBoxLayout()
        main_layout.addWidget(self._connection_management_widget)

        def add_row(*widgets):
            inner = QHBoxLayout()
            for w in widgets:
                inner.addWidget(w)
            main_layout.addLayout(inner)

        add_row(self._dc_quantities_widget,
                self._temperature_widget,
                self._hardware_flag_counters_widget)

        add_row(self._device_time_widget,
                self._vsi_status_widget)

        central_widget.setLayout(main_layout)
        self.setCentralWidget(central_widget)

    # noinspection PyCallByClass,PyUnresolvedReferences,PyArgumentList
    def _configure_menu(self):
        # File menu
        quit_action = QAction(get_icon('exit'), '&Quit', self)
        quit_action.triggered.connect(self._on_close)

        file_menu = self.menuBar().addMenu('&File')
        file_menu.addAction(quit_action)

        # Help menu
        website_action = QAction(get_icon('www'), 'Open Zubax Robotics &website', self)
        website_action.triggered.connect(lambda: QDesktopServices.openUrl(QUrl('https://zubax.com')))

        knowledge_base_action = QAction(get_icon('knowledge'), 'Open Zubax &Knowledge Base website', self)
        knowledge_base_action.triggered.connect(lambda: QDesktopServices.openUrl(QUrl('https://kb.zubax.com')))

        show_log_directory_action = QAction(get_icon('log'), 'Open &log directory', self)
        show_log_directory_action.triggered.connect(lambda: QDesktopServices.openUrl(QUrl.fromLocalFile(LOG_DIR)))

        help_menu = self.menuBar().addMenu('&Help')
        help_menu.addAction(website_action)
        help_menu.addAction(knowledge_base_action)
        help_menu.addAction(show_log_directory_action)
        # help_menu.addAction(about_action)                 # TODO: Implement this

    def on_connection_loss(self, reason: str):
        self._connection_management_widget.on_connection_loss(reason)
        self._dc_quantities_widget.reset()
        self._temperature_widget.reset()
        self._hardware_flag_counters_widget.reset()
        self._device_time_widget.reset()
        self._vsi_status_widget.reset()

    def on_connection_initialization_progress_report(self,
                                                     stage_description: str,
                                                     progress: float):
        self._connection_management_widget.on_connection_initialization_progress_report(stage_description, progress)

    def on_general_status_update(self, timestamp: float, s: GeneralStatusView):
        # DC quantities
        power = s.dc.voltage * s.dc.current
        self._dc_quantities_widget.set(_make_monitored_quantity(s.dc.voltage,
                                                                s.alert_flags.dc_undervoltage,
                                                                s.alert_flags.dc_overvoltage),
                                       _make_monitored_quantity(s.dc.current,
                                                                s.alert_flags.dc_undercurrent,
                                                                s.alert_flags.dc_overcurrent),
                                       power)
        # Temperature
        k2c = s.temperature.convert_kelvin_to_celsius
        self._temperature_widget.set(_make_monitored_quantity(k2c(s.temperature.cpu),
                                                              s.alert_flags.cpu_cold,
                                                              s.alert_flags.cpu_overheating),
                                     _make_monitored_quantity(k2c(s.temperature.vsi),
                                                              s.alert_flags.vsi_cold,
                                                              s.alert_flags.vsi_overheating),
                                     _make_monitored_quantity(k2c(s.temperature.motor) if s.temperature.motor else None,
                                                              s.alert_flags.motor_cold,
                                                              s.alert_flags.motor_overheating))
        # Hardware flags
        hfc_fs = HardwareFlagCountersWidget.FlagState
        # noinspection PyArgumentList
        self._hardware_flag_counters_widget.set(
            lvps_malfunction=hfc_fs(event_count=s.hardware_flag_edge_counters.lvps_malfunction,
                                    active=s.alert_flags.hardware_lvps_malfunction),
            overload=hfc_fs(event_count=s.hardware_flag_edge_counters.overload,
                            active=s.alert_flags.hardware_overload),
            fault=hfc_fs(event_count=s.hardware_flag_edge_counters.fault,
                         active=s.alert_flags.hardware_fault))

        # Device time
        self._device_time_widget.set(s.timestamp)

        # VSI status
        if s.status_flags.vsi_modulating:
            vsi_status = 'modulating'
        elif s.status_flags.vsi_enabled:
            vsi_status = 'armed'
        else:
            vsi_status = 'idle'

        self._vsi_status_widget.set(1 / s.pwm.period,
                                    vsi_status,
                                    s.status_flags.phase_current_agc_high_gain_selected)

    def closeEvent(self, event: QCloseEvent):
        self._on_close()
        event.ignore()


def _make_monitored_quantity(value: float,
                             too_low: bool=False,
                             too_high: bool=False) -> MonitoredQuantity:
    mq = MonitoredQuantity(value)

    if too_low:
        mq.alert = mq.Alert.TOO_LOW

    if too_high:
        mq.alert = mq.Alert.TOO_HIGH

    return mq

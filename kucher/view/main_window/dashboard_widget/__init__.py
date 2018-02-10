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

from PyQt5.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QSizePolicy
from view.widgets import WidgetBase
from view.monitored_quantity import MonitoredQuantity
from view.device_model_representation import GeneralStatusView

from .dc_quantities_widget import DCQuantitiesWidget
from .temperature_widget import TemperatureWidget
from .hardware_flag_counters_widget import HardwareFlagCountersWidget
from .device_time_widget import DeviceTimeWidget
from .vsi_status_widget import VSIStatusWidget
from .active_alerts_widget import ActiveAlertsWidget


class DashboardWidget(WidgetBase):
    def __init__(self, parent: QWidget):
        super(DashboardWidget, self).__init__(parent)

        self._dc_quantities_widget = DCQuantitiesWidget(self)
        self._temperature_widget = TemperatureWidget(self)
        self._hardware_flag_counters_widget = HardwareFlagCountersWidget(self)
        self._device_time_widget = DeviceTimeWidget(self)
        self._vsi_status_widget = VSIStatusWidget(self)
        self._active_alerts_widget = ActiveAlertsWidget(self)

        # Layout
        main_layout = QVBoxLayout()

        # noinspection PyArgumentList
        def add_row(*widgets):
            inner = QHBoxLayout()
            for w in widgets:
                if isinstance(w, tuple):
                    w, stretch = w
                else:
                    w, stretch = w, 0

                inner.addWidget(w, stretch)

            main_layout.addLayout(inner)

        add_row(self._dc_quantities_widget,
                self._temperature_widget,
                self._hardware_flag_counters_widget)

        add_row((self._device_time_widget,   1),
                (self._vsi_status_widget,    2),
                (self._active_alerts_widget, 3))

        self.setLayout(main_layout)

        self.setSizePolicy(QSizePolicy().Minimum, QSizePolicy().Minimum)

    def on_connection_loss(self):
        self._dc_quantities_widget.reset()
        self._temperature_widget.reset()
        self._hardware_flag_counters_widget.reset()
        self._device_time_widget.reset()
        self._vsi_status_widget.reset()
        self._active_alerts_widget.reset()

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

        # Active alerts
        self._active_alerts_widget.set(s.alert_flags)


def _make_monitored_quantity(value: float,
                             too_low: bool=False,
                             too_high: bool=False) -> MonitoredQuantity:
    mq = MonitoredQuantity(value)

    if too_low:
        mq.alert = mq.Alert.TOO_LOW

    if too_high:
        mq.alert = mq.Alert.TOO_HIGH

    return mq

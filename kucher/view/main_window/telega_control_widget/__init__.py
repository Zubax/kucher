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

from PyQt5.QtWidgets import QWidget

from kucher.view.widgets import WidgetBase
from kucher.view.monitored_quantity import MonitoredQuantity
from kucher.view.device_model_representation import GeneralStatusView, Commander
from kucher.view.utils import lay_out_horizontally, lay_out_vertically

from .dc_quantities_widget import DCQuantitiesWidget
from .temperature_widget import TemperatureWidget
from .hardware_flag_counters_widget import HardwareFlagCountersWidget
from .device_status_widget import DeviceStatusWidget
from .vsi_status_widget import VSIStatusWidget
from .active_alerts_widget import ActiveAlertsWidget
from .task_specific_status_widget import TaskSpecificStatusWidget
from .control_widget import ControlWidget


class TelegaControlWidget(WidgetBase):
    def __init__(self,
                 parent:    QWidget,
                 commander: Commander):
        super(TelegaControlWidget, self).__init__(parent)

        self._dc_quantities_widget = DCQuantitiesWidget(self)
        self._temperature_widget = TemperatureWidget(self)
        self._hardware_flag_counters_widget = HardwareFlagCountersWidget(self)
        self._device_status_widget = DeviceStatusWidget(self)
        self._vsi_status_widget = VSIStatusWidget(self)
        self._active_alerts_widget = ActiveAlertsWidget(self)

        self._task_specific_status_widget = TaskSpecificStatusWidget(self)

        self._control_widget = ControlWidget(self, commander)

        self.setLayout(
            lay_out_vertically(
                lay_out_horizontally(
                    (self._dc_quantities_widget, 1),
                    (self._temperature_widget, 1),
                    (self._hardware_flag_counters_widget, 1),
                    (self._vsi_status_widget, 1),
                    (self._active_alerts_widget, 2),
                ),
                lay_out_horizontally(
                    (self._device_status_widget, 1),
                    (self._task_specific_status_widget, 5),
                ),
                self._control_widget,
            ),
        )

    def on_connection_established(self):
        self._control_widget.on_connection_established()

    def on_connection_loss(self):
        self._dc_quantities_widget.reset()
        self._temperature_widget.reset()
        self._hardware_flag_counters_widget.reset()
        self._device_status_widget.reset()
        self._vsi_status_widget.reset()
        self._active_alerts_widget.reset()
        self._task_specific_status_widget.reset()

        self._control_widget.on_connection_loss()

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

        # Device status
        self._device_status_widget.set(s.current_task_id,
                                       s.timestamp)

        # VSI status
        self._vsi_status_widget.set(1 / s.pwm.period,
                                    s.status_flags.vsi_enabled,
                                    s.status_flags.vsi_modulating,
                                    s.status_flags.phase_current_agc_high_gain_selected)

        # Active alerts
        self._active_alerts_widget.set(s.alert_flags)

        # Task-specific
        self._task_specific_status_widget.on_general_status_update(timestamp, s)

        # Control widget
        self._control_widget.on_general_status_update(timestamp, s)


def _make_monitored_quantity(value: float,
                             too_low: bool = False,
                             too_high: bool = False) -> MonitoredQuantity:
    mq = MonitoredQuantity(value)

    if too_low:
        mq.alert = mq.Alert.TOO_LOW

    if too_high:
        mq.alert = mq.Alert.TOO_HIGH

    return mq

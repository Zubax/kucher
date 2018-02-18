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

import enum
import typing
import dataclasses
from decimal import Decimal

__all__ = ['GeneralStatusView', 'TaskID', 'TaskSpecificStatusReport']

_struct_view = dataclasses.dataclass(frozen=True)


class TaskID(enum.Enum):
    IDLE                    = enum.auto()
    FAULT                   = enum.auto()
    BEEPING                 = enum.auto()
    RUNNING                 = enum.auto()
    HARDWARE_TEST           = enum.auto()
    MOTOR_IDENTIFICATION    = enum.auto()
    LOW_LEVEL_MANIPULATION  = enum.auto()


@_struct_view
class TimestampedTaskResult:
    completed_at:   float = 0
    exit_code:      int = 0


@_struct_view
class AlertFlags:
    dc_undervoltage:                        bool = False
    dc_overvoltage:                         bool = False
    dc_undercurrent:                        bool = False
    dc_overcurrent:                         bool = False

    cpu_cold:                               bool = False
    cpu_overheating:                        bool = False
    vsi_cold:                               bool = False
    vsi_overheating:                        bool = False
    motor_cold:                             bool = False
    motor_overheating:                      bool = False

    hardware_lvps_malfunction:              bool = False
    hardware_fault:                         bool = False
    hardware_overload:                      bool = False

    phase_current_measurement_malfunction:  bool = False


@_struct_view
class StatusFlags:
    uavcan_node_up:                         bool = False
    can_data_link_up:                       bool = False

    usb_connected:                          bool = False
    usb_power_supplied:                     bool = False

    rcpwm_signal_detected:                  bool = False

    phase_current_agc_high_gain_selected:   bool = False
    vsi_modulating:                         bool = False
    vsi_enabled:                            bool = False


@_struct_view
class Temperature:          # In Kelvin
    cpu:                float = 0
    vsi:                float = 0
    motor:              float = 0

    @staticmethod
    def convert_kelvin_to_celsius(x: float) -> float:
        return x - 273.15


@_struct_view
class DCQuantities:
    voltage:            float = 0
    current:            float = 0


@_struct_view
class PWMState:
    period:             float = 0
    dead_time:          float = 0
    upper_limit:        float = 0


@_struct_view
class HardwareFlagEdgeCounters:
    lvps_malfunction:   int = 0
    overload:           int = 0
    fault:              int = 0


class TaskSpecificStatusReport:
    @_struct_view
    class Fault:
        failed_task_id:                 TaskID = TaskID.IDLE
        failed_task_exit_code:          int = 0

        @staticmethod
        def populate(fields: typing.Mapping):
            return TaskSpecificStatusReport.Fault(
                failed_task_id=TASK_ID_MAPPING[fields['failed_task_id']][0],
                failed_task_exit_code=fields['failed_task_exit_code'],
            )

    @_struct_view
    class Running:
        stall_count:                    int = 0
        demand_factor:                  float = 0
        # Velocity
        electrical_angular_velocity:    float = 0
        mechanical_angular_velocity:    float = 0
        # Rotating system parameters
        u_dq:                           typing.Tuple[float, float] = (0.0, 0.0)
        i_dq:                           typing.Tuple[float, float] = (0.0, 0.0)
        # Flags
        spinup_in_progress:             bool = False
        rotation_reversed:              bool = False
        controller_saturated:           bool = False

        @staticmethod
        def populate(fields: typing.Mapping):
            def tuplize(what):
                return tuple(x for x in what)

            return TaskSpecificStatusReport.Running(
                stall_count=fields['stall_count'],
                demand_factor=fields['demand_factor'],
                electrical_angular_velocity=fields['electrical_angular_velocity'],
                mechanical_angular_velocity=fields['mechanical_angular_velocity'],
                u_dq=tuplize(fields['u_dq']),
                i_dq=tuplize(fields['i_dq']),
                spinup_in_progress=fields['spinup_in_progress'],
                rotation_reversed=fields['rotation_reversed'],
                controller_saturated=fields['controller_saturated'],
            )

    @_struct_view
    class HardwareTest:
        progress:                       float = 0

        @staticmethod
        def populate(fields: typing.Mapping):
            return TaskSpecificStatusReport.HardwareTest(
                progress=fields['progress'],
            )

    @_struct_view
    class MotorIdentification:
        progress:                       float = 0

        @staticmethod
        def populate(fields: typing.Mapping):
            return TaskSpecificStatusReport.MotorIdentification(
                progress=fields['progress'],
            )

    @_struct_view
    class ManualControl:
        sub_task_id:                    int = 0

        @staticmethod
        def populate(fields: typing.Mapping):
            return TaskSpecificStatusReport.ManualControl(
                sub_task_id=fields['sub_task_id'],
            )

    Union = typing.Union[Fault, Running, HardwareTest, MotorIdentification, ManualControl]


TASK_ID_MAPPING = {
    'idle':                   (TaskID.IDLE,                   None),
    'fault':                  (TaskID.FAULT,                  TaskSpecificStatusReport.Fault),
    'beeping':                (TaskID.BEEPING,                None),
    'running':                (TaskID.RUNNING,                TaskSpecificStatusReport.Running),
    'hardware_test':          (TaskID.HARDWARE_TEST,          TaskSpecificStatusReport.HardwareTest),
    'motor_identification':   (TaskID.MOTOR_IDENTIFICATION,   TaskSpecificStatusReport.MotorIdentification),
    'low_level_manipulation': (TaskID.LOW_LEVEL_MANIPULATION, TaskSpecificStatusReport.ManualControl),
}


@_struct_view
class GeneralStatusView:
    current_task_id:                TaskID = TaskID.IDLE
    timestamp:                      Decimal = Decimal(0)
    alert_flags:                    AlertFlags = AlertFlags()
    status_flags:                   StatusFlags = StatusFlags()
    temperature:                    Temperature = Temperature()
    dc:                             DCQuantities = DCQuantities()
    pwm:                            PWMState = PWMState()
    hardware_flag_edge_counters:    HardwareFlagEdgeCounters = HardwareFlagEdgeCounters()
    task_specific_status_report:    typing.Optional[TaskSpecificStatusReport.Union] = None

    @staticmethod
    def populate(msg: typing.Mapping) -> 'GeneralStatusView':
        task_id, task_specific_type = TASK_ID_MAPPING[msg['current_task_id']]

        def gf(name, default=None):
            out = msg['status_flags'].get(name, default)
            if out is None:
                raise ValueError(f'Flag is not available and default value not provided: {out}')
            return out

        alert_flags = AlertFlags(
            dc_undervoltage=gf('dc_undervoltage'),
            dc_overvoltage=gf('dc_overvoltage'),
            dc_undercurrent=gf('dc_undercurrent'),
            dc_overcurrent=gf('dc_overcurrent'),
            cpu_cold=gf('cpu_cold'),
            cpu_overheating=gf('cpu_overheating'),
            vsi_cold=gf('vsi_cold'),
            vsi_overheating=gf('vsi_overheating'),
            motor_cold=gf('motor_cold'),
            motor_overheating=gf('motor_overheating'),
            hardware_lvps_malfunction=gf('hardware_lvps_malfunction'),
            hardware_fault=gf('hardware_fault'),
            hardware_overload=gf('hardware_overload'),
            phase_current_measurement_malfunction=gf('phase_current_measurement_malfunction'),
        )

        status_flags = StatusFlags(
            uavcan_node_up=gf('uavcan_node_up'),
            can_data_link_up=gf('can_data_link_up'),
            usb_connected=gf('usb_connected'),
            usb_power_supplied=gf('usb_power_supplied'),
            rcpwm_signal_detected=gf('rcpwm_signal_detected'),
            phase_current_agc_high_gain_selected=gf('phase_current_agc_high_gain_selected'),
            vsi_modulating=gf('vsi_modulating'),
            vsi_enabled=gf('vsi_enabled'),
        )

        temperature = Temperature(
            cpu=msg['temperature']['cpu'],
            vsi=msg['temperature']['vsi'],
            motor=msg['temperature']['motor'],
        )

        dc = DCQuantities(
            voltage=msg['dc']['voltage'],
            current=msg['dc']['current'],
        )

        pwm = PWMState(
            period=msg['pwm']['period'],
            dead_time=msg['pwm']['dead_time'],
            upper_limit=msg['pwm']['upper_limit'],
        )

        hardware_flag_edge_counters = HardwareFlagEdgeCounters(
            lvps_malfunction=msg['hardware_flag_edge_counters']['lvps_malfunction'],
            overload=msg['hardware_flag_edge_counters']['overload'],
            fault=msg['hardware_flag_edge_counters']['fault'],
        )

        if task_specific_type:
            task_specific_status_report = task_specific_type.populate(msg['task_specific_status_report'])
        else:
            task_specific_status_report = None

        return GeneralStatusView(
            timestamp=msg['timestamp'],
            current_task_id=task_id,
            alert_flags=alert_flags,
            status_flags=status_flags,
            temperature=temperature,
            dc=dc,
            pwm=pwm,
            hardware_flag_edge_counters=hardware_flag_edge_counters,
            task_specific_status_report=task_specific_status_report,
        )


def _unittest_general_status_view():
    from pytest import approx
    from decimal import Decimal

    sample = {
        'current_task_id':             'idle',
        'dc':                          {'voltage': 14.907779693603516,
                                        'current': 0.0},
        'hardware_flag_edge_counters': {'fault':            0,
                                        'lvps_malfunction': 0,
                                        'overload':         0},
        'pwm':                         {'dead_time':   1.0000000116860974e-07,
                                        'period':      2.1277777705108747e-05,
                                        'upper_limit': 0.8825064897537231},
        'status_flags':                {'can_data_link_up':                      True,
                                        'cpu_cold':                              False,
                                        'cpu_overheating':                       False,
                                        'dc_overcurrent':                        False,
                                        'dc_overvoltage':                        False,
                                        'dc_undercurrent':                       False,
                                        'dc_undervoltage':                       False,
                                        'hardware_fault':                        False,
                                        'hardware_lvps_malfunction':             False,
                                        'hardware_overload':                     False,
                                        'motor_cold':                            False,
                                        'motor_overheating':                     False,
                                        'phase_current_agc_high_gain_selected':  True,
                                        'phase_current_measurement_malfunction': False,
                                        'rcpwm_signal_detected':                 False,
                                        'uavcan_node_up':                        True,
                                        'usb_connected':                         True,
                                        'usb_power_supplied':                    True,
                                        'vsi_cold':                              False,
                                        'vsi_enabled':                           False,
                                        'vsi_modulating':                        False,
                                        'vsi_overheating':                       False},
        'task_specific_status_report': None,
        'temperature':                 {'cpu':   309.573974609375,
                                        'motor': 0.0,
                                        'vsi':   301.93438720703125},
        'timestamp':                   Decimal('14.924033')
    }

    gs = GeneralStatusView.populate(sample)

    assert gs.current_task_id == TaskID.IDLE
    assert gs.timestamp == Decimal('14.924033')

    assert gs.temperature.cpu == approx(309.573974609375)

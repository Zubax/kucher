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
from logging import getLogger
from .communicator import MessageType, Message


SendCommandFunction = typing.Callable[[Message], typing.Awaitable[None]]


_logger = getLogger(__name__)


class ControlMode(enum.Enum):
    RATIOMETRIC_CURRENT          = enum.auto()
    RATIOMETRIC_ANGULAR_VELOCITY = enum.auto()
    RATIOMETRIC_VOLTAGE          = enum.auto()
    CURRENT                      = enum.auto()
    MECHANICAL_RPM               = enum.auto()
    VOLTAGE                      = enum.auto()


class MotorIdentificationMode(enum.Enum):
    R_L     = enum.auto()
    PHI     = enum.auto()
    R_L_PHI = enum.auto()


class LowLevelManipulationMode(enum.Enum):
    CALIBRATION         = enum.auto()
    PHASE_MANIPULATION  = enum.auto()
    SCALAR_CONTROL      = enum.auto()


class Commander:
    def __init__(self, on_command_send: SendCommandFunction):
        self._sender: SendCommandFunction = on_command_send

    async def run(self, mode: ControlMode, value: float):
        try:
            mode = {
                ControlMode.RATIOMETRIC_CURRENT:          'ratiometric_current',
                ControlMode.RATIOMETRIC_ANGULAR_VELOCITY: 'ratiometric_angular_velocity',
                ControlMode.RATIOMETRIC_VOLTAGE:          'ratiometric_voltage',
                ControlMode.CURRENT:                      'current',
                ControlMode.MECHANICAL_RPM:               'mechanical_rpm',
                ControlMode.VOLTAGE:                      'voltage',
            }[mode]
        except KeyError:
            raise ValueError(f'Unsupported control mode: {mode!r}') from None
        else:
            await self._send('running', mode=mode, value=value)

    async def stop(self):
        await self._send('idle')

    async def beep(self, frequency: float, duration: float):
        await self._send('beeping', frequency=frequency, duration=duration)

    async def begin_hardware_test(self):
        await self._send('hardware_test')

    async def begin_motor_identification(self, mode: MotorIdentificationMode):
        try:
            mode = {
                MotorIdentificationMode.R_L:        'r_l',
                MotorIdentificationMode.PHI:        'phi',
                MotorIdentificationMode.R_L_PHI:    'r_l_phi',
            }[mode]
        except KeyError:
            raise ValueError(f'Unsupported motor identification mode: {mode!r}') from None
        else:
            await self._send('motor_identification', mode=mode)

    async def low_level_manipulate(self, mode: LowLevelManipulationMode, *parameters: float):
        parameters = list(map(float, parameters))
        while len(parameters) < 4:
            parameters.append(0.0)

        if len(parameters) > 4:
            raise ValueError(f'Too many parameters: {parameters!r}')

        assert len(parameters) == 4, 'Logic error'

        try:
            mode = {
                LowLevelManipulationMode.CALIBRATION:           'calibration',
                LowLevelManipulationMode.PHASE_MANIPULATION:    'phase_manipulation',
                LowLevelManipulationMode.SCALAR_CONTROL:        'scalar_control',
            }[mode]
        except KeyError:
            raise ValueError(f'Unsupported low-level manipulation mode: {mode!r}') from None
        else:
            await self._send('low_level_manipulation', mode=mode, parameters=parameters)

    async def emergency(self):
        await self._send('fault', magic=0xBADC0FFE)
        _logger.info('Emergency command sent')

    async def _send(self, converted_task_id: str, **kwargs):
        await self._sender(Message(MessageType.COMMAND, {
            'task_id': converted_task_id,
            'task_specific_command': kwargs,
        }))

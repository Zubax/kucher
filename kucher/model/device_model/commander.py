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
from logging import getLogger
from .communicator import MessageType, Message
from .general_status_view import ControlMode, MotorIdentificationMode, LowLevelManipulationMode,\
    CONTROL_MODE_MAPPING, LOW_LEVEL_MANIPULATION_MODE_MAPPING, MOTOR_IDENTIFICATION_MODE_MAPPING


SendCommandFunction = typing.Callable[[Message], typing.Awaitable[None]]


_logger = getLogger(__name__)


class Commander:
    def __init__(self, on_command_send: SendCommandFunction):
        self._sender: SendCommandFunction = on_command_send

        def reverse(d: dict) -> dict:
            return {v: k for k, v in d.items()}

        self._reverse_control_mode_mapping = reverse(CONTROL_MODE_MAPPING)
        self._reverse_llm_mode_mapping = reverse(LOW_LEVEL_MANIPULATION_MODE_MAPPING)
        self._reverse_motor_id_mode_mapping = reverse(MOTOR_IDENTIFICATION_MODE_MAPPING)

    async def run(self, mode: ControlMode, value: float):
        try:
            mode = self._reverse_control_mode_mapping[mode]
        except KeyError:
            raise ValueError(f'Unsupported control mode: {mode!r}') from None
        else:
            await self._send('running', mode=mode, value=float(value))

    async def stop(self):
        _logger.info('Requesting stop')
        await self._send('idle')

    async def beep(self, frequency: float, duration: float):
        frequency = float(frequency)
        duration = float(duration)
        _logger.info(f'Requesting beeping at {frequency:.3f} Hz for {duration:.3} seconds')
        await self._send('beeping', frequency=frequency, duration=duration)

    async def begin_hardware_test(self):
        _logger.info('Requesting hardware test')
        await self._send('hardware_test')

    async def begin_motor_identification(self, mode: MotorIdentificationMode):
        _logger.info(f'Requesting motor ID with mode {mode!r}')
        try:
            mode = self._reverse_motor_id_mode_mapping[mode]
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
            mode = self._reverse_llm_mode_mapping[mode]
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

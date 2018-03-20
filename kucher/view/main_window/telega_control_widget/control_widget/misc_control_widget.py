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
from dataclasses import dataclass
from logging import getLogger
from PyQt5.QtWidgets import QWidget, QDoubleSpinBox, QLabel

from kucher.view.device_model_representation import Commander, GeneralStatusView, TaskID
from kucher.view.utils import make_button, lay_out_horizontally, lay_out_vertically, get_icon_path

from .base import SpecializedControlWidgetBase


_logger = getLogger(__name__)


class MiscControlWidget(SpecializedControlWidgetBase):
    def __init__(self,
                 parent:    QWidget,
                 commander: Commander):
        super(MiscControlWidget, self).__init__(parent)

        self._commander = commander
        self._performer_should_stop = True

        self._frequency_input = QDoubleSpinBox(self)
        self._frequency_input.setRange(100, 15000)
        self._frequency_input.setValue(3000)
        self._frequency_input.setSuffix(' Hz')
        self._frequency_input.setToolTip('Beep frequency, in hertz')
        self._frequency_input.setStatusTip(self._frequency_input.toolTip())

        self._duration_input = QDoubleSpinBox(self)
        self._duration_input.setRange(0.01, 3)
        self._duration_input.setValue(0.5)
        self._duration_input.setSuffix(' s')
        self._duration_input.setToolTip('Beep duration, in seconds')
        self._duration_input.setStatusTip(self._duration_input.toolTip())

        self._go_button = make_button(self,
                                      text='Beep',
                                      icon_name='speaker',
                                      tool_tip='Sends a beep command to the device once',
                                      on_clicked=self._beep_once)

        def stealthy(icon_name: str, music_factory: typing.Callable[[], typing.Iterable['_Note']]) -> QWidget:
            b = make_button(self, icon_name=icon_name, on_clicked=lambda: self._begin_performance(music_factory()))
            b.setFlat(True)
            b.setFixedSize(4, 4)
            return b

        self.setLayout(
            lay_out_vertically(
                lay_out_horizontally(
                    QLabel('Frequency', self),
                    self._frequency_input,
                    QLabel('Duration', self),
                    self._duration_input,
                    self._go_button,
                    (None, 1),
                ),
                (None, 1),
                lay_out_horizontally(
                    (None, 1),
                    stealthy('darth-vader', _get_imperial_march),
                )
            )
        )

    def stop(self):
        self._performer_should_stop = True

    def on_general_status_update(self, timestamp: float, s: GeneralStatusView):
        if s.current_task_id in (TaskID.BEEP,
                                 TaskID.IDLE,
                                 TaskID.FAULT):
            self.setEnabled(True)
        else:
            self._performer_should_stop = True
            self.setEnabled(False)

    def _beep_once(self):
        self._performer_should_stop = True
        self._launch_async(self._commander.beep(frequency=self._frequency_input.value(),
                                                duration=self._duration_input.value()))

    def _begin_performance(self, composition: typing.Iterable['_Note']):
        self._performer_should_stop = False
        self._launch_async(self._perform(composition))

    async def _perform(self, composition: typing.Iterable['_Note']):
        composition = list(composition)
        _logger.info(f'Performer is starting with {len(composition)} notes')
        for note in composition:
            if self._performer_should_stop:
                _logger.info('Performer stopping early because the owner said so')
                break

            if note.frequency > 0:
                # Beep commands are idempotent, so we can repeat each command to be sure that no command gets
                # lost and to prevent timing mismatch issue when we send the next note but the previous one
                # is still being played, leading to the next note being ignored.
                # However, every time a command gets ignored, the device sends back a warning, that may be
                # annoying for the user. So we don't repeat commands, and instead we inject a small additional
                # delay after each note to avoid note loss to bad synchronization.
                await self._commander.beep(frequency=note.frequency, duration=note.duration)

            # The extra delay needed because we're running not on a real-time system
            await asyncio.sleep(note.duration + 0.07)
        else:
            _logger.info('Performer has finished')


@dataclass(frozen=True)
class _Note:
    duration:   float           # second; this field is required
    frequency:  float = 0.0     # hertz; zero means pause


class _OneLineOctave:
    C       = 261.6
    Csharp  = 277.2
    D       = 293.7
    Dsharp  = 311.1
    E       = 329.6
    F       = 349.2
    Fsharp  = 370.0
    G       = 392.0
    Gsharp  = 415.3
    A       = 440.0
    Asharp  = 466.2
    B       = 493.9
    C1      = 523.2
    D1      = 555.4
    E1      = 587.3
    F1      = 622.2
    G1      = 659.2
    A1      = 698.4
    B1      = 739.9
    C2      = 784.0


# noinspection PyArgumentList
def _get_imperial_march() -> typing.List[_Note]:
    n = _Note
    o = _OneLineOctave
    return [
        n(0.350, o.G),
        n(0.350, o.G),
        n(0.350, o.G),
        n(0.250, o.Dsharp),
        n(0.040, o.Asharp),
        n(0.350, o.G),
        n(0.250, o.Dsharp),
        n(0.040, o.Asharp),
        n(0.700, o.G),
        n(0.350, o.E1),
        n(0.350, o.E1),
        n(0.350, o.E1),
        n(0.250, o.F1),
        n(0.040, o.Asharp),
        n(0.350, o.Fsharp),
        n(0.250, o.Dsharp),
        n(0.040, o.Asharp),
        n(0.700, o.G),
        n(0.350, o.C2),
        n(0.250, o.G),
        n(0.040, o.G),
        n(0.350, o.C2),
        n(0.250, o.B1),
        n(0.040, o.A1),
        n(0.040, o.G1),
        n(0.040, o.F1),
        n(0.050, o.G1),
        n(0.040, o.Gsharp),
        n(0.350, o.D1),
        n(0.250, o.C1),
        n(0.040, o.B),
        n(0.040, o.Asharp),
        n(0.040, o.A),
        n(0.050, o.Asharp),
        n(0.040, o.Dsharp),
        n(0.350, o.Fsharp),
        n(0.250, o.Dsharp),
        n(0.040, o.G),
        n(0.350, o.Asharp),
        n(0.250, o.G),
        n(0.040, o.Asharp),
        n(0.700, o.E1),
        n(0.350, o.C2),
        n(0.250, o.G),
        n(0.040, o.G),
        n(0.350, o.C2),
        n(0.250, o.B1),
        n(0.040, o.A1),
        n(0.040, o.G1),
        n(0.040, o.F1),
        n(0.050, o.G1),
        n(0.040, o.Gsharp),
        n(0.350, o.D1),
        n(0.250, o.C1),
        n(0.040, o.B),
        n(0.040, o.A1),
        n(0.040, o.A),
        n(0.050, o.Asharp),
        n(0.040, o.Dsharp),
        n(0.350, o.G),
        n(0.250, o.Dsharp),
        n(0.040, o.Asharp),
        n(0.300, o.G),
        n(0.250, o.Dsharp),
        n(0.040, o.Asharp),
        n(0.700, o.G),
    ]

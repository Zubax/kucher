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
from ..widgets.value_display_group_widget import ValueDisplayGroupWidget


class VSIStatusWidget(ValueDisplayGroupWidget):
    # noinspection PyArgumentList,PyCallingNonCallable
    def __init__(self, parent: QWidget):
        super(VSIStatusWidget, self).__init__(parent, 'VSI status', 'sine')
        self.setToolTip('Voltage Source Inverter status')

        placeholder = 'N/A'

        self._pwm_frequency = self.create_value_display('PWM frequency', placeholder, 'PWM carrier frequency')
        self._vsi_driver_state = self.create_value_display('VSI driver state', placeholder)
        self._current_agc_level = self.create_value_display('Current AGC level', placeholder,
                                                            'Automatic Gain Control on current transducers')

    def set(self,
            pwm_frequency:              float,
            vsi_driver_state_name:      str,
            current_agc_is_high_level:  bool):
        pwm_frequency = '%.1f kHz' % (pwm_frequency * 1e-3)
        self._pwm_frequency.set(pwm_frequency)
        self._vsi_driver_state.set(str(vsi_driver_state_name).capitalize())
        self._current_agc_level.set('High gain' if current_agc_is_high_level else 'Low gain')

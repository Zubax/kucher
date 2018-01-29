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

import math
import enum
import typing
from dataclasses import dataclass
from .widgets.value_display_widget import ValueDisplayWidget
from .utils import gui_test


class MonitoredQuantity:
    class Alert(enum.Enum):
        NONE     = enum.auto()
        TOO_LOW  = enum.auto()
        TOO_HIGH = enum.auto()

    def __init__(self,
                 value: typing.Union[int, float],
                 alert: 'typing.Optional[MonitoredQuantity.Alert]'=None):
        self.value = float(value) if value is not None else None
        self.alert = alert or self.Alert.NONE

    def __float__(self):
        return float(self.value)

    def __int__(self):
        return int(self.value)

    def __str__(self):
        return f'{self.value}({self.alert})'

    __repr__ = __str__


class MonitoredQuantityPresenter:
    @dataclass
    class DisplayParameters:
        comment:    str = None
        icon_name:  str = None
        style:      ValueDisplayWidget = ValueDisplayWidget.Style.NORMAL

    def __init__(self,
                 display_target:    ValueDisplayWidget,
                 format_string:     str,
                 params_default:    DisplayParameters=None,
                 params_when_low:   DisplayParameters=None,
                 params_when_high:  DisplayParameters=None):
        self._display_target = display_target
        self._format_string = format_string
        self._params = {
            MonitoredQuantity.Alert.NONE:     params_default or self.DisplayParameters(),
            MonitoredQuantity.Alert.TOO_LOW:  params_when_low or self.DisplayParameters(),
            MonitoredQuantity.Alert.TOO_HIGH: params_when_high or self.DisplayParameters(),
        }

    def display(self, quantity: typing.Union[int, float, MonitoredQuantity]):
        if not isinstance(quantity, MonitoredQuantity):
            quantity = MonitoredQuantity(quantity)

        if quantity.value is None or math.isnan(quantity.value):
            text = 'N/A'
            params = self.DisplayParameters()
        else:
            text = self._format_string % quantity.value
            params = self._params[quantity.alert]

        # Send over to the widget
        self._display_target.set(text,
                                 style=params.style,
                                 comment=params.comment,
                                 icon_name=params.icon_name)


# noinspection PyArgumentList
@gui_test
def _unittest_monitored_quantity_presenter():
    import time
    from PyQt5.QtWidgets import QApplication, QMainWindow, QGroupBox, QHBoxLayout
    app = QApplication([])

    win = QMainWindow()
    container = QGroupBox(win)
    layout = QHBoxLayout()

    a = ValueDisplayWidget(container, 'Raskolnikov', 'N/A', tooltip='This is Rodion', with_comment=True)
    layout.addWidget(a)

    container.setLayout(layout)
    win.setCentralWidget(container)
    win.show()

    mqp = MonitoredQuantityPresenter(a, '%.1f \u00B0C',
                                     params_default=MonitoredQuantityPresenter.DisplayParameters(comment='OK',
                                                                                                 icon_name='ok'),
                                     params_when_low=MonitoredQuantityPresenter.DisplayParameters(comment='Cold',
                                                                                                  icon_name='cold'),
                                     params_when_high=MonitoredQuantityPresenter.DisplayParameters(comment='Hot',
                                                                                                   icon_name='fire'))

    def run_a_bit():
        for _ in range(1000):
            time.sleep(0.005)
            app.processEvents()

    run_a_bit()
    mqp.display(MonitoredQuantity(123.456, MonitoredQuantity.Alert.NONE))
    run_a_bit()
    mqp.display(MonitoredQuantity(123456, MonitoredQuantity.Alert.TOO_HIGH))
    run_a_bit()
    mqp.display(MonitoredQuantity(-123.456, MonitoredQuantity.Alert.TOO_LOW))
    run_a_bit()

    win.close()

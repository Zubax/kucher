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
from ..utils import gui_test
from ..monitored_quantity import MonitoredQuantity, MonitoredQuantityPresenter
from ..widgets.value_display_group_widget import ValueDisplayGroupWidget, ValueDisplayWidget


class DCQuantitiesWidget(ValueDisplayGroupWidget):
    # noinspection PyArgumentList,PyCallingNonCallable
    def __init__(self, parent: QWidget):
        super(DCQuantitiesWidget, self).__init__(parent,
                                                 'DC quantities',
                                                 'electricity',
                                                 with_comments=True)
        dp = MonitoredQuantityPresenter.DisplayParameters
        style = ValueDisplayWidget.Style
        placeholder = 'N/A'

        self._voltage = MonitoredQuantityPresenter(self.create_value_display('Voltage', placeholder),
                                                   '%.1f V',
                                                   params_default=dp(comment='OK',
                                                                     icon_name='ok'),
                                                   params_when_low=dp(comment='Undervoltage',
                                                                      icon_name='undervoltage',
                                                                      style=style.ALERT_LOW),
                                                   params_when_high=dp(comment='Overvoltage',
                                                                       icon_name='overvoltage',
                                                                       style=style.ALERT_HIGH))

        self._current = MonitoredQuantityPresenter(self.create_value_display('Current', placeholder),
                                                   '%.1f A',
                                                   params_default=dp(comment='OK',
                                                                     icon_name='ok'),
                                                   params_when_low=dp(comment='Regen OC',
                                                                      icon_name='overload-negative',
                                                                      style=style.ALERT_LOW),
                                                   params_when_high=dp(comment='Overcurrent',
                                                                       icon_name='overload',
                                                                       style=style.ALERT_HIGH))

        self._power = MonitoredQuantityPresenter(self.create_value_display('Power', placeholder),
                                                 '%.0f W')

    def set(self,
            voltage: MonitoredQuantity,
            current: MonitoredQuantity,
            power:   float):
        self._voltage.display(voltage)
        self._current.display(current)
        self._power.display(power)


# noinspection PyArgumentList
@gui_test
def _unittest_dc_quantities_widget():
    import time
    from PyQt5.QtWidgets import QApplication, QMainWindow
    app = QApplication([])

    win = QMainWindow()
    a = DCQuantitiesWidget(win)
    win.setCentralWidget(a)
    win.show()

    def run_a_bit():
        for _ in range(1000):
            time.sleep(0.005)
            app.processEvents()

    def do_set(volt, amp):
        a.set(volt, amp, float(volt) * float(amp))

    alert = MonitoredQuantity.Alert

    run_a_bit()
    do_set(12.34, 56.78)
    run_a_bit()
    do_set(MonitoredQuantity(123, alert.TOO_HIGH), MonitoredQuantity(-56.78, alert.TOO_LOW))
    run_a_bit()
    do_set(MonitoredQuantity(9, alert.TOO_LOW), MonitoredQuantity(156.78, alert.TOO_HIGH))
    run_a_bit()

    win.close()

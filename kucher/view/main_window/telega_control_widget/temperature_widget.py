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

from kucher.view.utils import gui_test
from kucher.view.monitored_quantity import MonitoredQuantity, MonitoredQuantityPresenter
from kucher.view.widgets.value_display_group_widget import ValueDisplayGroupWidget, ValueDisplayWidget


class TemperatureWidget(ValueDisplayGroupWidget):
    # noinspection PyArgumentList,PyCallingNonCallable
    def __init__(self, parent: QWidget):
        super(TemperatureWidget, self).__init__(parent,
                                                'Temperature',
                                                'thermometer',
                                                with_comments=True)
        dp = MonitoredQuantityPresenter.DisplayParameters
        style = ValueDisplayWidget.Style
        placeholder = 'N/A'

        default = dp(comment='OK',
                     icon_name='ok')

        when_low = dp(comment='Cold',
                      icon_name='cold',
                      style=style.ALERT_LOW)

        when_high = dp(comment='Overheat',
                       icon_name='fire',
                       style=style.ALERT_HIGH)

        self._cpu = MonitoredQuantityPresenter(self.create_value_display('CPU', placeholder),
                                               '%.0f \u00B0C',
                                               params_default=default,
                                               params_when_low=when_low,
                                               params_when_high=when_high)

        self._vsi = MonitoredQuantityPresenter(self.create_value_display('VSI', placeholder),
                                               '%.0f \u00B0C',
                                               params_default=default,
                                               params_when_low=when_low,
                                               params_when_high=when_high)

        self._motor = MonitoredQuantityPresenter(self.create_value_display('Motor', placeholder),
                                                 '%.0f \u00B0C',
                                                 params_default=default,
                                                 params_when_low=when_low,
                                                 params_when_high=when_high)

    def set(self,
            cpu:    MonitoredQuantity,
            vsi:    MonitoredQuantity,
            motor:  MonitoredQuantity):
        self._cpu.display(cpu)
        self._vsi.display(vsi)
        self._motor.display(motor)


# noinspection PyArgumentList
@gui_test
def _unittest_temperature_widget():
    import time
    from PyQt5.QtWidgets import QApplication, QMainWindow
    app = QApplication([])

    win = QMainWindow()
    a = TemperatureWidget(win)
    win.setCentralWidget(a)
    win.show()

    def run_a_bit():
        for _ in range(1000):
            time.sleep(0.005)
            app.processEvents()

    def do_set(mq):
        a.set(mq, mq, mq)

    alert = MonitoredQuantity.Alert

    run_a_bit()
    do_set(12.34)
    run_a_bit()
    do_set(MonitoredQuantity(123, alert.TOO_HIGH))
    run_a_bit()
    do_set(MonitoredQuantity(-99, alert.TOO_LOW))
    run_a_bit()

    win.close()

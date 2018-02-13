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
from PyQt5.QtWidgets import QWidget, QTabWidget
from view.device_model_representation import Commander
from view.widgets.group_box_widget import GroupBoxWidget
from view.utils import make_button, lay_out_vertically


_logger = getLogger(__name__)


class ControlWidget(GroupBoxWidget):
    def __init__(self,
                 parent:    QWidget,
                 commander: Commander):
        super(ControlWidget, self).__init__(parent, 'Controls', 'adjust')

        self._commander: Commander = commander

        self._tabs = QTabWidget(self)

        self._emergency_button =\
            make_button(self,
                        text='EMERGENCY\nSTOP',
                        tool_tip='Stops the motor unconditionally and locks down the hardware until restarted',
                        on_clicked=self._emergency)
        self._emergency_button.setStyleSheet('''QPushButton {
             background-color: #f33;
             border: 1px solid #800;
             font-weight: 600;
             color: #300;
        }''')

        self.setLayout(
            lay_out_vertically(
                (self._tabs, 1),
                self._emergency_button,
            )
        )

    def _emergency(self):
        pass
        _logger.warning('Emergency button clicked')
        self.window().statusBar().showMessage("DON'T PANIC. The hardware will remain unusable until restarted.")

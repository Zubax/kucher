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
from view.widgets.group_box_widget import GroupBoxWidget
from view.utils import make_button, lay_out_vertically


_logger = getLogger(__name__)


class ControlWidget(GroupBoxWidget):
    def __init__(self, parent: QWidget):
        super(ControlWidget, self).__init__(parent, 'Controls', 'adjust')

        self._tabs = QTabWidget(self)

        self._stop_button = make_button(self,
                                        text='Stop',
                                        icon_name='hand-stop',
                                        tool_tip='Unconditionally send a stop command',
                                        on_clicked=self._do_stop)
        # self._stop_button.setStyleSheet('''QPushButton {
        #      background-color: #f55; border: 1px solid #f00;
        # }''')

        self.setLayout(
            lay_out_vertically(
                (self._tabs, 1),
                self._stop_button,
            )
        )

    def _do_stop(self):
        pass

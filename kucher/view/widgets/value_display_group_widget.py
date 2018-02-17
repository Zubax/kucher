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
from PyQt5.QtWidgets import QWidget, QVBoxLayout, QGroupBox
from ..utils import gui_test, get_icon_path
from .value_display_widget import ValueDisplayWidget
from .group_box_widget import GroupBoxWidget


class ValueDisplayGroupWidget(GroupBoxWidget):
    def __init__(self,
                 parent:        QWidget,
                 title:         str,
                 icon_name:     typing.Optional[str]=None,
                 with_comments: bool=False):
        super(ValueDisplayGroupWidget, self).__init__(parent, title, icon_name)

        self._with_comments = with_comments
        self._inferiors: typing.List[ValueDisplayWidget] = []
        self._inferior_layout = QVBoxLayout()
        self.setLayout(self._inferior_layout)

    # noinspection PyArgumentList
    def create_value_display(self,
                             title:            str,
                             placeholder_text: typing.Optional[str]=None,
                             tooltip:          typing.Optional[str]=None) -> ValueDisplayWidget:
        inferior = ValueDisplayWidget(self,
                                      title,
                                      placeholder_text=placeholder_text,
                                      with_comment=self._with_comments,
                                      tooltip=tooltip)
        self._inferiors.append(inferior)
        self._inferior_layout.addWidget(inferior, stretch=1)
        return inferior

    def reset(self):
        for inf in self._inferiors:
            inf.reset()


# noinspection PyArgumentList
@gui_test
def _unittest_value_display_group_widget():
    import time
    from PyQt5.QtWidgets import QApplication, QMainWindow
    app = QApplication([])

    win = QMainWindow()

    midget = ValueDisplayGroupWidget(win, 'Temperature', icon_name='thermometer', with_comments=True)

    cpu = midget.create_value_display('CPU', 'N/A')
    vsi = midget.create_value_display('VSI', 'N/A')
    motor = midget.create_value_display('Motor', 'N/A')

    win.setCentralWidget(midget)
    win.show()

    def run_a_bit():
        for _ in range(1000):
            time.sleep(0.005)
            app.processEvents()

    run_a_bit()

    cpu.set('12', comment='OK', icon_name='ok')
    vsi.set('123', comment='Overheating', icon_name='fire')
    motor.set('-123', comment='Cold', icon_name='cold')

    run_a_bit()

    win.close()

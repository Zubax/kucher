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

from PyQt5.QtWidgets import QWidget, QLabel, QVBoxLayout
from PyQt5.QtCore import Qt
from ..widgets.group_box_widget import GroupBoxWidget
from ..utils import get_monospace_font, gui_test


_ICON_OK = 'ok-strong'
_ICON_ALERT = 'error'


class ActiveAlertsWidget(GroupBoxWidget):
    # noinspection PyArgumentList,PyCallingNonCallable
    def __init__(self, parent: QWidget):
        super(ActiveAlertsWidget, self).__init__(parent, 'Active alerts', _ICON_OK)

        self._content = QLabel()
        self._content.setWordWrap(True)
        self._content.setAlignment(Qt.AlignCenter)

        font = get_monospace_font()
        font.setBold(True)
        font.setPointSize(int(font.pointSize() * 0.8))
        self._content.setFont(font)

        layout = QVBoxLayout()
        layout.addStretch(1)
        layout.addWidget(self._content)
        layout.addStretch(1)
        self.setLayout(layout)

        self.reset()

    def reset(self):
        self.set(object())

    def set(self, flags):
        attrs = []

        for at in dir(flags):
            if at.startswith('_'):
                continue
            val = getattr(flags, at)
            if not isinstance(val, bool):
                continue
            if val:
                attrs.append(at.replace('_', ' '))

        text = '\n'.join(attrs).upper()

        # Changing icons is very expensive
        if text != str(self._content.text()):
            if text:
                self._content.setText(text)
                self.set_icon(_ICON_ALERT)
            else:
                self._content.setText('')
                self.set_icon(_ICON_OK)


# noinspection PyArgumentList
@gui_test
def _unittest_active_alerts_widget():
    from dataclasses import dataclass
    import time
    from PyQt5.QtWidgets import QApplication, QMainWindow
    app = QApplication([])

    win = QMainWindow()
    a = ActiveAlertsWidget(win)
    win.setCentralWidget(a)
    win.show()

    def run_a_bit():
        for _ in range(1000):
            time.sleep(0.005)
            app.processEvents()

    @dataclass
    class Instance:
        flag_a:         bool = False
        flag_b_too:     bool = False
        flag_c_as_well: bool = False

    run_a_bit()
    a.set(Instance())
    run_a_bit()
    a.set(Instance(flag_a=True, flag_c_as_well=True, flag_b_too=True))
    run_a_bit()
    a.set(Instance(flag_a=True, flag_c_as_well=True))
    run_a_bit()
    a.reset()
    run_a_bit()

    win.close()

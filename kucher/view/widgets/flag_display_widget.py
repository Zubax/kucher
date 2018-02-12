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
from dataclasses import dataclass
from logging import getLogger
from PyQt5.QtWidgets import QWidget, QLabel
from PyQt5.QtGui import QFont, QFontMetrics, QPixmap
from PyQt5.QtCore import Qt
from ..utils import gui_test, get_icon, lay_out_horizontally
from . import WidgetBase


_logger = getLogger(__name__)


class FlagDisplayWidget(WidgetBase):
    @dataclass
    class StateDefinition:
        icon_name:      str = ''
        text:           str = ''

    # noinspection PyArgumentList
    def __init__(self,
                 parent: QWidget,
                 state_when_cleared: StateDefinition,
                 state_when_set: StateDefinition,
                 state_when_undefined: StateDefinition=StateDefinition()):
        super(FlagDisplayWidget, self).__init__(parent)

        self._icon_label = QLabel(self)

        self._text_label = QLabel(self)
        self._text_label.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)

        icon_height = QFontMetrics(QFont()).height()

        def render_icon(icon_name: str) -> QPixmap:
            return get_icon(icon_name).pixmap(icon_height, icon_height)

        def render_state(s: self.StateDefinition) -> tuple:
            pixmap = render_icon(s.icon_name) if s.icon_name else None
            return pixmap, s.text

        self._params_when_cleared = render_state(state_when_cleared)
        self._params_when_set = render_state(state_when_set)
        self._params_when_undefined = render_state(state_when_undefined)

        self.setLayout(lay_out_horizontally(self._icon_label,
                                            (self._text_label, 1)))

    def set(self, value: bool):
        self._assign(*(self._params_when_set if value else self._params_when_cleared))

    def reset(self):
        self._assign(*self._params_when_undefined)

    def _assign(self, pixmap: typing.Optional[QPixmap], text: str):
        self._text_label.setText(text)
        if pixmap:
            self._icon_label.setPixmap(pixmap)
        else:
            self._icon_label.setPixmap(QPixmap())


# noinspection PyArgumentList
@gui_test
def _unittest_flag_display_widget():
    import time
    from PyQt5.QtWidgets import QApplication, QMainWindow
    app = QApplication([])

    win = QMainWindow()

    fd = FlagDisplayWidget(win,
                           FlagDisplayWidget.StateDefinition(icon_name='cold', text='Cleared'),
                           FlagDisplayWidget.StateDefinition(icon_name='fire', text='Set'))

    win.setCentralWidget(fd)
    win.show()

    def run_a_bit():
        for _ in range(1000):
            time.sleep(0.005)
            app.processEvents()

    run_a_bit()
    fd.set(False)
    run_a_bit()
    fd.set(True)
    run_a_bit()
    fd.set(False)
    run_a_bit()
    fd.reset()
    run_a_bit()

    win.close()

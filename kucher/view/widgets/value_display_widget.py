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
import enum
from logging import getLogger
from PyQt5.QtWidgets import QWidget, QHBoxLayout, QStackedLayout, QLabel
from PyQt5.QtWidgets import QVBoxLayout, QFrame, QSizePolicy
from PyQt5.QtGui import QIcon, QPalette, QFont, QFontMetrics
from PyQt5.QtCore import QTimer, Qt
from ..utils import gui_test, get_icon
from . import WidgetBase


_logger = getLogger(__name__)


class ValueDisplayWidget(WidgetBase):
    class AlertStyle(enum.Enum):
        HIGH = enum.auto()
        LOW  = enum.auto()

    @dataclass
    class State:
        comment:        typing.Optional[str] = None
        icon:           typing.Optional[QIcon] = None
        alert_style:    typing.Optional['ValueDisplayWidget.AlertStyle'] = None

    def __init__(self,
                 parent: QWidget,
                 title: str,
                 states: typing.Dict[str, 'ValueDisplayWidget.State'],
                 units_of_measurement: typing.Optional[str]=None,
                 decimal_places: typing.Optional[int]=None,
                 placeholder_text: typing.Optional[str]=None):
        super(ValueDisplayWidget, self).__init__(parent)

        self._states = states
        self._value_display = QLabel()
        self._comment_layout = QStackedLayout()

        if decimal_places is not None:
            format_string = f'%.{int(decimal_places)}f'
        else:
            format_string = '%s'

        if units_of_measurement is not None:
            format_string += f' {str(units_of_measurement)}'

        self._format_string = format_string

        self._placeholder_text = str(placeholder_text or '')

        layout = QVBoxLayout()
        layout.addWidget(QLabel(title))
        layout.addWidget(self._value_display)
        layout.addLayout(self._comment_layout)
        self.setLayout(layout)

        self.setFixedHeight(layout.minimumHeightForWidth(100))

    def reset(self):
        self._value_display.setText(self._placeholder_text)

    def set(self,
            value,
            state: typing.Optional[str]=None):
        pass


class _Comment(WidgetBase):
    def __init__(self,
                 parent: QWidget,
                 text: str,
                 icon: typing.Optional[QIcon]):
        super(_Comment, self).__init__(parent)

        layout = QHBoxLayout()
        layout.addStretch(1)

        # https://doc.qt.io/qt-5.10/qtwidgets-widgets-icons-example.html
        if icon:
            # Determine the required size of the icon using the application's default font
            icon_size = QFontMetrics(QFont()).height()

            # Render the icon into a new pixmap of the specified size
            icon_label = QLabel()
            icon_label.setAlignment(Qt.AlignCenter)
            icon_label.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
            icon_label.setPixmap(icon.pixmap(icon_size, icon_size))

            # Add the rendered icon to the layout
            layout.addWidget(icon_label, stretch=0)

        layout.addWidget(QLabel(text), stretch=0)
        layout.addStretch(1)
        self.setLayout(layout)


@gui_test
def _unittest_value_display_widget_comment():
    import time
    from PyQt5.QtWidgets import QApplication, QMainWindow, QGroupBox
    app = QApplication([])

    win = QMainWindow()
    container = QGroupBox(win)
    layout = QVBoxLayout()

    layout.addWidget(_Comment(container, 'Cold', get_icon('cold')))
    layout.addWidget(_Comment(container, 'Fire', get_icon('fire')))
    layout.addWidget(_Comment(container, 'Error', get_icon('error')))
    layout.addWidget(_Comment(container, 'Warning', get_icon('warning')))
    layout.addWidget(_Comment(container, 'Ok', get_icon('ok')))
    layout.addWidget(_Comment(container, 'No icon', None))

    container.setLayout(layout)
    win.setCentralWidget(container)
    win.show()

    def run_a_bit():
        for _ in range(1000):
            time.sleep(0.005)
            app.processEvents()

    run_a_bit()

    win.close()

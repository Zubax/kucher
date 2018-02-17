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

import enum
import typing
import warnings
import functools
from logging import getLogger
from PyQt5.QtWidgets import QWidget, QHBoxLayout, QLabel
from PyQt5.QtWidgets import QVBoxLayout
from PyQt5.QtGui import QFont, QFontMetrics, QPixmap
from PyQt5.QtCore import Qt
from ..utils import gui_test, get_icon, is_small_screen
from . import WidgetBase


_logger = getLogger(__name__)


class ValueDisplayWidget(WidgetBase):
    class Style(enum.Enum):
        NORMAL      = enum.auto()
        ALERT_ERROR = enum.auto()
        ALERT_HIGH  = enum.auto()
        ALERT_LOW   = enum.auto()

    # noinspection PyArgumentList
    def __init__(self,
                 parent: QWidget,
                 title: str,
                 placeholder_text: typing.Optional[str]=None,
                 with_comment: bool=False,
                 tooltip: typing.Optional[str]=None):
        super(ValueDisplayWidget, self).__init__(parent)

        self._placeholder_text = str(placeholder_text or '')

        self._value_display = QLabel(self)
        self._value_display.setAlignment(Qt.AlignVCenter | Qt.AlignRight)
        bold_font = QFont()
        bold_font.setBold(True)
        self._value_display.setFont(bold_font)

        if with_comment:
            self._comment = _Comment(self)
        else:
            self._comment = None

        self._default_tooltip = str(tooltip or '')
        self.setToolTip(self._default_tooltip)
        self.setStatusTip(self.toolTip())

        title_label = QLabel(title)
        title_label.setAlignment(Qt.AlignVCenter | Qt.AlignLeft)

        layout = QHBoxLayout()
        layout.addWidget(title_label, 1)
        layout.addWidget(self._value_display, 1)
        if self._comment is not None:
            layout.addWidget(self._comment)

        layout.setContentsMargins(0, 0, 0, 0)
        self.setLayout(layout)
        self.reset()

    def reset(self):
        # TODO: handle style
        self._value_display.setText(self._placeholder_text)
        self.setToolTip(self._default_tooltip)
        self.setStatusTip(self.toolTip())
        if isinstance(self._comment, _Comment):
            self._comment.reset()

    def set(self,
            text:       str,
            style:     'typing.Optional[ValueDisplayWidget.Style]'=None,
            comment:    typing.Optional[str]=None,
            icon_name:  typing.Optional[str]=None):
        # TODO: handle style
        style = style or self.Style.NORMAL

        self._value_display.setText(text)

        if isinstance(self._comment, _Comment):
            self._comment.set_text(comment)
            self._comment.set_icon(icon_name)
        elif comment or icon_name:
            warnings.warn('Attempting to set comment, but the instance is configured to not use one')


# noinspection PyArgumentList
@gui_test
def _unittest_value_display_widget_main():
    import time
    from PyQt5.QtWidgets import QApplication, QMainWindow, QGroupBox
    app = QApplication([])

    win = QMainWindow()
    container = QGroupBox(win)
    layout = QVBoxLayout()

    a = ValueDisplayWidget(container, 'Vladimir', 'N/A', tooltip='This is Vladimir')
    layout.addWidget(a)

    b = ValueDisplayWidget(container, 'Dmitri', with_comment=True)
    b.set('123.4 \u00B0C', comment='Init', icon_name='info')
    layout.addWidget(b)

    container.setLayout(layout)
    win.setCentralWidget(container)
    win.show()

    def run_a_bit():
        for _ in range(1000):
            time.sleep(0.005)
            app.processEvents()

    run_a_bit()
    b.set('12.3 \u00B0C', comment='OK', icon_name='ok')
    run_a_bit()
    b.set('123.4 \u00B0C')
    run_a_bit()
    b.set('-45.6 \u00B0C', comment='Cold', icon_name='cold')
    run_a_bit()

    win.close()


class _Comment(QLabel):
    # noinspection PyArgumentList
    def __init__(self, parent: QWidget):
        super(_Comment, self).__init__(parent)
        self.setAlignment(Qt.AlignCenter)
        self._icon_size = QFontMetrics(QFont()).height()        # As large as font
        self._pixmap_cache: typing.Dict[str, QPixmap] = {}
        self._current_icon_name: typing.Optional[str] = None
        # Initializing defaults
        self.reset()

    def reset(self):
        self.set_text(None)
        self.set_icon(None)

    def set_icon(self, icon_name: typing.Optional[str]):
        icon_name = str(icon_name or '_empty')
        if icon_name == self._current_icon_name:
            return

        try:
            pixmap = self._pixmap_cache[icon_name]
        except KeyError:
            icon = get_icon(icon_name)
            pixmap = icon.pixmap(self._icon_size, self._icon_size)
            self._pixmap_cache[icon_name] = pixmap

        self.setPixmap(pixmap)
        self._current_icon_name = icon_name

    def set_text(self, text: typing.Optional[str]):
        text = str(text or '')
        self.setToolTip(text)
        self.setStatusTip(text)


# noinspection PyArgumentList
@gui_test
def _unittest_value_display_widget_comment():
    import time
    from PyQt5.QtWidgets import QApplication, QMainWindow, QGroupBox
    app = QApplication([])

    win = QMainWindow()
    container = QGroupBox(win)
    layout = QVBoxLayout()
    layout.addStretch(1)

    # noinspection PyArgumentList
    def let_there_be_icon(text, icon_name):
        s = _Comment(container)
        s.set_text(text)
        s.set_icon(icon_name)
        layout.addWidget(s)
        return s

    a = let_there_be_icon('Cold', 'cold')
    b = let_there_be_icon(None, None)
    c = let_there_be_icon(None, 'info')
    let_there_be_icon('No icon', None)
    let_there_be_icon('Fire', 'fire')
    let_there_be_icon('Error', 'error')
    let_there_be_icon('Warning', 'warning')
    let_there_be_icon('Ok', 'ok')

    layout.addStretch(1)
    container.setLayout(layout)
    win.setCentralWidget(container)
    win.show()

    def run_a_bit():
        for _ in range(1000):
            time.sleep(0.005)
            app.processEvents()

    run_a_bit()
    a.set_icon('fire')
    b.set_text('Text')
    c.set_text('New icon')
    c.set_icon('guru')
    run_a_bit()
    c.set_icon(None)
    b.set_text('Text')
    a.set_text('New icon')
    a.set_icon(None)
    run_a_bit()

    win.close()

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
from PyQt5.QtWidgets import QVBoxLayout, QSizePolicy
from PyQt5.QtGui import QFont, QFontMetrics, QPixmap
from PyQt5.QtCore import Qt
from ..utils import gui_test, get_icon
from . import WidgetBase


_logger = getLogger(__name__)


@functools.lru_cache()
def _get_large_font() -> QFont:
    font = QFont()
    font.setPointSize(int(font.pointSize() * 1.5 + 0.5))
    return font


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
                 with_subscript: bool=False,
                 tooltip: typing.Optional[str]=None):
        super(ValueDisplayWidget, self).__init__(parent)

        self._placeholder_text = str(placeholder_text or '')

        self._value_display = QLabel()
        self._value_display.setAlignment(Qt.AlignCenter)
        self._value_display.setFont(_get_large_font())

        if with_subscript:
            self._subscript = _Subscript(self)
        else:
            self._subscript = None

        if tooltip:
            self.setToolTip(tooltip)

        title_label = QLabel(title)
        title_label.setAlignment(Qt.AlignCenter)

        layout = QVBoxLayout()
        layout.addWidget(title_label)
        layout.addWidget(self._value_display)

        if self._subscript is not None:
            layout.addWidget(self._subscript)

        layout.addStretch(1)        # Keeping the widget tight and top-aligned

        # We add another layer of layout on top in order to keep the widget tightly laid out
        outer_layout = QHBoxLayout()
        outer_layout.addStretch(1)
        outer_layout.addLayout(layout)
        outer_layout.addStretch(1)
        self.setLayout(outer_layout)

        self.reset()

    def reset(self):
        # TODO: handle style
        self._value_display.setText(self._placeholder_text)
        if isinstance(self._subscript, _Subscript):
            self._subscript.reset()

    def set(self,
            text: str,
            style: 'typing.Optional[ValueDisplayWidget.Style]'=None,
            subscript_text: typing.Optional[str]=None,
            subscript_icon_name: typing.Optional[str]=None):
        # TODO: handle style
        style = style or self.Style.NORMAL

        self._value_display.setText(text)

        if isinstance(self._subscript, _Subscript):
            self._subscript.set_text(subscript_text)
            self._subscript.set_icon(subscript_icon_name)
        elif subscript_text or subscript_icon_name:
            warnings.warn('Attempting to set subscript, but the instance is configured to not use one')


# noinspection PyArgumentList
@gui_test
def _unittest_value_display_widget_main():
    import time
    from PyQt5.QtWidgets import QApplication, QMainWindow, QGroupBox
    app = QApplication([])

    win = QMainWindow()
    container = QGroupBox(win)
    layout = QHBoxLayout()

    a = ValueDisplayWidget(container, 'Vladimir', 'N/A', tooltip='This is Vladimir')
    layout.addWidget(a)

    b = ValueDisplayWidget(container, 'Dmitri', with_subscript=True)
    b.set('123.4 \u00B0C', subscript_text='Init', subscript_icon_name='info')
    layout.addWidget(b)

    container.setLayout(layout)
    win.setCentralWidget(container)
    win.show()

    def run_a_bit():
        for _ in range(1000):
            time.sleep(0.005)
            app.processEvents()

    run_a_bit()
    b.set('12.3 \u00B0C', subscript_text='OK', subscript_icon_name='ok')
    run_a_bit()
    b.set('123.4 \u00B0C')
    run_a_bit()
    b.set('-45.6 \u00B0C', subscript_text='Cold', subscript_icon_name='cold')
    run_a_bit()

    win.close()


class _Subscript(WidgetBase):
    # noinspection PyArgumentList
    def __init__(self, parent: QWidget):
        super(_Subscript, self).__init__(parent)

        self._text_label = QLabel(self)

        self._icon_label = QLabel()
        self._icon_label.setAlignment(Qt.AlignCenter)
        self._icon_label.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

        self._icon_size = QFontMetrics(QFont()).height()        # As large as font
        self._pixmap_cache: typing.Dict[str, QPixmap] = {}
        self._current_icon_name: typing.Optional[str] = None

        layout = QHBoxLayout()
        layout.addStretch(1)
        layout.addWidget(self._icon_label, stretch=0)
        layout.addWidget(self._text_label, stretch=0)
        layout.addStretch(1)
        layout.setContentsMargins(0, 0, 0, 0)
        self.setLayout(layout)

    def reset(self):
        self.set_text(None)
        self.set_icon(None)

    def set_icon(self, icon_name: typing.Optional[str]):
        if icon_name == self._current_icon_name:
            return

        if icon_name:
            try:
                pixmap = self._pixmap_cache[icon_name]
            except KeyError:
                icon = get_icon(icon_name)
                pixmap = icon.pixmap(self._icon_size, self._icon_size)
                self._pixmap_cache[icon_name] = pixmap

            self._icon_label.setPixmap(pixmap)
        else:
            self._icon_label.setPixmap(QPixmap())

        self._current_icon_name = icon_name

    def set_text(self, text: typing.Optional[str]):
        self._text_label.setText(text or '')


# noinspection PyArgumentList
@gui_test
def _unittest_value_display_widget_subscript():
    import time
    from PyQt5.QtWidgets import QApplication, QMainWindow, QGroupBox
    app = QApplication([])

    win = QMainWindow()
    container = QGroupBox(win)
    layout = QVBoxLayout()
    layout.addStretch(1)

    # noinspection PyArgumentList
    def let_there_be_icon(text, icon_name):
        s = _Subscript(container)
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

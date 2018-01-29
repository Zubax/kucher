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

import os
import time
import typing
import functools
from logging import getLogger
from PyQt5.QtWidgets import QWidget, QPushButton, QMessageBox
from PyQt5.QtGui import QFont, QFontInfo, QIcon
from PyQt5.QtCore import Qt
from resources import get_absolute_path


_logger = getLogger(__name__)


def get_application_icon() -> QIcon:
    return QIcon(get_absolute_path('view', 'icons', 'zee-with-margins.png'))


@functools.lru_cache(None)
def get_icon(name: str) -> QIcon:
    return QIcon(get_absolute_path('view', 'icons', f'{name}.png'))


@functools.lru_cache()
def get_monospace_font() -> QFont:
    preferred = ['Consolas', 'DejaVu Sans Mono', 'Monospace', 'Lucida Console', 'Monaco']
    for name in preferred:
        font = QFont(name)
        if QFontInfo(font).fixedPitch():
            _logger.info('Selected monospace font: %r', font.toString())
            return font

    font = QFont()
    font.setStyleHint(QFont().Monospace)
    font.setFamily('monospace')
    _logger.info('Using fallback monospace font: %r', font.toString())
    return font


def make_button(parent: QWidget,
                text: str='',
                icon_name: typing.Optional[str]=None,
                tool_tip: typing.Optional[str]=None,
                checkable: bool=False,
                checked: bool=False,
                on_clicked: typing.Callable[[], None]=None) -> QPushButton:
    b = QPushButton(text, parent)
    b.setFocusPolicy(Qt.NoFocus)
    if icon_name:
        b.setIcon(get_icon(icon_name))

    if tool_tip:
        b.setToolTip(tool_tip)

    if checked and not checkable:
        checkable = True
        _logger.error(f'A checked button must be checkable! text={text} icon_name={icon_name}')

    if checkable:
        b.setCheckable(True)
        b.setChecked(checked)

    if on_clicked:
        b.clicked.connect(on_clicked)

    return b


def show_error(title: str,
               text: str,
               informative_text: str,
               parent: typing.Optional[QWidget]) -> QMessageBox:
    _logger.exception('Error window: title=%r, text=%r, informative_text=%r, parent=%r',
                      title, text, informative_text, parent)

    mbox = QMessageBox(parent)

    mbox.setWindowTitle(str(title))
    mbox.setText(str(text))
    if informative_text:
        mbox.setInformativeText(str(informative_text))

    mbox.setIcon(QMessageBox.Critical)
    mbox.setStandardButtons(QMessageBox.Ok)

    mbox.show()     # Not exec() because we don't want it to block!

    return mbox


def time_tracked(target: typing.Callable):
    """
    Execution time of functions wrapped in this decorator will be logged at the debug level.
    Note that if the wrapped function throws, the statistics is not updated and not logged.
    """
    worst = 0.0
    best = float('+inf')
    total = 0.0
    call_cnt = 0

    @functools.wraps(target)
    def decorator(*args, **kwargs):
        nonlocal worst, best, total, call_cnt

        entered_at = time.monotonic()
        output = target(*args, **kwargs)
        execution_time = time.monotonic() - entered_at

        worst = max(worst, execution_time)
        best = min(best, execution_time)
        total += execution_time
        call_cnt += 1

        getLogger(str(target.__module__)).debug('%r completed in %.3f s (worst %.3f, best %.3f, avg %.3f)',
                                                target, execution_time, worst, best, total / call_cnt)

        return output

    return decorator


def gui_test(test_case_function: typing.Callable):
    """
    Use this decorator with GUI test cases.
    It attempts to detect if there is a desktop environment available where the GUI could be rendered, and if not,
    it skips the decorated test.
    """
    import pytest

    @functools.wraps(test_case_function)
    def decorator(*args, **kwargs):
        if not bool(os.getenv('DISPLAY', False)):
            pytest.skip("GUI test skipped because this environment doesn't seem to be GUI-capable")

        if bool(os.environ.get('SKIP_SLOW_TESTS', False)):
            pytest.skip('GUI test skipped because $SKIP_SLOW_TESTS is set')

        test_case_function(*args, **kwargs)

    return decorator


@gui_test
def _unittest_show_error():
    from PyQt5.QtWidgets import QApplication
    app = QApplication([])
    # We don't have to act upon the returned object; we just need to keep a reference to keep it alive
    mb = show_error('Error title', 'Error text', 'Informative text', None)
    for _ in range(1000):
        time.sleep(0.002)
        app.processEvents()

    mb.close()


@gui_test
def _unittest_icons():
    import math
    import glob
    from PyQt5.QtWidgets import QApplication, QMainWindow, QGroupBox, QGridLayout, QLabel, QSizePolicy
    from PyQt5.QtGui import QFont, QFontMetrics

    app = QApplication([])

    all_icons = list(map(lambda x: os.path.splitext(os.path.basename(x))[0],
                         glob.glob(os.path.join(get_absolute_path('view', 'icons'), '*'))))
    print('All icons:', len(all_icons), all_icons)

    grid_size = int(math.ceil(math.sqrt(len(all_icons))))

    icon_size = QFontMetrics(QFont()).height()

    def render_icon(name: str, row: int, col: int):
        icon = get_icon(name)
        icon_label = QLabel()
        icon_label.setAlignment(Qt.AlignCenter)
        icon_label.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        icon_label.setPixmap(icon.pixmap(icon_size, icon_size))
        layout.addWidget(icon_label, row, col)

    win = QMainWindow()
    container = QGroupBox(win)
    layout = QGridLayout()

    for idx, ic in enumerate(all_icons):
        render_icon(ic, idx // grid_size, idx % grid_size)

    container.setLayout(layout)
    win.setCentralWidget(container)
    win.show()

    for _ in range(1000):
        time.sleep(0.005)
        app.processEvents()

    win.close()

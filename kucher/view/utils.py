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
from PyQt5.QtWidgets import QWidget, QPushButton
from PyQt5.QtGui import QFont, QFontInfo, QIcon
from PyQt5.QtCore import Qt
from resources import get_absolute_path


_logger = getLogger(__name__)


def get_application_icon() -> QIcon:
    return QIcon(get_absolute_path('view', 'icons', 'zee-with-margins.png'))


def get_icon(name: str) -> QIcon:
    return QIcon(get_absolute_path('view', 'icons', f'{name}.png'))


def get_monospace_font() -> QFont:
    preferred = ['Consolas', 'DejaVu Sans Mono', 'Monospace', 'Lucida Console', 'Monaco']
    for name in preferred:
        font = QFont(name)
        if QFontInfo(font).fixedPitch():
            _logger.debug('Selected monospace font: %r', font.toString())
            return font

    font = QFont()
    font.setStyleHint(QFont().Monospace)
    font.setFamily('monospace')
    _logger.debug('Using fallback monospace font: %r', font.toString())
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

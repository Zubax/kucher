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
from PyQt5.QtWidgets import QApplication, QWidget, QPushButton, QMessageBox, QLayout, QHBoxLayout, QVBoxLayout, \
    QBoxLayout
from PyQt5.QtGui import QFont, QFontInfo, QIcon, QPixmap
from PyQt5.QtCore import Qt

from kucher.resources import get_absolute_path


# Wraps the function with a cache.
# The cache is not size-bounded! Every combination of arguments will be kept as long as the program runs.
cached = functools.lru_cache(None)


_logger = getLogger(__name__)


def get_application_icon() -> QIcon:
    return get_icon('zee')


@cached
def get_icon_path(name: str) -> str:
    def attempt(ext: str) -> str:
        return get_absolute_path('view', 'icons', f'{name}.{ext}', check_existence=True)

    try:
        out = attempt('png')
    except ValueError:
        out = attempt('svg')

    _logger.info(f'Icon {name!r} found at {out!r}')
    return out


@cached
def get_icon(name: str) -> QIcon:
    return QIcon(get_icon_path(name))


@cached
def get_icon_pixmap(icon_name: str, width: int, height: int=None) -> QPixmap:
    """
    Caching wrapper around get_icon(...).pixmap(...).
    Every generated pixmap is cached permanently.
    """
    begun = time.monotonic()
    height = height or width
    output = get_icon(icon_name).pixmap(width, height)
    elapsed = time.monotonic() - begun
    _logger.info('Pixmap %r has been rendered with size %rx%r in %.6f seconds', icon_name, width, height, elapsed)
    return output


def get_monospace_font(small=False) -> QFont:
    # We have to copy the result because we don't want to share the same instance globally - users may mutate it
    return QFont(_get_monospace_font_impl(small))


@cached
def _get_monospace_font_impl(small=False) -> QFont:
    begun = time.monotonic()
    multiplier = 0.8 if small else 1.0
    min_font_size = 7
    preferred = ['Consolas', 'DejaVu Sans Mono', 'Monospace', 'Lucida Console', 'Monaco']
    for name in preferred:
        font = QFont(name)
        if QFontInfo(font).fixedPitch():
            font.setPointSize(round(max(min_font_size, QFont().pointSize() * multiplier)))
            _logger.info('Selected monospace font (%.6f seconds): %r', time.monotonic() - begun, font.toString())
            return font

    font = QFont()
    font.setStyleHint(QFont().Monospace)
    font.setFamily('monospace')
    _logger.info('Using fallback monospace font (%.6f seconds): %r', time.monotonic() - begun, font.toString())
    return font


@cached
def is_small_screen() -> bool:
    # See this for reference: http://screensiz.es/monitor
    # noinspection PyArgumentList
    rect = QApplication.desktop().screenGeometry()
    w, h = rect.width(), rect.height()
    is_small = (w < 1000) or (h < 800)
    _logger.info(f'Screen width and height: {w, h}, is small: {is_small}')
    return is_small


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


# noinspection PyArgumentList
def lay_out(layout_object: QBoxLayout,
            *items_or_items_with_stretch_factors: typing.Union[QWidget,
                                                               QLayout,
                                                               typing.Tuple[QWidget, int],
                                                               typing.Tuple[QLayout, int],
                                                               typing.Tuple[None, int]]):
    for item in items_or_items_with_stretch_factors:
        if isinstance(item, tuple):
            item, stretch = item
        else:
            item, stretch = item, 0

        if isinstance(item, QLayout):
            layout_object.addLayout(item, stretch)
        elif isinstance(item, QWidget):
            layout_object.addWidget(item, stretch)
        elif item is None:
            layout_object.addStretch(stretch)
        else:
            raise TypeError(f'Unexpected type: {type(item)!r}')


# noinspection PyArgumentList
def lay_out_horizontally(*items_or_items_with_stretch_factors: typing.Union[QWidget,
                                                                            QLayout,
                                                                            typing.Tuple[QWidget, int],
                                                                            typing.Tuple[QLayout, int],
                                                                            typing.Tuple[None, int]]) -> QLayout:
    """A simple convenience function that creates a horizontal layout in a Pythonic way"""
    inner = QHBoxLayout()
    lay_out(inner, *items_or_items_with_stretch_factors)
    return inner


# noinspection PyArgumentList
def lay_out_vertically(*items_or_items_with_stretch_factors: typing.Union[QWidget,
                                                                          QLayout,
                                                                          typing.Tuple[QWidget, int],
                                                                          typing.Tuple[QLayout, int],
                                                                          typing.Tuple[None, int]]) -> QLayout:
    """Like lay_out_horizontally(), but for vertical layouts."""
    inner = QVBoxLayout()
    lay_out(inner, *items_or_items_with_stretch_factors)
    return inner


def gui_test(test_case_function: typing.Callable):
    """
    Use this decorator with GUI test cases.
    It attempts to detect if there is a desktop environment available where the GUI could be rendered, and if not,
    it skips the decorated test.
    """
    @functools.wraps(test_case_function)
    def decorator(*args, **kwargs):
        # Observe that PyTest is NOT a runtime dependency; therefore, it must not be imported unless a test
        # function is invoked!
        import pytest

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

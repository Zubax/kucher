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

from logging import getLogger
from PyQt5.QtGui import QFont, QFontInfo, QIcon
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

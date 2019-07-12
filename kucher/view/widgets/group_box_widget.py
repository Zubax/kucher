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
from logging import getLogger
from PyQt5.QtWidgets import QWidget, QGroupBox
from PyQt5.QtGui import QFontMetrics, QFont
from ..utils import get_icon_path


_logger = getLogger(__name__)


class GroupBoxWidget(QGroupBox):
    def __init__(self,
                 parent:        QWidget,
                 title:         str,
                 icon_name:     typing.Optional[str] = None):
        super(GroupBoxWidget, self).__init__(title, parent)

        # Changing icons is very expensive, so we store last set icon in order to avoid re-setting it
        self._current_icon: typing.Optional[str] = None

        if icon_name:
            self.set_icon(icon_name)

    def set_icon(self, icon_name: str):
        if self._current_icon == icon_name:
            return

        _logger.debug('Changing icon from %r to %r', self._current_icon, icon_name)
        self._current_icon = icon_name

        icon_size = QFontMetrics(QFont()).height()
        icon_path = get_icon_path(icon_name)

        # This hack adds a custom icon to the GroupBox: make it checkable, and then, using styling, override
        # the image of the check box with the custom icon.
        self.setCheckable(True)     # This is needed to make the icon visible
        self.setStyleSheet(f'''
            QGroupBox::indicator {{
                width:  {icon_size}px;
                height: {icon_size}px;
                image: url({icon_path});
            }}
        ''')

        # We don't actually want it to be checkable, so override this thing to return it back to normal again
        # noinspection PyUnresolvedReferences
        self.toggled.connect(lambda _: self.setChecked(True))

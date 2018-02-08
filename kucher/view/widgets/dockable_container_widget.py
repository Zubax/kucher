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
from PyQt5.QtWidgets import QWidget, QDockWidget
from PyQt5.QtCore import Qt
from ..utils import get_icon_path
from utils import Event


_logger = getLogger(__name__)


class DockableContainerWidget(QDockWidget):
    def __init__(self,
                 parent:            QWidget,
                 title:             str,
                 icon_name:         typing.Optional[str]=None):
        super(QDockWidget, self).__init__(title, parent)
        self.setAttribute(Qt.WA_DeleteOnClose)                  # This is required to stop background timers!

        if icon_name:
            self.set_icon(icon_name)

        self._close_event = Event()

    def __del__(self):
        _logger.debug('Deleting %r', self)

    # noinspection PyCallingNonCallable
    def closeEvent(self, *_):
        _logger.debug('Close event at %r', self)
        self._close_event()

    @property
    def close_event(self):
        """No arguments are passed, nothing is expected back."""
        return self._close_event

    def set_icon(self, icon_name: str):
        raise NotImplementedError

    @property
    def widget(self) -> QWidget:
        return super(DockableContainerWidget, self).widget()

    # noinspection PyMethodOverriding
    @widget.setter
    def widget(self, widget: QWidget):
        if not isinstance(widget, QWidget):
            raise TypeError(f'Expected QWidget, got {type(widget)}')

        self.setWidget(widget)

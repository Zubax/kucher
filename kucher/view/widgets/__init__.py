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
from PyQt5.QtWidgets import QWidget


_logger = getLogger(__name__)


class WidgetBase(QWidget):
    """
    The base class for custom widgets implemented in Kucher.
    """

    def __init__(self, parent: typing.Optional[QWidget]):
        super(WidgetBase, self).__init__(parent)

    def flash(self, message: str, *format_args, duration: typing.Optional[float]=None):
        """
        Shows the specified message in the status bar of the parent window.
        """
        duration_milliseconds = int((duration or 0) * 1000)
        formatted_message = message % format_args
        self.window().statusBar().showMessage(formatted_message, duration_milliseconds)
        _logger.info('Flashing status bar message from %r for %.1f seconds: %r',
                     self,
                     (duration_milliseconds * 1e-3) if duration_milliseconds > 0 else float('inf'),
                     formatted_message)

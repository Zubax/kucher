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
from PyQt5.QtWidgets import QWidget, QTreeView, QLabel, QApplication
from view.widgets import WidgetBase
from view.utils import gui_test, make_button, get_monospace_font, lay_out_vertically, lay_out_horizontally
from view.device_model_representation import Register
from .model import Model


_logger = getLogger(__name__)


class RegisterViewWidget(WidgetBase):
    def __init__(self,
                 parent:    QWidget,
                 registers: typing.Iterable[Register]):
        super(RegisterViewWidget, self).__init__(parent)

        self._model = Model(self, registers)

        self.setLayout(lay_out_vertically())

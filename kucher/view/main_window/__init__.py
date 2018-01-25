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
from PyQt5.QtWidgets import QApplication, QMainWindow, QWidget, QVBoxLayout, QSplitter, QAction
from PyQt5.QtGui import QKeySequence, QDesktopServices
from PyQt5.QtCore import QTimer, Qt, QUrl
from ..utils import get_application_icon


class MainWindow(QMainWindow):
    def __init__(self, on_close: typing.Callable[[], None]):
        # noinspection PyArgumentList
        super(MainWindow, self).__init__()
        self.setWindowTitle('Zubax Kucher')
        self.setWindowIcon(get_application_icon())

        # File menu
        quit_action = QAction('&Quit', self)
        quit_action.setShortcut(QKeySequence('Ctrl+Shift+Q'))
        quit_action.triggered.connect(on_close)

        file_menu = self.menuBar().addMenu('&File')
        file_menu.addAction(quit_action)

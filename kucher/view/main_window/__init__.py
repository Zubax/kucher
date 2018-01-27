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
from PyQt5.QtWidgets import QMainWindow, QWidget, QVBoxLayout, QSplitter, QAction
from PyQt5.QtGui import QKeySequence, QDesktopServices, QCloseEvent
from PyQt5.QtCore import QUrl
from ..utils import get_application_icon, get_icon
from .connection_management_widget import ConnectionManagementWidget
from data_dir import LOG_DIR


class MainWindow(QMainWindow):
    # noinspection PyCallByClass,PyUnresolvedReferences,PyArgumentList
    def __init__(self, on_close: typing.Callable[[], None]):
        super(MainWindow, self).__init__()
        self.setWindowTitle('Zubax Kucher')
        self.setWindowIcon(get_application_icon())

        self.statusBar().show()

        self._on_close = on_close

        self._connection_management_widget = ConnectionManagementWidget(self)

        # File menu
        quit_action = QAction(get_icon('exit'), '&Quit', self)
        quit_action.setShortcut(QKeySequence('Ctrl+Shift+Q'))
        quit_action.triggered.connect(self._on_close)

        file_menu = self.menuBar().addMenu('&File')
        file_menu.addAction(quit_action)

        # Help menu
        website_action = QAction(get_icon('www'), 'Open Zubax Robotics &website', self)
        website_action.triggered.connect(lambda: QDesktopServices.openUrl(QUrl('https://zubax.com')))

        knowledge_base_action = QAction(get_icon('knowledge'), 'Open Zubax &Knowledge Base website', self)
        knowledge_base_action.triggered.connect(lambda: QDesktopServices.openUrl(QUrl('https://kb.zubax.com')))

        show_log_directory_action = QAction(get_icon('log'), 'Open &log directory', self)
        show_log_directory_action.triggered.connect(lambda: QDesktopServices.openUrl(QUrl.fromLocalFile(LOG_DIR)))

        help_menu = self.menuBar().addMenu('&Help')
        help_menu.addAction(website_action)
        help_menu.addAction(knowledge_base_action)
        help_menu.addAction(show_log_directory_action)
        # help_menu.addAction(about_action)                 # TODO: Implement this

        # Layout
        central_widget = QWidget(self)

        main_layout = QVBoxLayout()
        main_layout.addWidget(self._connection_management_widget)

        central_widget.setLayout(main_layout)
        self.setCentralWidget(central_widget)

    def closeEvent(self, event: QCloseEvent):
        self._on_close()
        event.ignore()

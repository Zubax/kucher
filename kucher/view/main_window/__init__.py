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
from PyQt5.QtWidgets import QMainWindow, QAction
from PyQt5.QtGui import QDesktopServices, QCloseEvent
from PyQt5.QtCore import QUrl
from ..utils import get_application_icon, get_icon, is_small_screen
from ..device_model_representation import GeneralStatusView, TaskStatisticsView, BasicDeviceInfo, Commander
from ..tool_window_manager import ToolWindowManager, ToolWindowLocation, ToolWindowGroupingCondition
from data_dir import LOG_DIR

from .connection_management_widget import ConnectionRequestCallback, DisconnectionRequestCallback
from .main_widget import MainWidget
from .task_statistics_widget import TaskStatisticsWidget
from .log_widget import LogWidget


_WINDOW_TITLE_PREFIX = 'Zubax Kucher'


TaskStatisticsRequestCallback = typing.Callable[[], typing.Awaitable[typing.Optional[TaskStatisticsView]]]


class MainWindow(QMainWindow):
    # noinspection PyCallByClass,PyUnresolvedReferences,PyArgumentList
    def __init__(self,
                 on_close:                   typing.Callable[[], None],
                 on_connection_request:      ConnectionRequestCallback,
                 on_disconnection_request:   DisconnectionRequestCallback,
                 on_task_statistics_request: TaskStatisticsRequestCallback,
                 commander:                  Commander):
        super(MainWindow, self).__init__()
        self.setWindowTitle(_WINDOW_TITLE_PREFIX)
        self.setWindowIcon(get_application_icon())

        self.statusBar().show()

        self._on_close = on_close
        self._tool_window_manager = ToolWindowManager(self)

        self._main_widget = MainWidget(self,
                                       on_connection_request=on_connection_request,
                                       on_disconnection_request=on_disconnection_request,
                                       commander=commander)

        self._configure_file_menu()
        self._configure_tool_windows(on_task_statistics_request)
        self._configure_help_menu()

        self.setCentralWidget(self._main_widget)

    def on_connection_established(self, device_info: BasicDeviceInfo):
        self._main_widget.on_connection_established(device_info)
        for w in self._tool_window_manager.select_widgets(LogWidget):
            w.on_device_connected(device_info)

        self.setWindowTitle(f'{_WINDOW_TITLE_PREFIX} - #{device_info.globally_unique_id.hex()}')

    def on_connection_loss(self, reason: str):
        self._main_widget.on_connection_loss(reason)
        for w in self._tool_window_manager.select_widgets(LogWidget):
            w.on_device_disconnected(reason)

        self.setWindowTitle(_WINDOW_TITLE_PREFIX)

    def on_connection_initialization_progress_report(self,
                                                     stage_description: str,
                                                     progress: float):
        self._main_widget.on_connection_initialization_progress_report(stage_description, progress)

    def on_general_status_update(self, timestamp: float, status: GeneralStatusView):
        self._main_widget.on_general_status_update(timestamp, status)

    def on_log_line_reception(self, monotonic_timestamp: float, text: str):
        for w in self._tool_window_manager.select_widgets(LogWidget):
            w.append_lines([text])

    def _configure_tool_windows(self,
                                on_task_statistics_request: TaskStatisticsRequestCallback):
        self._tool_window_manager.add_arrangement_rule(apply_to=[LogWidget, TaskStatisticsWidget],
                                                       group_when=ToolWindowGroupingCondition.ALWAYS,
                                                       location=ToolWindowLocation.BOTTOM)

        self._tool_window_manager.register(lambda parent: TaskStatisticsWidget(parent, on_task_statistics_request),
                                           'Task statistics',
                                           'spreadsheet',
                                           shown_by_default=not is_small_screen())

        self._tool_window_manager.register(LogWidget,
                                           'Device log',
                                           'log',
                                           shown_by_default=not is_small_screen())

    # noinspection PyCallByClass,PyUnresolvedReferences,PyArgumentList
    def _configure_file_menu(self):
        # File menu
        quit_action = QAction(get_icon('exit'), '&Quit', self)
        quit_action.triggered.connect(self._on_close)

        file_menu = self.menuBar().addMenu('&File')
        file_menu.addAction(quit_action)

    # noinspection PyCallByClass,PyUnresolvedReferences,PyArgumentList
    def _configure_help_menu(self):
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

    def closeEvent(self, event: QCloseEvent):
        self._on_close()
        event.ignore()

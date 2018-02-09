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
from PyQt5.QtWidgets import QMainWindow, QWidget, QVBoxLayout, QAction
from PyQt5.QtGui import QKeySequence, QDesktopServices, QCloseEvent
from PyQt5.QtCore import Qt, QUrl
from ..utils import get_application_icon, get_icon
from ..device_model_representation import GeneralStatusView, TaskStatisticsView, BasicDeviceInfo
from ..tool_window_manager import ToolWindowManager, ToolWindowLocation, ToolWindowGroupingCondition
from data_dir import LOG_DIR

from .connection_management_widget import ConnectionManagementWidget, ConnectionRequestCallback, \
                                          DisconnectionRequestCallback
from .main_dashboard_widget import MainDashboardWidget
from .task_statistics_widget import TaskStatisticsWidget
from .log_widget import LogWidget


TaskStatisticsRequestCallback = typing.Callable[[], typing.Awaitable[typing.Optional[TaskStatisticsView]]]


class MainWindow(QMainWindow):
    # noinspection PyCallByClass,PyUnresolvedReferences,PyArgumentList
    def __init__(self,
                 on_close: typing.Callable[[], None],
                 on_connection_request: ConnectionRequestCallback,
                 on_disconnection_request: DisconnectionRequestCallback,
                 on_task_statistics_request: TaskStatisticsRequestCallback):
        super(MainWindow, self).__init__()
        self.setWindowTitle('Zubax Kucher')
        self.setWindowIcon(get_application_icon())

        self.statusBar().show()

        self._on_close = on_close
        self._tool_window_manager = ToolWindowManager(self)

        self._connection_management_widget = \
            ConnectionManagementWidget(self,
                                       on_connection_request=on_connection_request,
                                       on_disconnection_request=on_disconnection_request)
        self._main_dashboard_widget = MainDashboardWidget(self)

        self._configure_file_menu()
        self._configure_tool_windows(on_task_statistics_request)
        self._configure_help_menu()

        # Layout
        central_widget = QWidget(self)

        main_layout = QVBoxLayout()
        main_layout.addWidget(self._connection_management_widget)
        main_layout.addWidget(self._main_dashboard_widget)

        central_widget.setLayout(main_layout)
        self.setCentralWidget(central_widget)

    def on_connection_established(self, device_info: BasicDeviceInfo):
        for w in self._tool_window_manager.select_widgets(LogWidget):
            w.on_device_connected(device_info)

    def on_connection_loss(self, reason: str):
        self._connection_management_widget.on_connection_loss(reason)
        self._main_dashboard_widget.on_connection_loss()
        for w in self._tool_window_manager.select_widgets(LogWidget):
            w.on_device_disconnected(reason)

    def on_connection_initialization_progress_report(self,
                                                     stage_description: str,
                                                     progress: float):
        self._connection_management_widget.on_connection_initialization_progress_report(stage_description, progress)

    def on_general_status_update(self, timestamp: float, status: GeneralStatusView):
        self._main_dashboard_widget.on_general_status_update(timestamp, status)

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
                                           shown_by_default=True)

        self._tool_window_manager.register(LogWidget,
                                           'Device log',
                                           'log',
                                           shown_by_default=True)

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

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
from PyQt5.QtWidgets import QMainWindow, QAction, QSizePolicy, QWIDGETSIZE_MAX, QWidget
from PyQt5.QtGui import QDesktopServices, QCloseEvent, QResizeEvent
from PyQt5.QtCore import QUrl, QSize

from kucher.data_dir import LOG_DIR
from kucher.view.utils import get_application_icon, get_icon, is_small_screen
from kucher.view.tool_window_manager import (
    ToolWindowManager,
    ToolWindowLocation,
    ToolWindowGroupingCondition,
)
from kucher.view.device_model_representation import (
    GeneralStatusView,
    TaskStatisticsView,
    BasicDeviceInfo,
    Commander,
    Register,
)

from .device_management_widget import (
    ConnectionRequestCallback,
    DisconnectionRequestCallback,
)
from .main_widget import MainWidget
from .task_statistics_widget import TaskStatisticsWidget
from .log_widget import LogWidget
from .about_widget import AboutWidget
from .register_view_widget import RegisterViewWidget


_WINDOW_TITLE_PREFIX = "Zubax Kucher"


TaskStatisticsRequestCallback = typing.Callable[
    [], typing.Awaitable[typing.Optional[TaskStatisticsView]]
]


class MainWindow(QMainWindow):
    # noinspection PyCallByClass,PyUnresolvedReferences,PyArgumentList
    def __init__(
        self,
        on_close: typing.Callable[[], None],
        on_connection_request: ConnectionRequestCallback,
        on_disconnection_request: DisconnectionRequestCallback,
        on_task_statistics_request: TaskStatisticsRequestCallback,
        commander: Commander,
    ):
        super(MainWindow, self).__init__()
        self.about_window: Optional[AboutWidget] = None
        self.setWindowTitle(_WINDOW_TITLE_PREFIX)
        self.setWindowIcon(get_application_icon())

        self.statusBar().show()

        self._on_close = on_close
        self._tool_window_manager = ToolWindowManager(self)

        self._registers: typing.List[Register] = None

        self._main_widget = MainWidget(
            self,
            on_connection_request=on_connection_request,
            on_disconnection_request=on_disconnection_request,
            commander=commander,
        )

        self._configure_file_menu()
        self._configure_tool_windows(on_task_statistics_request)
        self._configure_help_menu()

        self._tool_window_manager.tool_window_resize_event.connect(
            lambda *_: self._readjust_size_policies()
        )
        self._tool_window_manager.new_tool_window_event.connect(
            lambda *_: self._readjust_size_policies()
        )
        self._tool_window_manager.tool_window_removed_event.connect(
            lambda *_: self._readjust_size_policies()
        )

        self._main_widget.resize_event.connect(self._readjust_size_policies)
        self._main_widget.setSizePolicy(QSizePolicy.Minimum, QSizePolicy.Minimum)

        self.setCentralWidget(self._main_widget)

    def on_connection_established(
        self, device_info: BasicDeviceInfo, registers: typing.List[Register]
    ):
        self._main_widget.on_connection_established(device_info)
        for w in self._tool_window_manager.select_widgets(LogWidget):
            w.on_device_connected(device_info)

        self._registers = registers
        for w in self._tool_window_manager.select_widgets(RegisterViewWidget):
            w.setup(self._registers)

        self.setWindowTitle(
            f"{_WINDOW_TITLE_PREFIX} - #{device_info.globally_unique_id.hex()}"
        )

    def on_connection_loss(self, reason: str):
        self._main_widget.on_connection_loss(reason)
        for w in self._tool_window_manager.select_widgets(LogWidget):
            w.on_device_disconnected(reason)

        self._registers = None
        for w in self._tool_window_manager.select_widgets(RegisterViewWidget):
            w.reset()

        self.setWindowTitle(_WINDOW_TITLE_PREFIX)

    def on_connection_initialization_progress_report(
        self, stage_description: str, progress: float
    ):
        self._main_widget.on_connection_initialization_progress_report(
            stage_description, progress
        )

    def on_general_status_update(self, timestamp: float, status: GeneralStatusView):
        self._main_widget.on_general_status_update(timestamp, status)

    def on_log_line_reception(self, monotonic_timestamp: float, text: str):
        for w in self._tool_window_manager.select_widgets(LogWidget):
            w.append_lines([text])

    def _configure_tool_windows(
        self, on_task_statistics_request: TaskStatisticsRequestCallback
    ):
        self._tool_window_manager.add_arrangement_rule(
            apply_to=[LogWidget, TaskStatisticsWidget],
            group_when=ToolWindowGroupingCondition.ALWAYS,
            location=ToolWindowLocation.BOTTOM,
        )

        self._tool_window_manager.add_arrangement_rule(
            apply_to=[RegisterViewWidget],
            group_when=ToolWindowGroupingCondition.ALWAYS,
            location=ToolWindowLocation.RIGHT,
        )

        self._tool_window_manager.register(
            lambda parent: TaskStatisticsWidget(parent, on_task_statistics_request),
            "Task statistics",
            "spreadsheet",
            shown_by_default=not is_small_screen(),
        )

        self._tool_window_manager.register(
            LogWidget, "Device log", "log", shown_by_default=True
        )

        def spawn_register_widget(parent: QWidget):
            w = RegisterViewWidget(parent)
            if self._registers is not None:
                w.setup(self._registers)

            return w

        self._tool_window_manager.register(
            spawn_register_widget, "Registers", "data", shown_by_default=True
        )

    # noinspection PyCallByClass,PyUnresolvedReferences,PyArgumentList
    def _configure_file_menu(self):
        # File menu
        quit_action = QAction(get_icon("exit"), "&Quit", self)
        quit_action.triggered.connect(self._on_close)

        file_menu = self.menuBar().addMenu("&File")
        file_menu.addAction(quit_action)

    # noinspection PyCallByClass,PyUnresolvedReferences,PyArgumentList
    def _configure_help_menu(self):
        # Help menu
        website_action = QAction(get_icon("www"), "Open Zubax Robotics &website", self)
        website_action.triggered.connect(
            lambda: QDesktopServices.openUrl(QUrl("https://zubax.com"))
        )

        knowledge_base_action = QAction(
            get_icon("knowledge"), "Open Zubax &Knowledge Base website", self
        )
        knowledge_base_action.triggered.connect(
            lambda: QDesktopServices.openUrl(QUrl("https://kb.zubax.com"))
        )

        show_log_directory_action = QAction(
            get_icon("log"), "Open &log directory", self
        )
        open_about_action = QAction(
            get_icon("log"), "About", self
        )
        show_log_directory_action.triggered.connect(
            lambda: QDesktopServices.openUrl(QUrl.fromLocalFile(LOG_DIR))
        )

        def open_about_window():
            if not self.about_window:
                self.about_window = AboutWidget()
            else:
                self.about_window.show()
                self.about_window.raise_()

        open_about_action.triggered.connect(open_about_window)

        help_menu = self.menuBar().addMenu("&Help")
        help_menu.addAction(website_action)
        help_menu.addAction(knowledge_base_action)
        help_menu.addAction(show_log_directory_action)
        help_menu.addAction(open_about_action)

    def _readjust_size_policies(self):
        size_hint: QSize = self.centralWidget().sizeHint()
        width_hint, height_hint = size_hint.width(), size_hint.height()

        # TODO: remember the largest width hint, use it in order to prevent back and forth resizing when
        # TODO: the content changes?

        docked_tb = self._tool_window_manager.select_widgets(
            current_location=ToolWindowLocation.TOP
        ) + self._tool_window_manager.select_widgets(
            current_location=ToolWindowLocation.BOTTOM
        )

        docked_lr = self._tool_window_manager.select_widgets(
            current_location=ToolWindowLocation.LEFT
        ) + self._tool_window_manager.select_widgets(
            current_location=ToolWindowLocation.RIGHT
        )

        self.centralWidget().setMaximumHeight(
            height_hint if len(docked_tb) else QWIDGETSIZE_MAX
        )
        self.centralWidget().setMaximumWidth(
            width_hint if len(docked_lr) else QWIDGETSIZE_MAX
        )

    def closeEvent(self, event: QCloseEvent):
        self._on_close()
        event.ignore()

    def resizeEvent(self, event: QResizeEvent):
        super(MainWindow, self).resizeEvent(event)
        self._readjust_size_policies()

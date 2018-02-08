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
from PyQt5.QtWidgets import QWidget, QMainWindow, QAction, QMenu
from .widgets.tool_window import ToolWindow
from .utils import get_icon


_WidgetTypeVar = typing.NewType('W', QWidget)


_logger = getLogger(__name__)


class ToolWindowManager:
    def __init__(self, parent_window: QMainWindow):
        self._parent_window: QMainWindow = parent_window
        self._children: typing.List[ToolWindow] = []
        self._menu: QMenu = None

    # noinspection PyUnresolvedReferences
    def register(self,
                 title:                     str,
                 factory:                   typing.Callable[[], ToolWindow],
                 default_location:          int,
                 icon_name:                 typing.Optional[str]=None,
                 allow_multiple_instances:  bool=False,
                 shown_by_default:          bool=False):
        if self._menu is None:
            self._menu = self._parent_window.menuBar().addMenu('&Tools')

        def spawn():
            def terminate():
                self._children.remove(dock)
                if not allow_multiple_instances:
                    action.setEnabled(True)

            # noinspection PyBroadException
            try:
                dock = factory()
                dock.setWindowTitle(title)
                if icon_name:
                    dock.set_icon(icon_name)

                self._children.append(dock)
                dock.close_event.connect(terminate)

                self._parent_window.addDockWidget(default_location, dock)

                if not allow_multiple_instances:
                    action.setEnabled(False)
            except Exception:
                _logger.exception(f'Could not spawn tool window {title!r} with icon {icon_name!r}')
            else:
                _logger.info(f'Spawned tool window {dock!r} {title!r} with icon {icon_name!r}')

        action = QAction(get_icon(icon_name), title, self._parent_window)
        action.triggered.connect(spawn)
        self._menu.addAction(action)

        if shown_by_default:
            spawn()

    @property
    def children(self) -> typing.List[ToolWindow]:
        return self._children

    def select_widgets(self, widget_type: typing.Type[_WidgetTypeVar]) -> typing.List[_WidgetTypeVar]:
        """
        Returns a list of references to the root widgets of all existing tool windows which are instances of the
        specified type. This can be used to broadcast events and such.
        Specify the type as QWidget to iterate through all widgets.
        """
        return [win.widget for win in self._children if isinstance(win.widget, widget_type)]

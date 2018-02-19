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

import enum
import copy
import typing
from dataclasses import dataclass
from logging import getLogger
from PyQt5.QtWidgets import QWidget, QMainWindow, QAction, QMenu, QTabWidget, QTabBar
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QIcon
from .widgets.tool_window import ToolWindow
from .utils import get_icon, is_small_screen


_WidgetTypeVar = typing.TypeVar('W')


_logger = getLogger(__name__)


class ToolWindowLocation(enum.IntEnum):
    TOP    = Qt.TopDockWidgetArea
    BOTTOM = Qt.BottomDockWidgetArea
    LEFT   = Qt.LeftDockWidgetArea
    RIGHT  = Qt.RightDockWidgetArea


class ToolWindowGroupingCondition(enum.Enum):
    NEVER           = enum.auto()
    SAME_LOCATION   = enum.auto()
    ALWAYS          = enum.auto()


class ToolWindowManager:
    # noinspection PyUnresolvedReferences
    def __init__(self, parent_window: QMainWindow):
        self._parent_window: QMainWindow = parent_window

        self._children: typing.List[ToolWindow] = []
        self._menu: QMenu = None
        self._arrangement_rules: typing.List[_ArrangementRule] = []
        self._title_to_icon_mapping: typing.Dict[str, QIcon] = {}

        self._parent_window.tabifiedDockWidgetActivated.connect(self._reiconize)

        # Set up the appearance
        self._parent_window.setTabPosition(Qt.TopDockWidgetArea,    QTabWidget.North)
        self._parent_window.setTabPosition(Qt.BottomDockWidgetArea, QTabWidget.South)
        self._parent_window.setTabPosition(Qt.LeftDockWidgetArea,   QTabWidget.West)
        self._parent_window.setTabPosition(Qt.RightDockWidgetArea,  QTabWidget.East)

        # Now, most screens are wide but not very tall; we need to optimize the layout for that
        # More info (this is for Qt4 but works for Qt5 as well): https://doc.qt.io/archives/4.6/qt4-mainwindow.html
        self._parent_window.setCorner(Qt.TopLeftCorner,     Qt.LeftDockWidgetArea)
        self._parent_window.setCorner(Qt.BottomLeftCorner,  Qt.LeftDockWidgetArea)
        self._parent_window.setCorner(Qt.TopRightCorner,    Qt.RightDockWidgetArea)
        self._parent_window.setCorner(Qt.BottomRightCorner, Qt.RightDockWidgetArea)

        # http://doc.qt.io/qt-5/qmainwindow.html#DockOption-enum
        dock_options = self._parent_window.AnimatedDocks | self._parent_window.AllowTabbedDocks
        if not is_small_screen():
            dock_options |= self._parent_window.AllowNestedDocks    # This won't work well on small screens

        self._parent_window.setDockOptions(dock_options)

    # noinspection PyUnresolvedReferences
    def register(self,
                 factory:                   typing.Union[typing.Type[QWidget],
                                                         typing.Callable[[ToolWindow], QWidget]],
                 title:                     str,
                 icon_name:                 typing.Optional[str]=None,
                 allow_multiple_instances:  bool=False,
                 shown_by_default:          bool=False):
        """
        Adds the specified tool WIDGET (not window) to the set of known tools.
        If requested, it can be instantiated automatically at the time of application startup.
        The class will automatically register the menu item and do all of the other boring boilerplate stuff.
        """
        if self._menu is None:
            self._menu = self._parent_window.menuBar().addMenu('&Tools')

        def spawn():
            def terminate():
                self._children.remove(tw)
                action.setEnabled(True)

            # noinspection PyBroadException
            try:
                # Instantiating the tool window and set up its widget using the client-provided factory
                tw = ToolWindow(self._parent_window,
                                title=title,
                                icon_name=icon_name)
                tw.widget = factory(tw)

                # Set up the tool window
                self._children.append(tw)
                tw.close_event.connect(terminate)
                self._allocate(tw)

                # Below we're making sure that the newly added tool window ends up on top
                # https://stackoverflow.com/questions/1290882/focusing-on-a-tabified-qdockwidget-in-pyqt
                tw.show()
                tw.raise_()

                if not allow_multiple_instances:
                    action.setEnabled(False)
            except Exception:
                _logger.exception(f'Could not spawn tool window {title!r} with icon {icon_name!r}')
            else:
                _logger.info(f'Spawned tool window {tw!r} {title!r} with icon {icon_name!r}')

        icon = get_icon(icon_name)

        # FIXME: This is not cool - a title collision will mess up our icons!
        self._title_to_icon_mapping[title] = icon

        action = QAction(icon, title, self._parent_window)
        action.triggered.connect(spawn)
        self._menu.addAction(action)

        if shown_by_default:
            spawn()

    def add_arrangement_rule(self,
                             apply_to:      typing.Iterable[typing.Type[QWidget]],
                             group_when:    ToolWindowGroupingCondition,
                             location:      ToolWindowLocation):
        """
        :param apply_to:
        :param group_when:  Grouping policy:
                                NEVER         - do not group unless the user did that manually
                                SAME_LOCATION - group only if the grouped widgets are at the same location
                                ALWAYS        - group always, regardless of the location
        :param location:    Default placement in the main window
        """
        self._arrangement_rules.append(_ArrangementRule(apply_to=list(apply_to),
                                                        group_when=group_when,
                                                        location=location))

    def select_widgets(self, widget_type: typing.Type[_WidgetTypeVar]) -> typing.List[_WidgetTypeVar]:
        """
        Returns a list of references to the root widgets of all existing tool windows which are instances of the
        specified type. This can be used to broadcast events and such.
        Specify the type as QWidget to iterate through all widgets.
        """
        # noinspection PyTypeChecker
        return [win.widget for win in self._children if isinstance(win.widget, widget_type)]

    def _select_tool_windows(self, widget_type: typing.Type[QWidget]) -> typing.List[ToolWindow]:
        return [win for win in self._children if isinstance(win.widget, widget_type)]

    def _select_applicable_arrangement_rules(self, widget_type: typing.Type[QWidget]) -> \
            typing.List['_ArrangementRule']:
        return [copy.deepcopy(ar) for ar in self._arrangement_rules if widget_type in ar.apply_to]

    def _allocate(self, what: ToolWindow):
        widget_type = type(what.widget)

        rules = self._select_applicable_arrangement_rules(widget_type)
        if not rules:
            raise ValueError(f'Arrangement rules for widget of type {widget_type} could not be found')

        self._parent_window.addDockWidget(int(rules[0].location), what)

        # Oblaka, belogrivye loshadki...
        for ar in rules:
            matching_windows: typing.List[ToolWindow] = []
            for applicable in ar.apply_to:
                if applicable is not widget_type:
                    matching_windows += self._select_tool_windows(applicable)

            _logger.info(f'Existing tool windows matching the rule {ar} against {widget_type}: {matching_windows}')

            if not matching_windows:
                continue

            if ar.group_when == ToolWindowGroupingCondition.NEVER:
                continue

            if ar.group_when == ToolWindowGroupingCondition.SAME_LOCATION:
                tabify_with = None
                for mw in matching_windows:
                    if int(ar.location) == self._parent_window.dockWidgetArea(mw):
                        tabify_with = mw
                        break

                if tabify_with is None:
                    continue
            else:
                tabify_with = matching_windows[0]

            # Observe that the order of arguments matters here. The second widget will end up on top.
            # We always show the freshly added widget on top.
            self._parent_window.tabifyDockWidget(tabify_with, what)
            break

        self._reiconize()

    def _reiconize(self, *_):
        # https://stackoverflow.com/questions/46613165/qt-tab-icon-when-qdockwidget-becomes-docked
        # In order to reduce the probability of hitting a false positive, we query only the direct children of the
        # main window. Conveniently, the tab bars in the dock areas are direct descendants of the main window.
        # It is assumed that this can never be the case with other widgets, since tab bars are usually nested into
        # other widgets.
        to_a_bar = self._parent_window.findChildren(QTabBar, '', Qt.FindDirectChildrenOnly)
        for tab_walks in to_a_bar:      # ha ha
            for index in range(tab_walks.count()):
                title = tab_walks.tabText(index)
                try:
                    icon = self._title_to_icon_mapping[title]
                except KeyError:
                    continue

                tab_walks.setTabIcon(index, icon)


@dataclass
class _ArrangementRule:
    apply_to:       typing.List[typing.Type[QWidget]]
    group_when:     ToolWindowGroupingCondition
    location:       ToolWindowLocation

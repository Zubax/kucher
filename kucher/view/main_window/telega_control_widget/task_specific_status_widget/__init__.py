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
import importlib
from logging import getLogger
from PyQt5.QtWidgets import QWidget, QStackedLayout

from kucher.view.device_model_representation import GeneralStatusView, TaskID, get_icon_name_for_task_id, \
    get_human_friendly_task_name
from kucher.view.widgets.group_box_widget import GroupBoxWidget

from .placeholder_widget import PlaceholderWidget
from .base import StatusWidgetBase


_DEFAULT_ICON = 'question-mark'
_DEFAULT_TITLE = 'Task-specific status information'


_logger = getLogger(__name__)


class TaskSpecificStatusWidget(GroupBoxWidget):
    # noinspection PyArgumentList
    def __init__(self, parent: QWidget):
        super(TaskSpecificStatusWidget, self).__init__(parent, _DEFAULT_TITLE, _DEFAULT_ICON)

        self._placeholder_widget = PlaceholderWidget(self)

        self._layout = QStackedLayout()
        self._layout.addWidget(self._placeholder_widget)

        self._task_id_to_widget_mapping: typing.Dict[TaskID, StatusWidgetBase] = {}
        for tid in TaskID:
            try:
                w = _TASK_ID_TO_WIDGET_TYPE_MAPPING[tid](self)
            except KeyError:
                self._task_id_to_widget_mapping[tid] = self._placeholder_widget
            else:
                self._task_id_to_widget_mapping[tid] = w
                self._layout.addWidget(w)

        _logger.info('Task ID to widget mapping: %r', self._task_id_to_widget_mapping)

        self._layout.setCurrentWidget(self._placeholder_widget)
        self.setLayout(self._layout)

    def on_general_status_update(self, timestamp: float, s: GeneralStatusView):
        w = self._task_id_to_widget_mapping[s.current_task_id]
        self._ensure_widget_active(w)
        # noinspection PyBroadException
        try:
            w.on_general_status_update(timestamp, s)
        except Exception:
            _logger.exception(f'Task-specific widget update failed; '
                              f'task ID {s.current_task_id!r}, widget {type(w)!r}')

        self.set_icon(get_icon_name_for_task_id(s.current_task_id))

        title = f'{get_human_friendly_task_name(s.current_task_id)} task status information'
        if title != self.title():
            self.setTitle(title)

    def reset(self):
        self._ensure_widget_active(self._placeholder_widget)
        self.set_icon(_DEFAULT_ICON)
        self.setTitle(_DEFAULT_TITLE)

    def _ensure_widget_active(self, new_widget: StatusWidgetBase):
        if self._layout.currentWidget() is not new_widget:
            # noinspection PyBroadException
            try:
                self._layout.currentWidget().reset()
            except Exception:
                _logger.exception(f'Task-specific widget reset failed; widget {type(new_widget)!r}')

            self._layout.setCurrentWidget(new_widget)


_TASK_ID_TO_WIDGET_TYPE_MAPPING: typing.Dict[TaskID, typing.Type[StatusWidgetBase]] = {}


def _load_widgets():
    global _TASK_ID_TO_WIDGET_TYPE_MAPPING

    for tid in TaskID:
        module_name = f'{str(tid).split(".")[-1].lower()}_status_widget'
        _logger.info(f'Loading module {module_name} for task ID {tid!r}')
        try:
            module = importlib.import_module('.' + module_name, __name__)
        except ImportError:
            _logger.info(f'Module is not defined - no task-specific status info for task {tid!r} is available')
        else:
            assert issubclass(module.Widget, StatusWidgetBase)
            _TASK_ID_TO_WIDGET_TYPE_MAPPING[tid] = module.Widget
            _logger.info(f'Module {module} loaded successfully')


_load_widgets()

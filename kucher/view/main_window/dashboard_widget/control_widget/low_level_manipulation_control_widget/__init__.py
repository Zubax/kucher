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
from PyQt5.QtWidgets import QWidget, QTabWidget
from view.device_model_representation import Commander, GeneralStatusView, LowLevelManipulationMode
from view.utils import get_icon, lay_out_vertically
from ..base import SpecializedControlWidgetBase
from .base import LowLevelManipulationControlSubWidgetBase


_logger = getLogger(__name__)


class LowLevelManipulationControlWidget(SpecializedControlWidgetBase):
    # noinspection PyUnresolvedReferences
    def __init__(self,
                 parent:    QWidget,
                 commander: Commander):
        super(LowLevelManipulationControlWidget, self).__init__(parent)

        self._last_seen_timestamped_general_status: typing.Optional[typing.Tuple[float, GeneralStatusView]] = None

        self._tabs = QTabWidget(self)

        for widget_type in _LLM_MODE_TO_WIDGET_TYPE_MAPPING.values():
            widget = widget_type(self, commander)
            tab_name, icon_name = widget.get_widget_name_and_icon_name()
            self._tabs.addTab(widget, get_icon(icon_name), tab_name)

        self._current_widget: LowLevelManipulationControlSubWidgetBase = self._tabs.currentWidget()
        self._tabs.currentChanged.connect(self._on_current_widget_changed)

        # Presentation configuration.
        # We have only one widget here, so we reduce the margins to the bare minimum in order to
        # conserve the valuable screen space.
        # We also change the default appearance of the tab widget to make it look okay with the small margins.
        self._tabs.setTabPosition(QTabWidget.South)
        self._tabs.setDocumentMode(True)
        self.setLayout(lay_out_vertically((self._tabs, 1)))
        self.layout().setContentsMargins(0, 0, 0, 0)

    def start(self):
        self._current_widget.start()
        self._last_seen_timestamped_general_status = None

    def stop(self):
        self._current_widget.stop()
        self._last_seen_timestamped_general_status = None

    def on_general_status_update(self, timestamp: float, s: GeneralStatusView):
        self._last_seen_timestamped_general_status = timestamp, s
        self._current_widget.on_general_status_update(timestamp, s)

    def _on_current_widget_changed(self, new_widget_index: int):
        _logger.info(f'The user has changed the active widget. '
                     f'Stopping the previous widget, which was {self._current_widget!r}')
        self._current_widget.stop()

        self._current_widget = self._tabs.currentWidget()
        assert isinstance(self._current_widget, LowLevelManipulationControlSubWidgetBase)

        _logger.info(f'Starting the new widget (at index {new_widget_index}), which is {self._current_widget!r}')
        self._current_widget.start()

        # We also make sure to always provide the newly activated widget with the latest known general status,
        # in order to let it actualize its state faster.
        if self._last_seen_timestamped_general_status is not None:
            self._current_widget.on_general_status_update(*self._last_seen_timestamped_general_status)


_LLM_MODE_TO_WIDGET_TYPE_MAPPING: typing.Dict[LowLevelManipulationMode,
                                              typing.Type[LowLevelManipulationControlSubWidgetBase]] = {}


def _load_widgets():
    for llm_mode in LowLevelManipulationMode:
        module_name = f'{str(llm_mode).split(".")[-1].lower()}_widget'
        _logger.info(f'Loading module {module_name} for LLM mode {llm_mode!r}')
        try:
            module = importlib.import_module('.' + module_name, __name__)
        except ImportError:
            _logger.exception('Module load failed')
        else:
            assert issubclass(module.Widget, LowLevelManipulationControlSubWidgetBase)
            _LLM_MODE_TO_WIDGET_TYPE_MAPPING[llm_mode] = module.Widget


_load_widgets()

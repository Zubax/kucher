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
import asyncio
from logging import getLogger
from PyQt5.QtWidgets import QWidget, QTabWidget, QSizePolicy, QShortcut, QLabel
from PyQt5.QtGui import QKeySequence, QFont
from PyQt5.QtCore import Qt
from view.device_model_representation import Commander, GeneralStatusView
from view.widgets.group_box_widget import GroupBoxWidget
from view.utils import make_button, lay_out_vertically, lay_out_horizontally, get_icon

from .base import SpecializedControlWidgetBase
from .run_control_widget import RunControlWidget
from .motor_identification_control_widget import MotorIdentificationControlWidget
from .hardware_test_control_widget import HardwareTestControlWidget
from .misc_control_widget import MiscControlWidget
from .low_level_manipulation_control_widget import LowLevelManipulationControlWidget


STOP_SHORTCUT = 'Esc'
EMERGENCY_SHORTCUT = 'Ctrl+Space'


_logger = getLogger(__name__)


class ControlWidget(GroupBoxWidget):
    # noinspection PyArgumentList,PyUnresolvedReferences
    def __init__(self,
                 parent:    QWidget,
                 commander: Commander):
        super(ControlWidget, self).__init__(parent, 'Controls', 'adjust')

        self._commander: Commander = commander

        self._last_seen_timestamped_general_status: typing.Optional[typing.Tuple[float, GeneralStatusView]] = None

        self._run_widget = RunControlWidget(self, commander)
        self._motor_identification_widget = MotorIdentificationControlWidget(self, commander)
        self._hardware_test_widget = HardwareTestControlWidget(self, commander)
        self._misc_widget = MiscControlWidget(self, commander)
        self._low_level_manipulation_widget = LowLevelManipulationControlWidget(self, commander)

        self._panel = QTabWidget(self)

        self._panel.addTab(self._run_widget, get_icon('running'), 'Run')
        self._panel.addTab(self._motor_identification_widget, get_icon('caliper'), 'Motor identification')
        self._panel.addTab(self._hardware_test_widget, get_icon('pass-fail'), 'Self-test')
        self._panel.addTab(self._misc_widget, get_icon('ellipsis'), 'Miscellaneous')
        self._panel.addTab(self._low_level_manipulation_widget, get_icon('ok-hand'), 'Low-level manipulation')

        self._current_widget: SpecializedControlWidgetBase = self._hardware_test_widget
        self._panel.setCurrentWidget(self._hardware_test_widget)

        # Configuring the event handler in the last order, because it might fire while we're configuring the widgets!
        self._panel.currentChanged.connect(self._on_current_widget_changed)

        # Shared buttons
        self._stop_button =\
            make_button(self,
                        text='Stop',
                        icon_name='cancel',
                        tool_tip='Sends a regular stop command which instructs the controller to abandon the current'
                                 'task and activate the Idle task',
                        on_clicked=self._do_regular_stop)
        self._stop_button.setSizePolicy(QSizePolicy().MinimumExpanding,
                                        QSizePolicy().MinimumExpanding)

        self._emergency_button =\
            make_button(self,
                        text='EMERGENCY\nSHUTDOWN',
                        tool_tip='Unconditionally  disables and locks down the VSI until restarted',
                        on_clicked=self._do_emergency_stop)
        self._emergency_button.setSizePolicy(QSizePolicy().MinimumExpanding,
                                             QSizePolicy().MinimumExpanding)

        # Observe that the shortcuts are children of the window! This is needed to make them global.
        self._stop_shortcut = QShortcut(QKeySequence(STOP_SHORTCUT), self.window())
        self._stop_shortcut.setAutoRepeat(False)

        self._emergency_shortcut = QShortcut(QKeySequence(EMERGENCY_SHORTCUT), self.window())
        self._emergency_shortcut.setAutoRepeat(False)

        self.setEnabled(False)

        # Layout
        def make_tiny_label(text: str, alignment: int) -> QLabel:
            lbl = QLabel(text, self)
            lbl.setAlignment(alignment | Qt.AlignHCenter)
            font: QFont = lbl.font()
            font.setPointSize(round(font.pointSize() * 0.7))
            lbl.setFont(font)
            return lbl

        self.setLayout(
            lay_out_horizontally(
                (self._panel, 1),
                lay_out_vertically(
                    (self._stop_button, 1),
                    make_tiny_label(f'\u2191 {STOP_SHORTCUT} \u2191', Qt.AlignTop),
                    make_tiny_label(f'\u2193 {EMERGENCY_SHORTCUT} \u2193', Qt.AlignBottom),
                    (self._emergency_button, 1),
                )
            )
        )

    def on_connection_established(self):
        self._last_seen_timestamped_general_status = None
        self._enable()
        self._current_widget.start()

    def on_connection_loss(self):
        self._last_seen_timestamped_general_status = None
        self._current_widget.stop()
        self._disable()

    def on_general_status_update(self, timestamp: float, s: GeneralStatusView):
        self._last_seen_timestamped_general_status = timestamp, s
        self._current_widget.on_general_status_update(timestamp, s)

    def _on_current_widget_changed(self, new_widget_index: int):
        _logger.info(f'The user has changed the active widget. '
                     f'Stopping the previous widget, which was {self._current_widget!r}')
        self._current_widget.stop()

        self._current_widget = self._panel.currentWidget()
        assert isinstance(self._current_widget, SpecializedControlWidgetBase)

        _logger.info(f'Starting the new widget (at index {new_widget_index}), which is {self._current_widget!r}')
        self._current_widget.start()

        # We also make sure to always provide the newly activated widget with the latest known general status,
        # in order to let it actualize its state faster.
        if self._last_seen_timestamped_general_status is not None:
            self._current_widget.on_general_status_update(*self._last_seen_timestamped_general_status)

    # noinspection PyUnresolvedReferences
    def _enable(self):
        self._stop_shortcut.activated.connect(self._do_regular_stop)
        self._emergency_shortcut.activated.connect(self._do_emergency_stop)
        self.setEnabled(True)
        self._emergency_button.setStyleSheet('''QPushButton {
             background-color: #f00;
             font-weight: 600;
             color: #300;
        }''')

    # noinspection PyUnresolvedReferences
    def _disable(self):
        self._stop_shortcut.activated.disconnect(self._do_regular_stop)
        self._emergency_shortcut.activated.disconnect(self._do_emergency_stop)
        self.setEnabled(False)
        self._emergency_button.setStyleSheet('')

    def _do_regular_stop(self):
        self._launch(self._commander.stop())
        _logger.info('Stop button clicked (or shortcut activated)')
        self.window().statusBar().showMessage('Stop command has been sent. '
                                              'The device may choose to disregard it, depending on the current task.')
        self._current_widget.stop()

    def _do_emergency_stop(self):
        for _ in range(3):
            self._launch(self._commander.emergency())

        _logger.warning('Emergency button clicked (or shortcut activated)')
        self.window().statusBar().showMessage("DON'T PANIC. The hardware will remain unusable until restarted.")

        self._current_widget.stop()

    @staticmethod
    def _launch(coro: typing.Awaitable[None]):
        asyncio.get_event_loop().create_task(coro)

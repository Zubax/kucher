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
import string
import asyncio
from logging import getLogger
from PyQt5.QtWidgets import QWidget, QHBoxLayout, QComboBox, QCompleter, QStackedLayout, QLabel, QProgressBar
from PyQt5.QtWidgets import QVBoxLayout
from PyQt5.QtCore import QTimer, Qt
from view.utils import get_monospace_font, gui_test, make_button, show_error, get_icon
from view.device_model_representation import BasicDeviceInfo
from view.widgets import WidgetBase
from .port_discoverer import PortDiscoverer
from .little_bobby_tables_widget import LittleBobbyTablesWidget


_logger = getLogger(__name__)


_STATUS_WHEN_NOT_CONNECTED = 'Not connected'


ConnectionRequestCallback = typing.Callable[[str], typing.Awaitable[BasicDeviceInfo]]
DisconnectionRequestCallback = typing.Callable[[], typing.Awaitable[None]]


class DeviceManagementWidget(WidgetBase):
    # noinspection PyArgumentList,PyUnresolvedReferences
    def __init__(self,
                 parent: typing.Optional[QWidget],
                 on_connection_request: ConnectionRequestCallback,
                 on_disconnection_request: DisconnectionRequestCallback):
        super(DeviceManagementWidget, self).__init__(parent)
        self.setAttribute(Qt.WA_DeleteOnClose)                  # This is required to stop background timers!

        self._port_discoverer = PortDiscoverer()
        self._port_mapping: typing.Dict[str: str] = {}

        self._port_combo = QComboBox(self)
        self._port_combo.setEditable(True)
        self._port_combo.setInsertPolicy(QComboBox.NoInsert)
        self._port_combo.setSizeAdjustPolicy(QComboBox.AdjustToContents)
        self._port_combo.setFont(get_monospace_font())
        self._port_combo.lineEdit().returnPressed.connect(self._on_confirmation)

        self._connect_button = make_button(self, 'Connect', 'disconnected', on_clicked=self._on_confirmation)
        self._connect_button.setEnabled(False)              # Empty by default, therefore disabled

        self._port_combo.currentTextChanged.connect(
            lambda: self._connect_button.setEnabled(bool(self._port_combo.currentText().strip())))

        self._status_text = QLabel(self)
        self._status_text.setText(_STATUS_WHEN_NOT_CONNECTED)
        self._status_text.setWordWrap(True)

        self._device_info_widget = LittleBobbyTablesWidget(self)

        combo_completer = QCompleter()
        combo_completer.setCaseSensitivity(Qt.CaseInsensitive)
        combo_completer.setModel(self._port_combo.model())
        self._port_combo.setCompleter(combo_completer)

        self._update_timer = QTimer(self)
        self._update_timer.timeout.connect(self._update_ports)
        self._update_timer.start(2000)

        self._connection_progress_bar = QProgressBar(self)
        self._connection_progress_bar.setMinimum(0)
        self._connection_progress_bar.setMaximum(100)

        self._connection_established = False
        self._last_task: typing.Optional[asyncio.Task] = None

        self._connection_request_callback: ConnectionRequestCallback = on_connection_request
        self._disconnection_request_callback: DisconnectionRequestCallback = on_disconnection_request

        # Layout
        self._overlay = QStackedLayout(self)
        self._init_overlay_widgets()
        self.setLayout(self._overlay)

        # Initialization
        self._update_ports()

    def on_connection_loss(self, reason: str):
        """
        This method should be invoked when the connection becomes lost.
        It will cause the widget to change its state accordingly.
        :param reason: Human-readable description of the reason in one line.
        """
        if self._connection_established:
            self._switch_state_disconnected()
            self._status_text.setText(f'Connection lost: {reason.strip() or "Unknown reason"}')

    def on_connection_initialization_progress_report(self,
                                                     stage_description: str,
                                                     progress: float):
        """
        This method should be periodically invoked while connection is being initialized.
        :param stage_description: Human-readable short string displaying what is currently being done.
                                  E.g. "Opening port"
        :param progress:          A float in [0, 1] that displays how much of the work has been completed so far,
                                  where 0 - nothing, 1 - all done.
        """
        if self._overlay.currentIndex() != 1:
            raise RuntimeError('Invalid usage: this method can only be invoked when connection initialization is '
                               'in progress. Currently it is not.')

        # noinspection PyTypeChecker
        if not (0.0 <= progress <= 1.0):
            _logger.error(f'Connection progress estimate falls outside of [0, 1]: {progress}')

        stage_description = stage_description.strip()
        if stage_description[-1] in string.ascii_letters:
            stage_description += '...'

        self._connection_progress_bar.setValue(int(progress * 100))
        self._connection_progress_bar.setFormat(stage_description)

    # noinspection PyArgumentList,PyUnresolvedReferences
    def _init_overlay_widgets(self):
        # Main widget
        operational = WidgetBase(self)

        operational_layout_top = QHBoxLayout()
        operational_layout_top.addWidget(QLabel('Port:'))
        operational_layout_top.addWidget(self._port_combo, stretch=1)
        operational_layout_top.addWidget(self._connect_button)

        operational_layout_bottom = QHBoxLayout()
        operational_layout_bottom.addWidget(self._status_text)

        operational_layout = QVBoxLayout()
        operational_layout.addLayout(operational_layout_top)
        operational_layout.addLayout(operational_layout_bottom)
        operational_layout.addWidget(self._device_info_widget, 1)

        operational.setLayout(operational_layout)
        self._overlay.addWidget(operational)

        # Progress widget - shown while connecting/disconnecting
        progress = WidgetBase(self)
        progress_layout = QVBoxLayout()
        progress_layout.addStretch(1)
        progress_layout.addWidget(self._connection_progress_bar)
        progress_layout.addStretch(1)
        progress.setLayout(progress_layout)
        self._overlay.addWidget(progress)

    def _update_ports(self):
        if self._connection_established:
            return

        # noinspection PyBroadException
        try:
            ports = self._port_discoverer.get_ports()
        except Exception as ex:
            _logger.exception('Could not list ports')
            self.flash(f'Could not list ports: {ex}', duration=10)
            ports = []

        self._port_mapping = self._port_discoverer.display_ports(ports, self._port_combo)

    def _switch_state_connected(self, device_info: BasicDeviceInfo):
        self._connection_established = True
        self._overlay.setCurrentIndex(0)

        self._port_combo.setEnabled(False)

        self._connect_button.setEnabled(True)
        self._connect_button.setText('Disconnect')
        self._connect_button.setIcon(get_icon('connected'))

        self._status_text.setText('Connected')
        self._device_info_widget.set(device_info)

    def _switch_state_disconnected(self):
        self._connection_established = False
        self._overlay.setCurrentIndex(0)

        self._port_combo.setEnabled(True)

        self._connect_button.setEnabled(True)
        self._connect_button.setText('Connect')
        self._connect_button.setIcon(get_icon('disconnected'))

        self._device_info_widget.clear()
        self._status_text.setText(_STATUS_WHEN_NOT_CONNECTED)

        self._update_ports()

    async def _do_connect(self):
        _logger.info('Connection initialization task spawned')
        try:
            selected_port = self._port_mapping[str(self._port_combo.currentText()).strip()]
        except KeyError:
            selected_port = str(self._port_combo.currentText()).strip()

        # Activate the progress view and initialize it
        self._overlay.setCurrentIndex(1)
        self._connection_progress_bar.setValue(0)
        self._connection_progress_bar.setFormat('Requesting connection...')

        # noinspection PyBroadException
        try:
            device_info: BasicDeviceInfo = await self._connection_request_callback(selected_port)
        except Exception as ex:
            show_error('Could not connect',
                       f'Connection via the port {selected_port} could not be established.',
                       f'Reason: {str(ex)}',
                       parent=self)
            self._switch_state_disconnected()
        else:
            assert device_info is not None
            self._switch_state_connected(device_info)

    async def _do_disconnect(self):
        _logger.info('Connection termination task spawned')

        # Activate the progress view and initialize it
        self._overlay.setCurrentIndex(1)
        self._connection_progress_bar.setValue(100)
        self._connection_progress_bar.setFormat('Disconnecting, please wait...')

        # noinspection PyBroadException
        try:
            await self._disconnection_request_callback()
        except Exception as ex:
            _logger.exception('Disconnect request failed')
            self.flash(f'Disconnection problem: {ex}', duration=10)

        self._switch_state_disconnected()

    def _on_confirmation(self):
        # Deactivate the controls in order to prevent accidental double-entry
        self._port_combo.setEnabled(False)
        self._connect_button.setEnabled(False)

        if (self._last_task is not None) and not self._last_task.done():
            show_error("I'm sorry Dave, I'm afraid I can't do that",
                       'Cannot connect/disconnect while another connection/disconnection operation is still running',
                       f'Pending future: {self._last_task}',
                       self)
        else:
            if not self._connection_established:
                self._last_task = asyncio.get_event_loop().create_task(self._do_connect())
            else:
                self._last_task = asyncio.get_event_loop().create_task(self._do_disconnect())


# noinspection PyGlobalUndefined
@gui_test
def _unittest_connection_management_widget():
    import asyncio
    from PyQt5.QtWidgets import QApplication

    def list_prospective_ports_mock(*_):
        # noinspection PyPep8Naming
        class Mock:
            @staticmethod
            def manufacturer():
                return 'Vendor'

            @staticmethod
            def description():
                return 'Product'

            @staticmethod
            def portName():
                return 'PortName'

            @staticmethod
            def systemLocation():
                return 'SystemLocation'

            @staticmethod
            def serialNumber():
                return 'SerialNumber'

        return [Mock()]

    original_get_ports = PortDiscoverer.get_ports
    PortDiscoverer.get_ports = list_prospective_ports_mock

    good_night_sweet_prince = False
    throw = False

    async def run_events():
        while not good_night_sweet_prince:
            app.processEvents()
            await asyncio.sleep(0.01)

    # noinspection PyProtectedMember
    async def walk():
        nonlocal good_night_sweet_prince, throw

        await asyncio.sleep(2)
        print('Connect button click')
        assert not widget._connection_established
        widget._on_confirmation()

        # Should be CONNECTED now
        await asyncio.sleep(10)
        print('Disconnect button click')
        assert widget._connection_established
        widget._on_confirmation()

        # Should be DISCONNECTED now
        await asyncio.sleep(2)
        print('Connect button click with error')
        assert not widget._connection_established
        throw = True
        widget._on_confirmation()

        # Should be DISCONNECTED now
        await asyncio.sleep(10)
        print('Connect button click without error, connection loss later')
        assert not widget._connection_established
        throw = False
        widget._on_confirmation()

        # Should be CONNECTED now
        await asyncio.sleep(10)
        print('Connection loss')
        assert widget._connection_established
        widget.on_connection_loss("You're half machine, half pussy!")

        # Should be DISCONNECTED now
        await asyncio.sleep(5)
        print('Termination')
        assert not widget._connection_established
        good_night_sweet_prince = True
        widget.close()

    async def on_connection_request(selected_port):
        print('CONNECTION REQUESTED:', selected_port)
        assert selected_port == 'SystemLocation'            # See above

        await asyncio.sleep(0.5)
        widget.on_connection_initialization_progress_report('First stage', 0.2)

        await asyncio.sleep(0.5)
        widget.on_connection_initialization_progress_report('Second stage', 0.4)

        await asyncio.sleep(0.5)
        widget.on_connection_initialization_progress_report('Third stage', 0.6)

        await asyncio.sleep(0.5)
        widget.on_connection_initialization_progress_report('Fourth stage', 0.7)

        if throw:
            raise RuntimeError('Houston we have a problem!')

        await asyncio.sleep(0.5)
        widget.on_connection_initialization_progress_report('Success!', 1.0)

        out = BasicDeviceInfo(name='com.zubax.whatever',
                              description='Joo Janta 200 Super-Chromatic Peril Sensitive Sunglasses',
                              globally_unique_id=b'0123456789abcdef')
        out.software_version.major = 1
        out.software_version.minor = 2
        out.software_version.dirty_build = True
        out.hardware_version.major = 3
        out.hardware_version.minor = 4

        return out

    async def on_disconnection_request():
        print('DISCONNECTION REQUESTED')
        await asyncio.sleep(0.5)

    app = QApplication([])

    widget = DeviceManagementWidget(None,
                                    on_connection_request=on_connection_request,
                                    on_disconnection_request=on_disconnection_request)
    widget.show()

    asyncio.get_event_loop().run_until_complete(asyncio.gather(
        run_events(),
        walk()
    ))

    # Restore the global state carefully
    PortDiscoverer.get_ports = original_get_ports

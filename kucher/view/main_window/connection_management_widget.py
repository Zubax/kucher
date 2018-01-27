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
import fnmatch
import itertools
from logging import getLogger
from utils import Event
from PyQt5.QtWidgets import QWidget, QHBoxLayout, QComboBox, QCompleter, QStackedLayout, QLabel, QGroupBox, QProgressBar
from PyQt5.QtWidgets import QVBoxLayout
from PyQt5.QtCore import QTimer, Qt
from PyQt5 import QtSerialPort
from ..utils import get_monospace_font, gui_test, time_tracked, make_button
from ..widget_base import WidgetBase


_logger = getLogger(__name__)


# This list defines serial ports that will float up the list of possible ports.
# The objective is to always pre-select the best guess, best choice port, so that the user could connect in
# just one click. Vendor-product pairs located at the beginning of the list are preferred.
_PREFERABLE_VENDOR_PRODUCT_PATTERNS: typing.List[typing.Tuple[str, str]] = [
    ('*zubax*', '*telega*'),
]


# TODO: This is probably blocking IO-heavy (perhaps not on all platforms); run this logic in a background worker?
@time_tracked
def _list_prospective_ports() -> typing.List[QtSerialPort.QSerialPortInfo]:
    # https://github.com/UAVCAN/gui_tool/issues/21
    def get_score(pi: QtSerialPort.QSerialPortInfo) -> int:
        """Higher value --> better score"""
        for idx, (vendor_wildcard, product_wildcard) in enumerate(_PREFERABLE_VENDOR_PRODUCT_PATTERNS):
            vendor_match = fnmatch.fnmatch(pi.manufacturer().lower(), vendor_wildcard.lower())
            product_match = fnmatch.fnmatch(pi.description().lower(), product_wildcard.lower())
            if vendor_match and product_match:
                return -idx

        return -9999

    ports = QtSerialPort.QSerialPortInfo.availablePorts()
    ports = filter(lambda pi: not pi.isBusy(), ports)

    # noinspection PyBroadException
    try:
        ports = sorted(ports, key=lambda pi: pi.manufacturer() + pi.description() + pi.systemLocation())
    except Exception:
        _logger.exception('Pre-sorting failed')

    ports = sorted(ports, key=lambda pi: -get_score(pi))
    return list(ports)


def _update_port_list(ports: typing.List[QtSerialPort.QSerialPortInfo],
                      combo: QComboBox) -> typing.Dict[str, str]:
    known_keys = set()
    remove_indices = []
    was_empty = combo.count() == 0

    def make_description(p: QtSerialPort.QSerialPortInfo) -> str:
        out = f'{p.portName()}: {p.manufacturer() or "Unknown vendor"} - {p.description() or "Unknown product"}'
        if p.serialNumber().strip():
            out += ' #' + str(p.serialNumber())

        return out

    ports = {
        make_description(x): x.systemLocation() for x in ports
    }

    # Marking known and scheduling for removal
    for idx in itertools.count():
        tx = combo.itemText(idx)
        if not tx:
            break

        known_keys.add(tx)
        if tx not in ports:
            _logger.debug('Removing iface %r', tx)
            remove_indices.append(idx)

    # Removing - starting from the last item in order to retain indexes
    for idx in remove_indices[::-1]:
        combo.removeItem(idx)

    # Adding new items - starting from the last item in order to retain the final order
    for key in list(ports.keys())[::-1]:
        if key not in known_keys:
            _logger.debug('Adding iface %r', key)
            combo.insertItem(0, key)

    # Updating selection
    if was_empty:
        combo.setCurrentIndex(0)

    return ports


class ConnectionManagementWidget(WidgetBase):
    def __init__(self, parent: QWidget):
        super(ConnectionManagementWidget, self).__init__(parent)
        self.setAttribute(Qt.WA_DeleteOnClose)                  # This is required to stop background timers!

        self._port_mapping: typing.Dict[str: str] = {}

        self._port_combo = QComboBox(self)
        self._port_combo.setEditable(True)
        self._port_combo.setInsertPolicy(QComboBox.NoInsert)
        self._port_combo.setSizeAdjustPolicy(QComboBox.AdjustToContents)
        self._port_combo.setFont(get_monospace_font())
        self._port_combo.lineEdit().returnPressed.connect(self._on_confirmation)

        self._connect_button = make_button(self, 'Connect', 'disconnected', on_clicked=self._on_confirmation)

        self._connected_device_description = QLabel(self)
        self._connected_device_description.setText('Not connected')

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

        self.connection_requested_event = Event()   # (Optional[str]) -> bool

        # Layout
        self._overlay = QStackedLayout(self)

        operational_group = QGroupBox('Device connection', self)

        operational_layout_top = QHBoxLayout()
        operational_layout_top.addWidget(QLabel('Port:'))
        operational_layout_top.addWidget(self._port_combo, stretch=1)
        operational_layout_top.addWidget(self._connect_button)

        operational_layout_bottom = QHBoxLayout()
        operational_layout_bottom.addWidget(self._connected_device_description)

        operational_layout = QVBoxLayout()
        operational_layout.addLayout(operational_layout_top)
        operational_layout.addLayout(operational_layout_bottom)

        operational_group.setLayout(operational_layout)
        self._overlay.addWidget(operational_group)

        progress_group = QGroupBox('Device connection progress', self)
        progress_layout = QHBoxLayout()
        progress_layout.addWidget(self._connection_progress_bar)
        progress_group.setLayout(progress_layout)
        self._overlay.addWidget(progress_group)

        self.setLayout(self._overlay)

        min_width = 800
        self.setMinimumWidth(min_width)
        self.setFixedHeight(self._overlay.minimumHeightForWidth(min_width))

        # Initialization
        self._update_ports()

    def on_connection_lost(self):
        self._connection_established = False
        self._overlay.setCurrentIndex(0)

        self._port_combo.setEnabled(True)
        self._connect_button.setText('Connect')
        self._connected_device_description.setText('Not connected')

        self._update_ports()

    def on_connection_established(self,
                                  device_description: str,
                                  software_version_major_minor: typing.Tuple[int, int],
                                  hardware_version_major_minor: typing.Tuple[int, int],
                                  device_unique_id: bytes):
        self._connection_established = True
        self._overlay.setCurrentIndex(0)

        self._port_combo.setEnabled(False)
        self._connect_button.setText('Disconnect')

        sw_ver = '.'.join(map(str, software_version_major_minor))
        hw_ver = '.'.join(map(str, hardware_version_major_minor))
        self._connected_device_description.setText(f'Connected to: {device_description}, '
                                                   f'SW v{sw_ver}, HW v{hw_ver}, '
                                                   f'UID #{device_unique_id.hex()}')

    def on_connection_initialization_progress(self, stage_description: str, progress: float):
        self._connection_established = False
        self._overlay.setCurrentIndex(1)

        stage_description = stage_description.strip()
        if stage_description[-1] in string.ascii_letters:
            stage_description += '...'

        self._connection_progress_bar.setValue(int(progress * 100))
        self._connection_progress_bar.setFormat(stage_description)

    def _update_ports(self):
        if self._connection_established:
            return

        # noinspection PyBroadException
        try:
            ports = _list_prospective_ports()
        except Exception as ex:
            _logger.exception('Could not list ports')
            self.flash(f'Could not list ports: {ex}')
            ports = []

        self._port_mapping = _update_port_list(ports, self._port_combo)

    def _on_confirmation(self):
        if not self._connection_established:
            try:
                selected_port = self._port_mapping[str(self._port_combo.currentText()).strip()]
            except KeyError:
                selected_port = str(self._port_combo.currentText()).strip()

            self.on_connection_initialization_progress('Requesting connection...', 0)
        else:
            self.on_connection_lost()
            selected_port = None

        self.connection_requested_event(selected_port)


@gui_test
def _unittest_connection_management_widget():
    global _list_prospective_ports

    from PyQt5.QtWidgets import QApplication
    app = QApplication([])

    def list_prospective_ports_mock():
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

    _list_prospective_ports = list_prospective_ports_mock

    # noinspection PyProtectedMember
    def connect():
        widget._on_confirmation()
        timer.singleShot(500, lambda: progress(0))

    def progress(value: float):
        assert selected_port == 'SystemLocation'  # See above
        if value < 1:
            timer.singleShot(500, lambda: progress(value + 0.1))
            widget.on_connection_initialization_progress(f'Progress {int(value * 100)}%', value)
        else:
            widget.connection_requested_event -= on_connection_requested
            widget.connection_requested_event += on_disconnection_requested
            timer.singleShot(3000, disconnect)
            widget.on_connection_established('Device Description', (1, 2), (3, 4), b'0123456789abcdef')

    # noinspection PyProtectedMember
    def disconnect():
        assert selected_port == 'SystemLocation'  # See above
        widget._on_confirmation()
        timer.singleShot(3000, finalize)

    def finalize():
        assert selected_port is None
        widget.close()

    selected_port = None

    def on_connection_requested(p):
        nonlocal selected_port
        selected_port = p
        print('CONNECTION REQUESTED:', selected_port)
        assert selected_port == 'SystemLocation'            # See above

    def on_disconnection_requested(p):
        nonlocal selected_port
        selected_port = p
        assert selected_port is None

    widget = ConnectionManagementWidget(None)
    widget.show()

    widget.connection_requested_event += on_connection_requested

    timer = QTimer()
    timer.singleShot(1000, connect)

    app.exec()

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
import fnmatch
import itertools
from logging import getLogger
from PyQt5.QtWidgets import QComboBox
from PyQt5.QtGui import QIcon
from PyQt5 import QtSerialPort

from kucher.view.utils import time_tracked, get_icon


_logger = getLogger(__name__)


# This list defines serial ports that will float up the list of possible ports.
# The objective is to always pre-select the best guess, best choice port, so that the user could connect in
# just one click. Vendor-product pairs located at the beginning of the list are preferred.
_PREFERABLE_VENDOR_PRODUCT_PATTERNS: typing.List[typing.Tuple[str, str]] = [
    ('*zubax*', '*telega*'),
]


class PortDiscoverer:
    """
    This is a bit low-effort, I mostly pulled this code from the UAVCAN GUI Tool.
    """
    def __init__(self):
        pass

    # TODO: This is probably blocking IO-heavy (perhaps not on all platforms); run this logic in a background worker?
    # noinspection PyArgumentList
    @time_tracked
    def get_ports(self) -> typing.List[QtSerialPort.QSerialPortInfo]:
        # https://github.com/UAVCAN/gui_tool/issues/21
        def get_score(pi: QtSerialPort.QSerialPortInfo) -> int:
            idx = _get_index_of_first_matching_preferable_pattern(pi)
            return (-idx) if idx is not None else (-9999)

        ports = QtSerialPort.QSerialPortInfo.availablePorts()
        ports = filter(lambda pi: not pi.isBusy(), ports)

        # noinspection PyBroadException
        try:
            ports = sorted(ports, key=lambda pi: pi.manufacturer() + pi.description() + pi.systemLocation())
        except Exception:
            _logger.exception('Pre-sorting failed')

        ports = sorted(ports, key=lambda pi: -get_score(pi))
        return list(ports)

    @staticmethod
    def display_ports(ports: typing.List[QtSerialPort.QSerialPortInfo],
                      combo: QComboBox) -> typing.Dict[str, str]:
        known_keys = set()
        remove_indices = []
        was_empty = combo.count() == 0

        def make_description(p: QtSerialPort.QSerialPortInfo) -> str:
            out = f'{p.portName()}: {p.manufacturer() or "Unknown vendor"} - {p.description() or "Unknown product"}'
            if p.serialNumber().strip():
                out += ' #' + str(p.serialNumber())

            return out

        description_location_mapping = {}
        description_icon_mapping = {}
        for x in ports:
            desc = make_description(x)
            icon = _get_port_icon(x)
            description_location_mapping[desc] = x.systemLocation()
            if icon:
                description_icon_mapping[desc] = icon

        # Marking known and scheduling for removal
        for idx in itertools.count():
            tx = combo.itemText(idx)
            if not tx:
                break

            known_keys.add(tx)
            if tx not in description_location_mapping:
                _logger.debug('Removing port %r', tx)
                remove_indices.append(idx)

        # Removing - starting from the last item in order to retain indexes
        for idx in remove_indices[::-1]:
            combo.removeItem(idx)

        # Adding new items - starting from the last item in order to retain the final order
        for key in list(description_location_mapping.keys())[::-1]:
            if key not in known_keys:
                _logger.debug('Adding port %r', key)
                try:
                    combo.insertItem(0, description_icon_mapping[key], key)
                except KeyError:
                    combo.insertItem(0, key)

        # Updating selection
        if was_empty:
            combo.setCurrentIndex(0)

        return description_location_mapping


def _get_index_of_first_matching_preferable_pattern(pi: QtSerialPort.QSerialPortInfo) -> typing.Optional[int]:
    for idx, (vendor_wildcard, product_wildcard) in enumerate(_PREFERABLE_VENDOR_PRODUCT_PATTERNS):
        vendor_match = fnmatch.fnmatch(pi.manufacturer().lower(), vendor_wildcard.lower())
        product_match = fnmatch.fnmatch(pi.description().lower(), product_wildcard.lower())
        if vendor_match and product_match:
            return idx


def _get_port_icon(p: QtSerialPort.QSerialPortInfo) -> typing.Optional[QIcon]:
    if _get_index_of_first_matching_preferable_pattern(p) is not None:
        return get_icon('zee')
    else:
        return get_icon('question-mark')

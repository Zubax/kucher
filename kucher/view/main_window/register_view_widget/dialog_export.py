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

import os
import yaml
import asyncio

from logging import getLogger
from PyQt5.QtWidgets import QWidget, QFileDialog, QTableWidget, QTableWidgetItem, QDialog, QLabel, \
    QPushButton, QHeaderView

from kucher.view.device_model_representation import Register
from kucher.view.utils import show_error, lay_out_horizontally, lay_out_vertically, get_monospace_font

_logger = getLogger(__name__)


class ExportDialogWindow(QWidget):

    def __init__(self, registers):
        self.registers = registers
        super().__init__()
        self.setGeometry(10, 10, 1000, 700)
        self._saveFileDialog()

    def _saveFileDialog(self):
        self.fileName, _ = QFileDialog.getSaveFileName(self, 'Export configuration file', 'config.yml',
                                                       'YAML Files (*.yml  *.yaml);;All Files (*)')
        if not self.fileName:
            return
        try:
            _file = open(self.fileName, 'w+')

        except IOError:
            _logger.exception(f'File {self.fileName} could not be open')
            return

        async def executor():
            register_yaml = {}
            for reg in self.registers:
                if reg.mutable:
                    try:
                        register_yaml[reg.name] = await reg.read_through()
                    except Exception as ex:
                        _logger.exception(f'Register {reg.name} could not be read')

            yaml.dump(register_yaml, _file, tags=False, default_flow_style=False)
            _file.close()

        asyncio.get_event_loop().create_task(executor())


class ImportDialogWindow(QWidget):

    def __init__(self, parent, registers):
        self.parent = parent
        self.registers = registers
        super().__init__()
        self.setGeometry(10, 10, 1000, 700)
        self._saveFileDialog()

    def _saveFileDialog(self):
        self.fileName, _ = QFileDialog.getOpenFileName(self, 'Import configuration file', '',
                                                       'YAML Files (*.yml *.yaml);;All Files (*)')
        if not self.fileName:
            return
        try:
            self._file = open(self.fileName, 'r')
        except IOError:
            _logger.exception(f'File {self.fileName} could not be open')
            return

        # Check before writing any register if they are available on the device and within the permitted range
        self.imported_registers = yaml.safe_load(self._file)
        try:
            for reg_check in self.registers:
                if reg_check.name in self.imported_registers.keys():
                    if not reg_check.mutable:
                        show_error('Import failed',
                                   f'Cannot import {self.fileName}',
                                   f'This parameter cannot be modified on this device:\n{reg_check.name}',
                                   self.parent)
                        self._file.close()
                        _logger.exception(f'Import failed : This parameter cannot be modified on this '
                                          f'device: {reg_check.name}')
                        return

                    elif reg_check.has_min_and_max_values and reg_check.type_id != Register.ValueType.BOOLEAN:
                        if not (reg_check.min_value <= self.imported_registers[reg_check.name] <= reg_check.max_value):
                            show_error('Import failed',
                                       f'Cannot import {self.fileName}',
                                       f'This parameter value is outside permitted range:\n{reg_check.name}',
                                       self.parent)
                            self._file.close()
                            _logger.exception('Import failed :This parameter value is outside '
                                              f'permitted range: {reg_check.name}')
                            return

        except Exception as ex:
            show_error('Import failed',
                       f'Cannot import {self.fileName}',
                       f'Reason: {str(ex)}',
                       self.parent)
            _logger.exception(f'Could not write registers: {ex!r}')
            self._file.close()
            return

        self._file.close()

        async def executor():
            for _attempt in range(3):
                try:
                    await self._writeRegisters()
                    break
                except Exception as ex:
                    _logger.exception(f'Registers could not be loaded (attempt {_attempt}/3')

        asyncio.get_event_loop().create_task(executor())

    async def _writeRegisters(self):
        self._unwritten_registers = []
        for reg in self.registers:
            if reg.mutable and (reg.name in self.imported_registers.keys()):

                try:
                    value = self.imported_registers[reg.name]
                    await reg.write_through(value)

                except KeyError:
                    self._unwritten_registers.append([reg.name,
                                                     reg._cached_value,
                                                     ['(not found)']])
                    _logger.exception(f'Register {reg.name} could not be loaded')
                    pass

                except Exception as ex:
                    self._unwritten_registers.append([reg.name,
                                                     reg._cached_value,
                                                     self.imported_registers[reg.name]])
                    _logger.exception(f'Register {reg.name} could not be loaded')
                    pass
        if self._unwritten_registers:
            self._displayWarningMessage()

    def _displayWarningMessage(self):
        _warning = QDialog(self.parent)
        _warning.setGeometry(10, 10, 1000, 400)
        _warning.setWindowTitle('Unwritable parameters')

        _tableWidget = QTableWidget(_warning)
        _tableWidget.setFont(get_monospace_font())
        _tableWidget.setRowCount(len(self._unwritten_registers))
        _tableWidget.setColumnCount(3)

        _tableWidget.setHorizontalHeaderLabels(['Full name', 'Current value', 'Requested value'])
        _tableWidget.horizontalHeader().setStretchLastSection(True)

        _header = _tableWidget.horizontalHeader()
        _header.setSectionResizeMode(0, QHeaderView.ResizeToContents)
        _header.setSectionResizeMode(1, QHeaderView.Stretch)
        _header.setSectionResizeMode(2, QHeaderView.Stretch)

        _tableWidget.verticalHeader().hide()
        _tableWidget.verticalHeader().setSectionResizeMode(_tableWidget.verticalHeader().ResizeToContents)

        for i in range(len(self._unwritten_registers)):
            _name = self._unwritten_registers[i][0]
            _current_value = self._unwritten_registers[i][1]
            _requested_value = self._unwritten_registers[i][2]
            _tableWidget.setItem(i, 0, QTableWidgetItem(_name + ' '))
            _tableWidget.setItem(i, 1, QTableWidgetItem(', '.join(str(e) for e in _current_value)))
            _tableWidget.setItem(i, 2, QTableWidgetItem(', '.join(str(e) for e in _requested_value)))

        _btn_ok = QPushButton(_warning)
        _btn_ok.setText('Ok')
        _btn_ok.clicked.connect(_warning.close)

        _warning.setLayout(
            lay_out_vertically(
                lay_out_horizontally(QLabel('Some configuration parameters could not be written:', _warning)),
                lay_out_horizontally(_tableWidget),
                lay_out_horizontally(_btn_ok),
            )
        )

        _warning.show()

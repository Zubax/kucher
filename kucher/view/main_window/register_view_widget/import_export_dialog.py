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
import math
import itertools

from logging import getLogger
from PyQt5.QtWidgets import QWidget, QFileDialog, QTableWidget, QTableWidgetItem, QDialog, QLabel, \
    QPushButton, QHeaderView, QMessageBox
from popcop.standard.register import ValueType

from kucher.view.device_model_representation import Register
from kucher.view.utils import show_error, lay_out_horizontally, lay_out_vertically, get_monospace_font

_logger = getLogger(__name__)


def export_registers(parent, registers):
    """
    Store all mutable and persistent registers in a .yml file
    """
    dialog_box = QWidget()
    dialog_box.setGeometry(10, 10, 1000, 700)

    file_name, _ = QFileDialog.getSaveFileName(dialog_box, 'Export configuration file', 'config.yml',
                                               'YAML Files (*.yml  *.yaml);;All Files (*)')
    if not file_name:
        return
    try:
        _file = open(file_name, 'w+')

    except Exception as ex:
        show_error('Export failed',
                   f'Cannot export {file_name}',
                   f'Error: {ex}',
                   parent)
        _logger.exception(f'File {file_name} could not be exported: {ex!r}')
        return

    async def executor():
        register_yaml = {}
        for reg in registers:
            if reg.mutable and reg.persistent:
                try:
                    register_yaml[reg.name] = await reg.read_through()
                except Exception as ex:
                    show_error('Export failed',
                               f'Cannot export {file_name}',
                               f'This parameter cannot be read:\n{reg.name}',
                               parent)
                    _logger.exception(f'Register {reg} could not be read')
                    return

        yaml.dump(register_yaml, _file)
        _file.close()

    asyncio.get_event_loop().create_task(executor())

    display_sucess_message('Export successful',
                           f'Parameters have been successfully exported to:\n{file_name}',
                           '',
                           parent)


def import_registers(parent, registers):
    """
    Import registers values from a .yml (or .yaml) file.
    The file must match the following pattern:

    full_register_name:
    - register_value

    e.g:

    ctl.num_attempts:
    - 100
    ctl.pwron_slftst:
    - false
    ctl.spinup_durat:
    - 1.7000000476837158

    It can only contain available registers on the current device, with values within the allowed range. The values
    must be the right type and dimension. If a register is not mentioned in the file, it will keep its former value.
    """
    dialog_box = QWidget()
    dialog_box.setGeometry(10, 10, 1000, 700)
    file_name, _ = QFileDialog.getOpenFileName(dialog_box, 'Import configuration file', '',
                                               'YAML Files (*.yml *.yaml);;All Files (*)')
    if not file_name:
        return
    try:
        file = open(file_name, 'r')
    except IOError:
        _logger.exception(f'File {file_name} could not be open')
        return

    imported_registers = yaml.load(file, Loader=yaml.Loader)

    if imported_registers:
        check_passed = check_registers(parent, file_name, file, registers, imported_registers)
        if check_passed:
            write_registers(parent, file_name, registers, imported_registers)
    else:
        write_registers(parent, file_name, registers, imported_registers)


def check_registers(parent, file_name, file, registers, imported_registers, ):
    print("checking...")
    try:
        for reg_check in registers:
            if reg_check.name in imported_registers:
                if not (reg_check.mutable and reg_check.persistent):
                    show_error('Import failed',
                               f'Cannot import {file_name}',
                               f'This parameter cannot be modified on this device:\n{reg_check.name}',
                               parent)
                    file.close()
                    _logger.exception(f'Import failed: this parameter cannot be modified on this device: {reg_check}')
                    return False

                elif not check_type(reg_check, imported_registers[reg_check.name]):
                    show_error('Import failed',
                               f'Cannot import {file_name}',
                               f'This parameter type is incorrect:\n{reg_check.name}',
                               parent)
                    file.close()
                    _logger.exception(f'Import failed: this parameter type is incorrect {reg_check}')
                    return False

                if len(imported_registers[reg_check.name]) != len(reg_check.cached_value):
                    show_error('Import failed',
                               f'Cannot import {file_name}',
                               f'This parameter dimension is incorrect:\n{reg_check.name}',
                               parent)
                    file.close()
                    _logger.exception(f'Import failed: this parameter dimension is incorrect {reg_check}')
                    return False

                elif reg_check.has_min_and_max_values and reg_check.type_id != Register.ValueType.BOOLEAN:
                    if not (reg_check.min_value <= imported_registers[reg_check.name] <= reg_check.max_value):
                        show_error('Import failed',
                                   f'Cannot import {file_name}',
                                   f'This parameter value is outside permitted range:\n{reg_check.name}',
                                   parent)
                        file.close()
                        _logger.exception('Import failed: this parameter value is outside '
                                          f'permitted range: {reg_check}')
                        return False

    except Exception as ex:
        show_error('Import failed',
                   f'Cannot import {file_name}',
                   f'Reason: {str(ex)}',
                   parent)
        _logger.exception(f'Could not write registers: {ex!r}')
        file.close()
        return False
    return True

    file.close()


def write_registers(parent, file_name, registers, imported_registers):
    async def executor():
        unwritten_registers = []
        changed_registers_number = 0
        if imported_registers:
            for reg in imported_registers:
                for _attempt in range(3):
                    try:
                        old_reg = next((r for r in registers if r.name == reg))
                        new_value = imported_registers[reg]
                        old_value = await old_reg.read_through()
                        equal = is_equal(old_reg.type_id, old_value, imported_registers[reg])

                        if not equal:
                            await old_reg.write_through(new_value)
                            changed_registers_number += 1
                        break

                    except Exception as ex:
                        if _attempt == 2:
                            try:
                                old_reg = next((r for r in registers if r.name == reg))
                                old_value = await old_reg.read_through()
                            except Exception as ex:
                                old_value = ['(unknown)']

                            unwritten_registers.append([reg, old_value, imported_registers[reg]])
                        _logger.exception(f'Register {reg} could not be loaded (attempt {_attempt + 1}/3)')

            if unwritten_registers:
                display_warning_message(parent, unwritten_registers)

        total_registers_number = sum(1 for b in registers if b.mutable and b.persistent)

        display_sucess_message('Import successful',
                               f'{file_name} have been successfully imported',
                               f'{changed_registers_number} registers have been edited, '
                               f'{total_registers_number - changed_registers_number} were left unchanged',
                               parent)

    asyncio.get_event_loop().create_task(executor())


def check_type(old_reg, new_value):
    # iterates over 'new_value' and check if all of its elements are the same type as 'old_reg' value
    _type_float = True
    _type_int = True
    _type_bool = True
    for e in new_value:
        _type_float = _type_float and isinstance(e, float) and (old_reg.type_id in (ValueType.F32,
                                                                                    ValueType.F64))
        _type_int = _type_int and isinstance(e, int) and (old_reg.type_id in (ValueType.I64,
                                                                              ValueType.I32,
                                                                              ValueType.I16,
                                                                              ValueType.I8,
                                                                              ValueType.U64,
                                                                              ValueType.U32,
                                                                              ValueType.U16,
                                                                              ValueType.U8))
        _type_bool = _type_bool and isinstance(e, bool) and old_reg.type_id == ValueType.BOOLEAN
    return _type_float or _type_int or _type_bool


def is_equal(old_type, old_value, new_value):
    if old_type in (ValueType.F32, ValueType.F64):
        # Absolute tolerance equals the epsilon as per IEEE754
        absolute_tolerance = {
            ValueType.F32: 1e-6,
            ValueType.F64: 1e-15,
        }[old_type]

        # Relative tolerance is roughly the epsilon multiplied by 10...100
        relative_tolerance = {
            ValueType.F32: 1e-5,
            ValueType.F64: 1e-13,
        }[old_type]

        return all(map(lambda args: math.isclose(*args, rel_tol=relative_tolerance, abs_tol=absolute_tolerance),
                       itertools.zip_longest(old_value, new_value)))
    else:
        return new_value == old_value


def display_sucess_message(title, text, informative_text, parent):
    mbox = QMessageBox(parent)
    mbox.setWindowTitle(title)
    mbox.setText(text)
    mbox.setInformativeText(informative_text)
    mbox.setStandardButtons(QMessageBox.Ok)
    mbox.show()


def display_warning_message(parent, unwritten_registers):
    _warning = QDialog(parent)
    _warning.setGeometry(10, 10, 1000, 400)
    _warning.setWindowTitle('Unwritable parameters')

    _tableWidget = QTableWidget(_warning)
    _tableWidget.setFont(get_monospace_font())
    _tableWidget.setRowCount(len(unwritten_registers))
    _tableWidget.setColumnCount(3)

    _tableWidget.setHorizontalHeaderLabels(['Full name', 'Current value', 'Requested value'])
    _tableWidget.horizontalHeader().setStretchLastSection(True)

    _header = _tableWidget.horizontalHeader()
    _header.setSectionResizeMode(0, QHeaderView.ResizeToContents)
    _header.setSectionResizeMode(1, QHeaderView.Stretch)
    _header.setSectionResizeMode(2, QHeaderView.Stretch)

    _tableWidget.verticalHeader().hide()
    _tableWidget.verticalHeader().setSectionResizeMode(_tableWidget.verticalHeader().ResizeToContents)

    for i in range(len(unwritten_registers)):
        _name = unwritten_registers[i][0]
        _current_value = unwritten_registers[i][1]
        _requested_value = unwritten_registers[i][2]
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

    _warning.exec()

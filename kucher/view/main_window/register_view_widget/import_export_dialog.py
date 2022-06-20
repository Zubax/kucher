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
# Author: Loic Gilbert <loic.gilbert@zubax.com>
#

import os
import yaml
import asyncio
import math
import itertools
import enum
import typing

from logging import getLogger
from PyQt5.QtWidgets import (
    QWidget,
    QFileDialog,
    QTableWidget,
    QTableWidgetItem,
    QDialog,
    QLabel,
    QPushButton,
    QHeaderView,
    QMessageBox,
)
from popcop.standard.register import ValueType

from kucher.view.widgets import WidgetBase
from kucher.view.device_model_representation import Register
from kucher.view.utils import (
    show_error,
    lay_out_horizontally,
    lay_out_vertically,
    get_monospace_font,
)

_logger = getLogger(__name__)


class CheckResult(enum.Enum):
    NOT_MUTABLE = enum.auto()
    INCORRECT_TYPE = enum.auto()
    INCORRECT_DIMENSION = enum.auto()
    OUTSIDE_RANGE = enum.auto()
    UNKNOWN = enum.auto()
    NO_ERROR = enum.auto()


CHECK_RESULT_MAPPING: typing.Dict[CheckResult, str] = {
    CheckResult.NOT_MUTABLE: "This parameter cannot be modified on this device: ",
    CheckResult.INCORRECT_TYPE: "This parameter type is incorrect: ",
    CheckResult.INCORRECT_DIMENSION: "This parameter dimension is incorrect: ",
    CheckResult.OUTSIDE_RANGE: "This parameter value is outside permitted range: ",
    CheckResult.UNKNOWN: "Reason: ",
}


def export_registers(parent: WidgetBase, registers: list):
    """
    Stores all mutable and persistent registers in a .yml file.
    """
    dialog_box = QWidget()
    dialog_box.setGeometry(10, 10, 1000, 700)

    file_name, _ = QFileDialog.getSaveFileName(
        dialog_box,
        "Export configuration file",
        "config.yml",
        "YAML Files (*.yml  *.yaml);;All Files (*)",
    )
    if not file_name:
        return
    try:
        _file = open(file_name, "w+")
    except Exception as ex:
        show_error(
            "Export failed", f"Cannot open {file_name}", f"Error: {str(ex)}", parent
        )
        _logger.exception(f"File {file_name} could not be open: {str(ex)}")
        return

    async def executor():
        try:
            register_yaml = {}
            for reg in registers:
                if reg.mutable and reg.persistent:
                    register_yaml[reg.name] = await reg.read_through()

            yaml.dump(register_yaml, _file)
            display_sucess_message(
                "Export successful",
                f"Parameters have been successfully exported to:\n{file_name}",
                parent,
            )
        except Exception as ex:
            show_error("Export failed", f"Parameters cannot be read.", str(ex), parent)
            _logger.exception(f"Registers could not be read")
        finally:
            _file.close()

    asyncio.get_event_loop().create_task(executor())


def import_registers(parent: WidgetBase, registers: list):
    """
    Imports registers values from a .yml (or .yaml) file.
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
    file_name, _ = QFileDialog.getOpenFileName(
        dialog_box,
        "Import configuration file",
        "",
        "YAML Files (*.yml *.yaml);;All Files (*)",
    )
    if not file_name:
        return
    try:
        with open(file_name, "r") as file:
            imported_registers = yaml.load(file, Loader=yaml.Loader)
    except IOError as ex:
        _logger.exception(f"File {file_name} could not be open")
        show_error(
            "Import failed", f"Cannot open {file_name}", f"Error: {str(ex)}", parent
        )
        return

    except Exception as ex:
        _logger.exception(f"File {file_name} could not be parsed")
        show_error(
            "Import failed", f"Cannot read {file_name}", f"Error: {str(ex)}", parent
        )
        return

    if imported_registers:
        result, detail = check_registers(registers, imported_registers)
        if result == CheckResult.NO_ERROR:
            write_registers(parent, file_name, registers, imported_registers)
        else:
            show_error_box(result, detail, file_name, parent)


def check_registers(registers: list, imported_registers: dict) -> CheckResult:
    try:
        for reg_check in registers:
            if reg_check.name in imported_registers:
                if not (reg_check.mutable and reg_check.persistent):
                    _logger.error(
                        f"Import failed: this parameter cannot be modified on this device: {reg_check}"
                    )
                    return CheckResult.NOT_MUTABLE, reg_check.name

                elif not check_type(reg_check, imported_registers[reg_check.name]):
                    _logger.error(
                        f"Import failed: this parameter type is incorrect {reg_check}"
                    )
                    return CheckResult.INCORRECT_TYPE, reg_check.name

                elif len(imported_registers[reg_check.name]) != len(
                    reg_check.cached_value
                ):
                    _logger.error(
                        f"Import failed: this parameter dimension is incorrect {reg_check}"
                    )
                    return CheckResult.INCORRECT_DIMENSION, reg_check.name

                elif (
                    reg_check.has_min_and_max_values
                    and reg_check.type_id != Register.ValueType.BOOLEAN
                ):
                    if not (
                        reg_check.min_value
                        <= imported_registers[reg_check.name]
                        <= reg_check.max_value
                    ):
                        _logger.error(
                            f"Import failed: this parameter value is outside permitted range {reg_check}"
                        )
                        return CheckResult.OUTSIDE_RANGE, reg_check.name

    except Exception as ex:
        _logger.exception(f"Could not write registers: {str(ex)}")
        return CheckResult.UNKNOWN, str(ex)

    return CheckResult.NO_ERROR, ""


def show_error_box(
    result: CheckResult, detail: str, file_name: str, parent: WidgetBase
):
    show_error(
        "Import failed",
        f"Cannot import {file_name}",
        CHECK_RESULT_MAPPING[result] + detail,
        parent,
    )


def write_registers(
    parent: WidgetBase, file_name: str, registers: list, imported_registers: dict
):
    async def executor():
        unwritten_registers = []
        for reg in imported_registers:
            _attempt = 0
            while True:
                try:
                    old_reg = next((r for r in registers if r.name == reg))
                    await old_reg.write_through(imported_registers[reg])
                    break

                except Exception as ex:
                    _attempt += 1
                    _logger.exception(
                        f"Register {reg} could not be loaded (attempt {_attempt}/3)"
                    )
                    if _attempt >= 3:
                        try:
                            old_reg = next((r for r in registers if r.name == reg))
                            old_value = old_reg.cached_value
                        except Exception:
                            old_value = ["(unknown)"]

                        unwritten_registers.append(
                            [reg, old_value, imported_registers[reg]]
                        )
                        break

        if unwritten_registers:
            display_warning_message(
                "Import successful",
                f"{file_name} have been successfully imported.",
                parent,
                unwritten_registers,
            )

        else:
            display_sucess_message(
                "Import successful",
                f"{file_name} have been successfully imported.",
                parent,
            )

    asyncio.get_event_loop().create_task(executor())


def check_type(old_reg: Register, new_value: list) -> bool:
    """
    Checks if all elements of new_value are the same type as old_reg value.
    """
    _int_types = (
        ValueType.I64,
        ValueType.I32,
        ValueType.I16,
        ValueType.I8,
        ValueType.U64,
        ValueType.U32,
        ValueType.U16,
        ValueType.U8,
    )

    _float_types = (ValueType.F32, ValueType.F64)

    # >>> isinstance(True, int)
    # True
    if all(map(lambda _type: isinstance(_type, bool), new_value)):
        return old_reg.type_id == ValueType.BOOLEAN
    else:
        _type_float = all(map(lambda _type: isinstance(_type, float), new_value)) and (
            old_reg.type_id in _float_types
        )
        # allow the user to enter an int if expected value is float
        _type_int = all(map(lambda _type: isinstance(_type, int), new_value)) and (
            old_reg.type_id in _float_types + _int_types
        )
        return _type_float or _type_int


def display_sucess_message(title: str, text: str, parent: WidgetBase):
    mbox = QMessageBox(parent)
    mbox.setWindowTitle(title)
    mbox.setText(text)
    mbox.setStandardButtons(QMessageBox.Ok)
    mbox.show()


def display_warning_message(
    title: str, text: str, parent: WidgetBase, unwritten_registers: list
):
    _warning = QDialog(parent)
    _warning.setWindowTitle(title)

    _tableWidget = QTableWidget(_warning)
    _tableWidget.setFont(get_monospace_font())
    _tableWidget.setRowCount(len(unwritten_registers))
    _tableWidget.setColumnCount(3)

    _tableWidget.setHorizontalHeaderLabels(
        ["Full name", "Current value", "Requested value"]
    )
    _tableWidget.horizontalHeader().setStretchLastSection(True)

    _header = _tableWidget.horizontalHeader()
    _header.setSectionResizeMode(0, QHeaderView.ResizeToContents)
    _header.setSectionResizeMode(1, QHeaderView.Stretch)
    _header.setSectionResizeMode(2, QHeaderView.Stretch)

    _tableWidget.verticalHeader().hide()
    _tableWidget.verticalHeader().setSectionResizeMode(
        _tableWidget.verticalHeader().ResizeToContents
    )

    for i in range(len(unwritten_registers)):
        _name = unwritten_registers[i][0]
        _current_value = unwritten_registers[i][1]
        _requested_value = unwritten_registers[i][2]
        _tableWidget.setItem(i, 0, QTableWidgetItem(_name + " "))
        _tableWidget.setItem(
            i, 1, QTableWidgetItem(", ".join(str(e) for e in _current_value))
        )
        _tableWidget.setItem(
            i, 2, QTableWidgetItem(", ".join(str(e) for e in _requested_value))
        )

    _btn_ok = QPushButton(_warning)
    _btn_ok.setText("Ok")
    _btn_ok.clicked.connect(_warning.close)

    _warning.setLayout(
        lay_out_vertically(
            lay_out_horizontally(QLabel(text, _warning)),
            lay_out_horizontally(
                QLabel("Some configuration parameters could not be written:", _warning)
            ),
            lay_out_horizontally(_tableWidget),
            lay_out_horizontally(_btn_ok),
        )
    )

    _warning.show()

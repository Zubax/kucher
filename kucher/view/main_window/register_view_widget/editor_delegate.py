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

import math
from logging import getLogger
from PyQt5.QtWidgets import QStyledItemDelegate, QWidget, QStyleOptionViewItem, QSpinBox, QDoubleSpinBox, QLineEdit, \
    QComboBox
from PyQt5.QtCore import Qt, QModelIndex, QObject, QAbstractItemModel
from view.utils import get_monospace_font, show_error, get_icon
from view.device_model_representation import Register
from .model import Model, display_value, parse_value


_logger = getLogger(__name__)

# Number of steps between minimum and maximum values for real valued registers (unless entering the value directly)
_NUMBER_OF_STEPS_IN_FULL_RANGE = 1000

# Displayed precision depends on the type of the floating point number
_FLOATING_POINT_DECIMALS = {
    Register.ValueType.F32: 6,
    Register.ValueType.F64: 15,
}


class EditorDelegate(QStyledItemDelegate):
    """
    Factory and manager of editing widgets for use with the Register view table.
    """

    def __init__(self, parent: QObject):
        super(EditorDelegate, self).__init__(parent)

    def createEditor(self, parent: QWidget, option: QStyleOptionViewItem, index: QModelIndex) -> QWidget:
        register = self._get_register_from_index(index)
        _logger.info('Constructing editor for %r', register)

        if self._can_use_bool_switch(register):
            editor = QComboBox(parent)
            editor.setEditable(False)
            editor.addItem(get_icon('cancel'), 'False')
            editor.addItem(get_icon('ok'), 'True')
        elif self._can_use_spinbox(register):
            minimum, maximum = register.min_value[0], register.max_value[0]

            if register.type_id in _FLOATING_POINT_DECIMALS:
                raw_step = (maximum - minimum) / _NUMBER_OF_STEPS_IN_FULL_RANGE
                refined_step = 10 ** round(math.log10(raw_step))
                _logger.info('Constructing QDoubleSpinBox with single step set to %r', refined_step)
                editor = QDoubleSpinBox(parent)
                editor.setSingleStep(refined_step)
                editor.setDecimals(_FLOATING_POINT_DECIMALS[register.type_id])
            else:
                editor = QSpinBox(parent)

            editor.setMinimum(minimum)
            editor.setMaximum(maximum)
        else:
            editor = QLineEdit(parent)
            editor.setFont(get_monospace_font())

        return editor

    def setEditorData(self, editor: QWidget, index: QModelIndex):
        """Invoked in the beginning of the editing session; data transferred from the model to the editor"""
        register = self._get_register_from_index(index)

        if isinstance(editor, QComboBox):
            assert self._can_use_bool_switch(register)
            editor.setCurrentIndex(int(bool(register.cached_value[0])))
            _logger.info('Value %r has been represented as %r', register.cached_value, editor.currentText())
        elif isinstance(editor, (QDoubleSpinBox, QSpinBox)):
            assert self._can_use_spinbox(register)
            editor.setValue(register.cached_value[0])
        elif isinstance(editor, QLineEdit):
            assert not self._can_use_spinbox(register)
            editor.setText(display_value(register.cached_value, register.type_id))
        else:
            raise TypeError(f'Unexpected editor: {editor}')

    def setModelData(self, editor: QWidget, model: QAbstractItemModel, index: QModelIndex):
        """Invoked ad the end of the editing session; data transferred from the editor to the model"""
        register = self._get_register_from_index(index)

        if isinstance(editor, QComboBox):
            assert self._can_use_bool_switch(register)
            # >>> int('1')
            # 1
            # >>> bool(int(False))
            # False
            # >>> bool('False')
            # True
            # Wait what?!
            value = bool(editor.currentIndex())
            _logger.info('Value %r has been interpreted as %r', editor.currentText(), value)
        elif isinstance(editor, (QDoubleSpinBox, QSpinBox)):
            assert self._can_use_spinbox(register)
            editor.interpretText()                          # Beware!!1
            value = editor.value()
        elif isinstance(editor, QLineEdit):
            assert not self._can_use_spinbox(register)
            text = editor.text()
            try:
                value = parse_value(text, register.type_id)
            except Exception as ex:
                _logger.warning('The following value could not be parsed: %r', text, exc_info=True)
                show_error('Invalid value', 'Could not parse the entered value', str(ex), editor.window())
                value = None
        else:
            raise TypeError(f'Unexpected editor: {editor}')

        # We're not going to touch the device here; instead, we're going to delegate that back to the Model instance.
        if value is not None:
            model.setData(index, value, Qt.EditRole)

    def updateEditorGeometry(self, editor: QWidget, option: QStyleOptionViewItem, index: QModelIndex):
        """
        http://doc.qt.io/qt-5/model-view-programming.html#delegate-classes
        """
        # noinspection PyUnresolvedReferences
        editor.setGeometry(option.rect)

    @staticmethod
    def _get_register_from_index(index: QModelIndex) -> Register:
        register = Model.get_register_from_index(index)
        if register is None:
            raise ValueError(f'Logic error - the index {index} MUST contain a valid register reference')

        if register.type_id == Register.ValueType.EMPTY:
            raise ValueError("Did not expect an empty register here (who needs them anyway? doesn't make sense)")

        return register

    @staticmethod
    def _can_use_spinbox(register: Register) -> bool:
        return \
            register.kind == Register.ValueKind.ARRAY_OF_SCALARS and \
            len(register.cached_value) == 1 and \
            register.has_min_and_max_values

    @staticmethod
    def _can_use_bool_switch(register: Register) -> bool:
        # No need to check for min and max, they are evident for booleans
        return register.type_id == Register.ValueType.BOOLEAN and \
            len(register.cached_value) == 1

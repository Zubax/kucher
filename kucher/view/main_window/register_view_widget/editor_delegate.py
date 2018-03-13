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
from PyQt5.QtWidgets import QStyledItemDelegate, QWidget, QStyleOptionViewItem, QSpinBox, QDoubleSpinBox, \
    QPlainTextEdit, QComboBox
from PyQt5.QtCore import Qt, QModelIndex, QObject, QAbstractItemModel, QRect, QSize
from PyQt5.QtGui import QFontMetrics
from view.utils import get_monospace_font, show_error, get_icon
from view.device_model_representation import Register
from .model import Model
from .textual import display_value, parse_value, MAX_LINE_LENGTH


_logger = getLogger(__name__)

# Preferred minimal number of steps between minimum and maximum values for real valued registers when using arrows
_MIN_PREFERRED_NUMBER_OF_STEPS_IN_FULL_RANGE = 1000

# Displayed precision depends on the type of the floating point number
_FLOATING_POINT_DECIMALS = {
    Register.ValueType.F32: 7,
    Register.ValueType.F64: 16,
}


class EditorDelegate(QStyledItemDelegate):
    """
    Factory and manager of editing widgets for use with the Register view table.
    """

    def __init__(self, parent: QObject):
        super(EditorDelegate, self).__init__(parent)

    def createEditor(self, parent: QWidget, option: QStyleOptionViewItem, index: QModelIndex) -> QWidget:
        """
        The set of editors that we have defined here are only good for small-dimensioned registers with a few values.
        They are not good for unstructured data and large arrays. For that, shall the need arise, we'll need to define
        dedicated complex widgets. Luckily, it is very easy to do, just not really necessary at the moment.
        The framework doesn't care what kind of widget we're displaying when editing, it's just a basic pop-up that
        appears on top of the view.
        """
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
                step = (maximum - minimum) / _MIN_PREFERRED_NUMBER_OF_STEPS_IN_FULL_RANGE
                step = 10 ** round(math.log10(step))
                step = min(1.0, step)                       # Step can't be greater than one for UX reasons
                _logger.info('Constructing QDoubleSpinBox with single step set to %r', step)
                editor = QDoubleSpinBox(parent)
                editor.setSingleStep(step)
                editor.setDecimals(_FLOATING_POINT_DECIMALS[register.type_id])
            else:
                editor = QSpinBox(parent)

            editor.setMinimum(minimum)
            editor.setMaximum(maximum)
        else:
            editor = QPlainTextEdit(parent)
            editor.setFont(get_monospace_font())
            editor.setMinimumWidth(QFontMetrics(editor.font()).width('9' * (MAX_LINE_LENGTH + 10)))

        editor.setFont(Model.get_font())

        # noinspection PyBroadException
        try:
            parent.window().statusBar().showMessage('Press Esc to cancel editing', 5000)
        except Exception:
            _logger.exception('Could not display editing hint')

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
        elif isinstance(editor, QPlainTextEdit):
            assert not self._can_use_spinbox(register)
            editor.setPlainText(display_value(register.cached_value, register.type_id))
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
        elif isinstance(editor, QPlainTextEdit):
            assert not self._can_use_spinbox(register)
            text = editor.toPlainText()
            try:
                value = parse_value(text, register.type_id)
            except Exception as ex:
                _logger.warning('The following value could not be parsed: %r', text, exc_info=True)
                show_error('Invalid value', 'Could not parse the entered value', repr(ex), editor.window())
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
        # The field "rect" got rect. I'll show myself out.
        # Seriously though, it is missing in the PyQt5 bindings docs for some reason, so PyCharm generates a false
        # warning here, which we have to suppress.
        # noinspection PyUnresolvedReferences
        rect: QRect = option.rect

        # Now, this is tricky. The official Qt documentation tells us that we have to do simply this:
        # >>> editor.setGeometry(rect)
        # Some background: http://doc.qt.io/qt-5/model-view-programming.html#delegate-classes
        # But we don't want that, because our cells are extremely small (we need to conserve screen space),
        # and our editing controls don't fit well into small cells. I mean they do fit, but it looks terribly ugly,
        # and using them is a disappointing experience at its best.
        # So, we do NOT enforce size constraints on them. Check this out: if we were to ignore the geometry hint
        # from the framework, our widget would appear at the coordinates (0, 0), which happen to be at the
        # upper-left corner of the parent element. This looks even worse, but at least the widget's available
        # space is not constrained by its small parent cell. So the solution is to use the location data provided
        # by the framework, and disregard the size data, allowing the widget to resize itself in whichever way it
        # pleases. It would overlay the neighboring cells, but that is perfectly acceptable!
        if editor.minimumWidth() < rect.width():
            editor.setMinimumWidth(rect.width())

        if editor.minimumHeight() < rect.height():
            editor.setMinimumHeight(rect.height())

        # Determine the preferred size
        editor_size: QSize = editor.sizeHint()
        if not editor_size.isValid():
            editor_size = editor.size()

        assert editor_size.isValid()

        # Relocate the widget so that it is centered exactly on top of its containing cell,
        # possibly overflowing in all directions uniformly. Never offset the origin to the right or downwards,
        # because that may expose the overlaid value we're editing, which looks bad (hence the limiting).
        x_offset = max(0, editor_size.width() - rect.width()) // 2
        y_offset = max(0, editor_size.height() - rect.height()) // 2
        editor.move(rect.x() - x_offset,
                    rect.y() - y_offset)

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
        return \
            register.type_id == Register.ValueType.BOOLEAN and \
            len(register.cached_value) == 1

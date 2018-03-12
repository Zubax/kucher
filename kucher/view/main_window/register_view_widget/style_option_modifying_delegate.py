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

from PyQt5.QtWidgets import QStyledItemDelegate, QStyleOptionViewItem
from PyQt5.QtCore import Qt, QModelIndex, QObject, QAbstractItemModel, QRect, QSize
from PyQt5.QtGui import QPainter


class StyleOptionModifyingDelegate(QStyledItemDelegate):
    """
    Modifies the style option in a specified way before painting.
    http://doc.qt.io/qt-5/qstyleoptionviewitem.html
    """

    def __init__(self, parent: QObject, decoration_position: int):
        super(StyleOptionModifyingDelegate, self).__init__(parent)
        self._decoration_position = decoration_position

    def paint(self, painter: QPainter, option: QStyleOptionViewItem, index: QModelIndex):
        option.decorationPosition = self._decoration_position
        super(StyleOptionModifyingDelegate, self).paint(painter, option, index)

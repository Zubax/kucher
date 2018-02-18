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

from PyQt5.QtWidgets import QWidget, QLabel, QVBoxLayout
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QFont
from .base import StatusWidgetBase
from view.device_model_representation import GeneralStatusView


class PlaceholderWidget(StatusWidgetBase):
    # noinspection PyArgumentList
    def __init__(self, parent: QWidget):
        super(PlaceholderWidget, self).__init__(parent)

        label = QLabel(self)
        label.setText('Task-specific status information is not available')
        label.setWordWrap(True)
        label.setAlignment(Qt.AlignCenter)

        font: QFont = label.font()
        font.setItalic(True)
        label.setFont(font)

        layout = QVBoxLayout()
        layout.addWidget(label)
        self.setLayout(layout)

    def reset(self):
        pass

    def on_general_status_update(self, timestamp: float, s: GeneralStatusView):
        pass

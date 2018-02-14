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

import enum
import typing
from logging import getLogger
from contextlib import contextmanager
from PyQt5.QtWidgets import QWidget, QSlider, QDoubleSpinBox
from PyQt5.QtCore import Qt
from view.utils import gui_test
from utils import Event


_logger = getLogger(__name__)


class SpinboxLinkedWithSlider:
    """
    A simple class that contains a pair of linked QDoubleSpinBox and QSlider.
    The class does all of the tricky management inside in order to ensure that both widgets are perfectly in sync
    at all times. There is a number of complicated corner cases that one might stumble upon when making ad-hoc
    implementations of the same logic, so it makes sense to factor it out once into a well-tested class.

    Note that this is not a widget. The user will have to allocate the two linked widgets on their own.
    They are accessible via the respective properties. Note that the user must NEVER attempt to modify the
    values in the widgets manually, as that will break the class' own behavior.

    TODO: make it impossible for the users to modify the sensitive parameters of the contained widgets.
    """

    class SliderOrientation(enum.IntEnum):
        HORIZONTAL = Qt.Horizontal
        VERTICAL   = Qt.Vertical

    # noinspection PyUnresolvedReferences
    def __init__(self,
                 parent:                QWidget,
                 minimum:               float=0.0,
                 maximum:               float=100.0,
                 step:                  float=1.0,
                 slider_orientation:    SliderOrientation=SliderOrientation.VERTICAL):
        self._events_suppressed = False

        # Instantiating the widgets
        self._box = QDoubleSpinBox(parent)
        self._sld = QSlider(int(slider_orientation), parent)

        # This stuff breaks if I remove lambdas, no clue why, investigate later
        self._box.valueChanged[float].connect(lambda v: self._on_box_changed(v))
        self._sld.valueChanged.connect(lambda v: self._on_sld_changed(v))

        # Initializing the parameters
        self.set_range(minimum, maximum)
        self.step = step

        # Initializing the API
        self._value_change_event = Event()

    @property
    def value_change_event(self) -> Event:
        return self._value_change_event

    @property
    def spinbox(self) -> QDoubleSpinBox:
        return self._box

    @property
    def slider(self) -> QSlider:
        return self._sld

    @property
    def minimum(self) -> float:
        return self._box.minimum()

    @minimum.setter
    def minimum(self, value: float):
        self._box.setMinimum(value)

        with self._with_events_suppressed():
            self._sld.setMinimum(self._value_to_int(value))

        _logger.debug('New minimum: %r %r', value, self._value_to_int(value))

    @property
    def maximum(self) -> float:
        return self._box.maximum()

    @maximum.setter
    def maximum(self, value: float):
        self._box.setMaximum(value)

        with self._with_events_suppressed():
            self._sld.setMaximum(self._value_to_int(value))

        _logger.debug('New maximum: %r %r', value, self._value_to_int(value))

    @property
    def step(self) -> float:
        return self._box.singleStep()

    @step.setter
    def step(self, value: float):
        if not (value > 0):
            raise ValueError(f'Step must be positive, got {value!r}')

        self._box.setSingleStep(value)

        with self._with_events_suppressed():
            self._sld.setMinimum(self._value_to_int(self.minimum))
            self._sld.setMaximum(self._value_to_int(self.maximum))
            self._sld.setValue(self._value_to_int(self.value))

        _logger.debug('New step: %r; resulting range of the slider: [%r, %r]',
                      value, self._sld.minimum(), self._sld.maximum())

    @property
    def value(self) -> float:
        return self._box.value()

    @value.setter
    def value(self, value: float):
        self._box.setValue(value)

        with self._with_events_suppressed():
            self._sld.setValue(self._value_to_int(value))

    def set_range(self, minimum: float, maximum: float):
        self.minimum = minimum
        self.maximum = maximum

    def _on_box_changed(self, value: float):
        if self._events_suppressed:
            return

        with self._with_events_suppressed():
            self._sld.setValue(self._value_to_int(value))

        # The signal must be emitted in the last order, when the object's own state has been updated
        self._value_change_event.emit(value)

    def _on_sld_changed(self, scaled_int_value: int):
        if self._events_suppressed:
            return

        value = self._value_from_int(scaled_int_value)
        with self._with_events_suppressed():
            self._box.setValue(value)

        # The signal must be emitted in the last order, when the object's own state has been updated
        self._value_change_event.emit(value)

    def _value_to_int(self, value: float) -> int:
        return round(value / self._box.singleStep())

    def _value_from_int(self, value: int) -> int:
        return value * self._box.singleStep()

    # noinspection PyUnresolvedReferences
    @contextmanager
    def _with_events_suppressed(self):
        self._events_suppressed = True
        yield
        self._events_suppressed = False


# noinspection PyArgumentList
@gui_test
def _unittest_spinbox_linked_with_slider():
    import time
    from PyQt5.QtWidgets import QApplication, QMainWindow, QLayout
    from view.utils import lay_out_horizontally, lay_out_vertically

    app = QApplication([])

    instances: typing.List[SpinboxLinkedWithSlider] = []

    def make(minimum:   float,
             maximum:   float,
             step:      float) -> QLayout:
        o = SpinboxLinkedWithSlider(widget,
                                    minimum=minimum,
                                    maximum=maximum,
                                    step=step,
                                    slider_orientation=SpinboxLinkedWithSlider.SliderOrientation.HORIZONTAL)
        instances.append(o)
        return lay_out_horizontally((o.slider, 1), o.spinbox)

    win = QMainWindow()
    widget = QWidget(win)
    widget.setLayout(lay_out_vertically(make(0, 100, 1),
                                        make(-10, 10, 0.01),
                                        make(-99999, 100, 100)))
    win.setCentralWidget(widget)
    win.show()

    def run_a_bit():
        for _ in range(1000):
            time.sleep(0.005)
            app.processEvents()

    run_a_bit()
    instances[0].minimum = -1000
    instances[2].step = 10
    run_a_bit()

    win.close()

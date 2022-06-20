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

from kucher.view.utils import gui_test
from kucher.utils import Event


_logger = getLogger(__name__)


class SpinboxLinkedWithSlider:
    """
    A simple class that contains a pair of linked QDoubleSpinBox and QSlider.
    The class does all of the tricky management inside in order to ensure that both widgets are perfectly in sync
    at all times. There is a number of complicated corner cases that one might stumble upon when making ad-hoc
    implementations of the same logic, so it makes sense to factor it out once into a well-tested class.

    Note that this is not a widget. The user will have to allocate the two linked widgets on their own.
    They are accessible via the respective properties. Note that the user must NEVER attempt to modify the
    values in the widgets manually, as that will break the class' own behavior. This is why the widget accessor
    properties are annotated as the most generic widget type - QWidget.

    I wrote the comment below in a different piece of code trying to document the dangers of flawed synchronization
    between a spin box and a slider. Ultimately, that was why I decided to separate that logic out into a separate
    class. The comment is provided here verbatim for historical reasons:

        The on-changed signal MUST be disconnected, otherwise we may end up emitting erroneous setpoints
        while the values are being updated. Another problem with the signals is that they go through the slider,
        if it is enabled, which breaks the value configured in the spin box. This is how it's happening (I had
        to look into the Qt's sources in order to find this out):
              setRange() updates the limits. If the currently set value is outside of the limits, it is updated.
              Assuming that the old value doesn't fit the new limits, setRange() invokes setValue(), which, in turn,
              invokes the on-change event handler in this class. The on-change event handler then moves the slider,
              in order to keep it in sync with the value. If the value exceeds the range of the slider, the slider
              will silently clip it, and then set the clipped value back to the spinbox from its event handler.
              A catastrophe! We lost the proper value and ended up with a clipped one. This is how it happens, if
              we were to print() out the relevant values from handlers:
                  CONFIGURING RANGE AND VALUE...
                  SPINBOX CHANGED TO 678.52           <-- this is the correct value
                  SLIDER MOVED TO 100%                <-- doesn't fit into the slider's range, so it gets clipped
                  SPINBOX CHANGED TO 100.0            <-- the clipped value fed back (and sent to the device!)
                  RANGE AND VALUE CONFIGURED
        So we disconnect the signal before changing stuff, and then connect the signal back.
    """

    class SliderOrientation(enum.IntEnum):
        HORIZONTAL = Qt.Horizontal
        VERTICAL = Qt.Vertical

    # noinspection PyUnresolvedReferences
    def __init__(
        self,
        parent: QWidget,
        minimum: float = 0.0,
        maximum: float = 100.0,
        step: float = 1.0,
        slider_orientation: SliderOrientation = SliderOrientation.VERTICAL,
    ):
        self._events_suppression_depth = 0

        # Instantiating the widgets
        self._box = QDoubleSpinBox(parent)
        self._sld = QSlider(int(slider_orientation), parent)

        self._sld.setTickPosition(
            QSlider.TicksBothSides
        )  # Perhaps expose this via API later

        # This stuff breaks if I remove lambdas, no clue why, investigate later
        self._box.valueChanged[float].connect(lambda v: self._on_box_changed(v))
        self._sld.valueChanged.connect(lambda v: self._on_sld_changed(v))

        # Initializing the parameters
        with self._with_events_suppressed():
            self.set_range(minimum, maximum)
            self.step = step

        # Initializing the API
        self._value_change_event = Event()

    @property
    def value_change_event(self) -> Event:
        return self._value_change_event

    @property
    def spinbox(self) -> QWidget:
        """
        Annotated as QWidget in order to prevent direct access to the critical functionality of the widgets,
        as that may break the inner logic of the class. This property should only be used for layout purposes.
        """
        return self._box

    @property
    def slider(self) -> QWidget:
        """
        Annotated as QWidget in order to prevent direct access to the critical functionality of the widgets,
        as that may break the inner logic of the class. This property should only be used for layout purposes.
        """
        return self._sld

    @property
    def minimum(self) -> float:
        return self._box.minimum()

    @minimum.setter
    def minimum(self, value: float):
        self._box.setMinimum(value)

        with self._with_events_suppressed():
            self._sld.setMinimum(self._value_to_int(value))

        _logger.debug("New minimum: %r %r", value, self._value_to_int(value))

    @property
    def maximum(self) -> float:
        return self._box.maximum()

    @maximum.setter
    def maximum(self, value: float):
        self._box.setMaximum(value)

        with self._with_events_suppressed():
            self._sld.setMaximum(self._value_to_int(value))

        self._refresh_invariants()

        _logger.debug("New maximum: %r %r", value, self._value_to_int(value))

    @property
    def step(self) -> float:
        return self._box.singleStep()

    @step.setter
    def step(self, value: float):
        if not (value > 0):
            raise ValueError(f"Step must be positive, got {value!r}")

        self._box.setSingleStep(value)

        with self._with_events_suppressed():
            self._sld.setMinimum(self._value_to_int(self.minimum))
            self._sld.setMaximum(self._value_to_int(self.maximum))
            self._sld.setValue(self._value_to_int(self.value))

        self._refresh_invariants()

        _logger.debug(
            "New step: %r; resulting range of the slider: [%r, %r]",
            value,
            self._sld.minimum(),
            self._sld.maximum(),
        )

    @property
    def value(self) -> float:
        return self._box.value()

    @value.setter
    def value(self, value: float):
        self._box.setValue(value)

        with self._with_events_suppressed():
            self._sld.setValue(self._value_to_int(value))

    @property
    def num_decimals(self) -> int:
        return self._box.decimals()

    @num_decimals.setter
    def num_decimals(self, value: int):
        self._box.setDecimals(value)

    @property
    def tool_tip(self) -> str:
        return self._box.toolTip()

    @tool_tip.setter
    def tool_tip(self, value: str):
        self._box.setToolTip(value)
        self._sld.setToolTip(value)

    @property
    def status_tip(self) -> str:
        return self._box.statusTip()

    @status_tip.setter
    def status_tip(self, value: str):
        self._box.setStatusTip(value)
        self._sld.setStatusTip(value)

    @property
    def spinbox_suffix(self) -> str:
        return self._box.suffix()

    @spinbox_suffix.setter
    def spinbox_suffix(self, value: str):
        self._box.setSuffix(value)

    @property
    def slider_visible(self) -> bool:
        return self._sld.isVisible()

    @slider_visible.setter
    def slider_visible(self, value: bool):
        self._sld.setVisible(value)

    def set_range(self, minimum: float, maximum: float):
        if minimum >= maximum:
            raise ValueError(
                f"Minimum must be less than maximum: min={minimum} max={maximum}"
            )

        self.minimum = minimum
        self.maximum = maximum

    def update_atomically(
        self,
        minimum: typing.Optional[float] = None,
        maximum: typing.Optional[float] = None,
        step: typing.Optional[float] = None,
        value: typing.Optional[float] = None,
    ):
        """
        This function updates all of the parameters, and invokes the change event only once at the end, provided
        that the new value is different from the old value.
        Parameters that are set to None will be left as-is, unchanged.
        """
        if (minimum is not None) and (maximum is not None):
            if minimum >= maximum:
                raise ValueError(
                    f"Minimum must be less than maximum: min={minimum} max={maximum}"
                )

        original_value = self.value

        with self._with_events_suppressed():
            if minimum is not None:
                self.minimum = minimum

            if maximum is not None:
                self.maximum = maximum

            if step is not None:
                self.step = step

            if value is not None:
                self.value = value

        if original_value != self.value:
            self._value_change_event.emit(self.value)

    def _on_box_changed(self, value: float):
        if self._events_suppression_depth > 0:
            return

        with self._with_events_suppressed():
            self._sld.setValue(self._value_to_int(value))

        # The signal must be emitted in the last order, when the object's own state has been updated
        self._value_change_event.emit(value)

    def _on_sld_changed(self, scaled_int_value: int):
        if self._events_suppression_depth > 0:
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

    def _refresh_invariants(self):
        assert self._events_suppression_depth >= 0
        self._sld.setTickInterval((self._sld.maximum() - self._sld.minimum()) // 2)

    # noinspection PyUnresolvedReferences
    @contextmanager
    def _with_events_suppressed(self):
        assert self._events_suppression_depth >= 0
        self._events_suppression_depth += 1
        yield
        self._events_suppression_depth -= 1
        assert self._events_suppression_depth >= 0


# noinspection PyArgumentList
@gui_test
def _unittest_spinbox_linked_with_slider():
    import time
    from PyQt5.QtWidgets import QApplication, QMainWindow, QLayout
    from kucher.view.utils import lay_out_horizontally, lay_out_vertically

    app = QApplication([])

    instances: typing.List[SpinboxLinkedWithSlider] = []

    def make(minimum: float, maximum: float, step: float) -> QLayout:
        o = SpinboxLinkedWithSlider(
            widget,
            minimum=minimum,
            maximum=maximum,
            step=step,
            slider_orientation=SpinboxLinkedWithSlider.SliderOrientation.HORIZONTAL,
        )
        instances.append(o)
        return lay_out_horizontally((o.slider, 1), o.spinbox)

    win = QMainWindow()
    widget = QWidget(win)
    widget.setLayout(
        lay_out_vertically(make(0, 100, 1), make(-10, 10, 0.01), make(-99999, 100, 100))
    )
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

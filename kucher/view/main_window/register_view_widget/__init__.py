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
import asyncio
import itertools
from logging import getLogger
from PyQt5.QtCore import Qt, QModelIndex
from PyQt5.QtGui import QKeySequence
from PyQt5.QtWidgets import QWidget, QTreeView, QHeaderView, QStyleOptionViewItem, QComboBox, QAbstractItemView, \
    QLabel, QShortcut
from view.widgets import WidgetBase
from view.utils import gui_test, make_button, lay_out_vertically, lay_out_horizontally, show_error
from view.device_model_representation import Register
from .model import Model
from .style_option_modifying_delegate import StyleOptionModifyingDelegate
from .editor_delegate import EditorDelegate


READ_SELECTED_SHORTCUT = 'Ctrl+R'      # Like Reload


_logger = getLogger(__name__)


class RegisterViewWidget(WidgetBase):
    def __init__(self, parent: QWidget):
        super(RegisterViewWidget, self).__init__(parent)

        self._registers = []
        self._running_task: asyncio.Task = None

        self._visibility_selector = QComboBox(self)
        self._visibility_selector.addItem('Show all registers', lambda _: True)
        self._visibility_selector.addItem('Only configuration parameters', lambda r: r.mutable and r.persistent)

        # noinspection PyUnresolvedReferences
        self._visibility_selector.currentIndexChanged.connect(lambda _: self._on_visibility_changed())

        self._reset_selected_button = make_button(self, 'Reset selected',
                                                  icon_name='clear-symbol',
                                                  tool_tip='Reset the currently selected registers to their default '
                                                           'values. The restored values will be committed '
                                                           'immediately. This function is available only if a '
                                                           'default value is defined.',
                                                  on_clicked=self._do_reset_selected)

        self._read_selected_button = make_button(self, 'Read selected',
                                                 icon_name='process',
                                                 tool_tip=f'Read the currently selected registers only '
                                                          f'[{READ_SELECTED_SHORTCUT}]',
                                                 on_clicked=self._do_read_selected)

        self._read_all_button = make_button(self, 'Read all',
                                            icon_name='process-plus',
                                            tool_tip='Read all registers from the device',
                                            on_clicked=self._do_read_all)

        self._expand_all_button = make_button(self, '',
                                              icon_name='expand-arrow',
                                              tool_tip='Expand all namespaces',
                                              on_clicked=lambda: self._tree.expandAll())

        self._collapse_all_button = make_button(self, '',
                                                icon_name='collapse-arrow',
                                                tool_tip='Collapse all namespaces',
                                                on_clicked=lambda: self._tree.collapseAll())

        self._read_selected_shortcut = QShortcut(QKeySequence(READ_SELECTED_SHORTCUT), self)
        self._read_selected_shortcut.setAutoRepeat(False)
        # noinspection PyUnresolvedReferences
        self._read_selected_shortcut.activated.connect(self._do_read_selected)

        self._status_display = QLabel(self)
        self._status_display.setWordWrap(True)
        self._status_display.setText(f'Press {READ_SELECTED_SHORTCUT} to read selected registers')

        self._reset_selected_button.setEnabled(False)
        self._read_selected_button.setEnabled(False)
        self._read_all_button.setEnabled(False)

        self._tree = QTreeView(self)
        self._tree.setItemDelegate(EditorDelegate(self._tree, self._display_status))
        self._tree.setVerticalScrollMode(QTreeView.ScrollPerPixel)
        self._tree.setHorizontalScrollMode(QTreeView.ScrollPerPixel)
        self._tree.setAnimated(True)
        self._tree.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self._tree.setAlternatingRowColors(True)

        # Register state icons should be shown on the right; on the left it looks quite ugly
        self._tree.setItemDelegateForColumn(
            int(Model.ColumnIndices.NAME),
            StyleOptionModifyingDelegate(self._tree,
                                         decoration_position=QStyleOptionViewItem.Right))

        # It doesn't seem to be explicitly documented, but it seems to be necessary to select either top or bottom
        # decoration position in order to be able to use center alignment. Left or right positions do not work here.
        self._tree.setItemDelegateForColumn(
            int(Model.ColumnIndices.FLAGS),
            StyleOptionModifyingDelegate(self._tree,
                                         decoration_position=QStyleOptionViewItem.Top,  # Important
                                         decoration_alignment=Qt.AlignCenter))

        header: QHeaderView = self._tree.header()
        header.setSectionResizeMode(QHeaderView.ResizeToContents)
        header.setStretchLastSection(False)  # Horizontal scroll bar doesn't work if this is enabled

        self.setLayout(
            lay_out_vertically(
                (self._tree, 1),
                lay_out_horizontally(
                    self._read_all_button,
                    self._read_selected_button,
                    self._reset_selected_button,
                    (None, 1),
                ),
                lay_out_horizontally(
                    self._visibility_selector,
                    (None, 1),
                    self._expand_all_button,
                    self._collapse_all_button,
                ),
                self._status_display
            )
        )

    def reset(self):
        self.setup([])

    def setup(self, registers: typing.Iterable[Register]):
        self._registers = list(registers)
        self._on_visibility_changed()

    def _replace_model(self, register_visibility_predicate: typing.Callable[[Register], bool]):
        # Cancel all operations that might be pending on the old model
        self._cancel_task()

        old_model = self._tree.model()

        # Configure the new model
        filtered_registers = list(filter(register_visibility_predicate, self._registers))
        # It is important to set the Tree widget as the parent in order to let the widget take ownership
        new_model = Model(self._tree, filtered_registers)
        _logger.info('New model %r', new_model)
        self._tree.setModel(new_model)

        # The selection model is implicitly replaced when we replace the model, so it has to be reconfigured
        self._tree.selectionModel().selectionChanged.connect(lambda *_: self._on_selection_changed())

        # TODO: Something fishy is going on. Something keeps the old model alive when we're replacing it.
        #       We could call deleteLater() on it, but it seems dangerous, because if that something ever decided
        #       to refer to that dead model later for any reason, we'll get a rougue dangling pointer access on
        #       our hands. The horror!
        if old_model is not None:
            import gc
            model_referrers = gc.get_referrers(old_model)
            if len(model_referrers) > 1:
                _logger.warning('Extra references to the old model %r: %r', old_model, model_referrers)

        # Update the widget - all root items are expanded by default
        for row in itertools.count():
            index = self._tree.model().index(row, 0)
            if not index.isValid():
                break

            self._tree.expand(index)

        self._reset_selected_button.setEnabled(False)
        self._read_selected_button.setEnabled(False)
        self._read_all_button.setEnabled(len(filtered_registers) > 0)

        self._display_status(f'{len(filtered_registers)} registers loaded')

    def _on_visibility_changed(self):
        self._replace_model(self._visibility_selector.currentData())

    def _on_selection_changed(self):
        selected = self._get_selected_registers()

        self._reset_selected_button.setEnabled(any(map(lambda r: r.has_default_value, selected)))
        self._read_selected_button.setEnabled(len(selected) > 0)

    def _do_read_selected(self):
        selected = self._get_selected_registers()
        if selected:
            self._read_specific(selected)
        else:
            self._display_status('No registers are selected, nothing to read')

    def _do_reset_selected(self):
        rv = {}
        for r in self._get_selected_registers():
            if r.has_default_value:
                rv[r] = r.default_value

        self._write_specific(rv)

    def _do_read_all(self):
        self._read_specific(self._tree.model().registers)

    def _read_specific(self, registers: typing.List[Register]):
        total_registers_read = None

        def progress_callback(register: Register, current_register_index: int, total_registers: int):
            nonlocal total_registers_read
            total_registers_read = total_registers
            self._display_status(f'Reading {register.name!r} '
                                 f'({current_register_index + 1} of {total_registers})')

        async def executor():
            try:
                _logger.info('Reading registers: %r', [r.name for r in registers])
                mod: Model = self._tree.model()
                await mod.read(registers=registers,
                               progress_callback=progress_callback)
            except asyncio.CancelledError:
                self._display_status(f'Read has been cancelled')
                raise
            except Exception as ex:
                _logger.exception('Register read failed')
                show_error('Read failed', 'Could not read registers', repr(ex), self)
                self._display_status(f'Could not read registers: {ex!r}')
            else:
                self._display_status(f'{total_registers_read} registers have been read')

        self._cancel_task()
        self._running_task = asyncio.get_event_loop().create_task(executor())

    def _write_specific(self, register_value_mapping: typing.Dict[Register, typing.Any]):
        total_registers_assigned = None

        def progress_callback(register: Register, current_register_index: int, total_registers: int):
            nonlocal total_registers_assigned
            total_registers_assigned = total_registers
            self._display_status(f'Writing {register.name!r} '
                                 f'({current_register_index + 1} of {total_registers})')

        async def executor():
            try:
                _logger.info('Writing registers: %r', [r.name for r in register_value_mapping.keys()])
                mod: Model = self._tree.model()
                await mod.write(register_value_mapping=register_value_mapping,
                                progress_callback=progress_callback)
            except asyncio.CancelledError:
                self._display_status(f'Write has been cancelled')
                raise
            except Exception as ex:
                _logger.exception('Register write failed')
                show_error('Write failed', 'Could not read registers', repr(ex), self)
                self._display_status(f'Could not write registers: {ex!r}')
            else:
                self._display_status(f'{total_registers_assigned} registers have been written')

        self._cancel_task()
        self._running_task = asyncio.get_event_loop().create_task(executor())

    def _get_selected_registers(self) -> typing.List[Register]:
        selected_indexes: typing.List[QModelIndex] = self._tree.selectedIndexes()
        selected_registers = set()
        for si in selected_indexes:
            r = Model.get_register_from_index(si)
            if r is not None:
                selected_registers.add(r)
        # Beware that sets are not sorted, this may lead to weird user experience when watching the registers
        # read in a funny order.
        return list(sorted(selected_registers, key=lambda r: r.name))

    def _cancel_task(self):
        # noinspection PyBroadException
        try:
            self._running_task.cancel()
        except Exception:
            pass
        else:
            _logger.info('A running task had to be cancelled: %r', self._running_task)
        finally:
            self._running_task = None

    def _display_status(self, text=None):
        self._status_display.setText(text)


# noinspection PyArgumentList
@gui_test
def _unittest_register_tree_widget():
    from PyQt5.QtWidgets import QApplication, QMainWindow
    from ._mock_registers import get_mock_registers
    from .editor_delegate import EditorDelegate

    app = QApplication([])
    win = QMainWindow()

    tw = RegisterViewWidget(win)
    tw.setup(get_mock_registers())

    win.setCentralWidget(tw)
    win.show()

    good_night_sweet_prince = False

    async def run_events():
        while not good_night_sweet_prince:
            app.processEvents()
            await asyncio.sleep(0.01)

    async def walk():
        nonlocal good_night_sweet_prince
        await asyncio.sleep(3600)
        good_night_sweet_prince = True

    asyncio.get_event_loop().run_until_complete(asyncio.gather(
        run_events(),
        walk()
    ))

    win.close()

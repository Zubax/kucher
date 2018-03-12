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
from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import QWidget, QTreeView, QHeaderView, QStyleOptionViewItem, QComboBox
from view.widgets import WidgetBase
from view.utils import gui_test, make_button, lay_out_vertically, lay_out_horizontally, show_error
from view.device_model_representation import Register
from .model import Model
from .style_option_modifying_delegate import StyleOptionModifyingDelegate
from .editor_delegate import EditorDelegate


_logger = getLogger(__name__)


class RegisterViewWidget(WidgetBase):
    def __init__(self, parent: QWidget):
        super(RegisterViewWidget, self).__init__(parent)

        self._registers = []
        self._reload_all_task: asyncio.Task = None

        self._visibility_selector = QComboBox(self)
        self._visibility_selector.addItem('All registers', lambda _: True)
        self._visibility_selector.addItem('Only configuration parameters', lambda r: r.mutable and r.persistent)

        # noinspection PyUnresolvedReferences
        self._visibility_selector.currentIndexChanged.connect(lambda _: self._on_visibility_changed())

        self._reload_all_button = make_button(self, 'Fetch all',
                                              icon_name='process',
                                              tool_tip='Reload all registers from the device',
                                              on_clicked=self._do_reload_all)

        self._tree = QTreeView(self)
        self._tree.setItemDelegate(EditorDelegate(self._tree))
        self._tree.setVerticalScrollMode(QTreeView.ScrollPerPixel)
        self._tree.setHorizontalScrollMode(QTreeView.ScrollPerPixel)
        self._tree.setAnimated(True)

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
                lay_out_horizontally(
                    self._reload_all_button,
                    (None, 1),
                    self._visibility_selector,
                ),
                (self._tree, 1)
            )
        )

    def reset(self):
        self._replace_model(lambda _: False)

    def set_registers(self, registers: typing.Iterable[Register]):
        self._registers = list(registers)
        self._on_visibility_changed()

    def _replace_model(self, register_visibility_predicate: typing.Callable[[Register], bool]):
        # Cancel all operations that might be pending on the old model
        # noinspection PyBroadException
        try:
            self._reload_all_task.cancel()
        except Exception:
            pass
        else:
            _logger.info('Reload-all task has been cancelled because the model is being replaced')
        finally:
            self._reload_all_task = None

        old_model = self._tree.model()

        # Configure the new model
        filtered_registers = filter(register_visibility_predicate, self._registers)
        # It is important to set the Tree widget as the parent in order to let the widget take ownership
        new_model = Model(self._tree, filtered_registers)
        _logger.info('New model %r', new_model)
        self._tree.setModel(new_model)

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

    def _on_visibility_changed(self):
        self._replace_model(self._visibility_selector.currentData())

    def _do_reload_all(self):
        def progress_callback(register: Register, current_register_index: int, total_registers: int):
            self.flash(f'Reading register {register.name!r} ({current_register_index + 1} of {total_registers})',
                       duration=3)

        async def executor():
            try:
                mod: Model = self._tree.model()
                await mod.reload_all(progress_callback)
            except asyncio.CancelledError:
                self.flash(f'Register reload has been cancelled', duration=60)
                raise
            except Exception as ex:
                _logger.exception('Register reload failed')
                show_error('Reload failed', 'Could not reload registers', repr(ex), self)
                self.flash(f'Could not reload registers: {ex!r}')
            else:
                self.flash(f'Registers have been reloaded', duration=10)
            finally:
                self._reload_all_task = None

        self._reload_all_task = asyncio.get_event_loop().create_task(executor())


# noinspection PyArgumentList
@gui_test
def _unittest_register_tree_widget():
    from PyQt5.QtWidgets import QApplication, QMainWindow
    from ._mock_registers import get_mock_registers
    from .editor_delegate import EditorDelegate

    app = QApplication([])
    win = QMainWindow()

    tw = RegisterViewWidget(win)
    tw.set_registers(get_mock_registers())

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

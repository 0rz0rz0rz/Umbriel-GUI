import os
import tempfile
import unittest
from unittest.mock import patch

import tomlkit
from PySide6.QtCore import QPoint, QSize, Qt
from PySide6.QtGui import QPalette
from PySide6.QtTest import QTest
from PySide6.QtWidgets import (
    QApplication, QInputDialog, QMessageBox, QPushButton, QScrollArea, QStyle,
    QStyleOptionViewItem, QTreeView,
)

from umbriel_config_gui import actions, keybinds, state
from umbriel_config_gui.common import apply_interaction_styles, contrast_ratio
from umbriel_config_gui.keybind_ui import KeybindEditor, short_action_description
from umbriel_config_gui.settings_layout import CollapsibleGroup


class KeybindUiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.tempdir = tempfile.TemporaryDirectory()
        self.addCleanup(self.tempdir.cleanup)
        path_patch = patch.object(state, "PATH", os.path.join(self.tempdir.name, "config.toml"))
        path_patch.start()
        self.addCleanup(path_patch.stop)
        dir_patch = patch.object(keybinds, "config_gui_data_dir", return_value=self.tempdir.name)
        dir_patch.start()
        self.addCleanup(dir_patch.stop)
        self.doc = tomlkit.parse(
            '[keybinds]\n'
            '"Mod+A" = { action = "spawn foo", repeat = true, custom = "keep" }\n'
            '"Mod+B" = "window-close"\n'
        )
        self.editor = KeybindEditor(self.doc)
        self.addCleanup(self.editor.close)
        self.editor.show()
        self.app.processEvents()

    def item_for_row(self, row):
        tree = self.editor.bind_list
        for index in range(tree.topLevelItemCount()):
            group = tree.topLevelItem(index)
            for child_index in range(group.childCount()):
                item = group.child(child_index)
                if item.data(0, Qt.ItemDataRole.UserRole) == row:
                    return item
        self.fail(f"No keybind item for row {row}")

    def test_edit_selected_binding_preserves_unknown_options(self):
        self.assertEqual(self.editor.key_edit.text(), "Mod+A")
        self.editor.action_edit.setEditText("spawn bar")
        self.editor.submap_edit.setText("resize")
        self.editor.validate()
        self.editor.commit()
        self.assertEqual(self.doc["keybinds"]["Mod+A"]["action"], "spawn bar")
        self.assertEqual(self.doc["keybinds"]["Mod+A"]["custom"], "keep")
        self.assertTrue(self.doc["keybinds"]["Mod+A"]["repeat"])
        self.assertEqual(self.doc["keybinds"]["Mod+A"]["submap"], "resize")

    def test_selection_lock_and_bulk_unlock(self):
        self.editor.lock_edit.setChecked(True)
        self.assertFalse(self.editor.action_edit.isEnabled())
        self.assertIn("Mod+A", self.editor.locked)
        self.app.processEvents()
        self.assertNotIn("[Locked]", self.item_for_row(0).text(0))
        self.assertFalse(self.item_for_row(0).icon(0).isNull())
        self.assertEqual(self.item_for_row(0).data(0, Qt.ItemDataRole.AccessibleDescriptionRole),
                         "Locked")
        self.assertFalse(self.item_for_row(1).icon(0).isNull())
        self.assertEqual(self.item_for_row(1).data(0, Qt.ItemDataRole.AccessibleDescriptionRole),
                         "Unlocked")
        self.assertTrue(self.editor.lock_edit.isChecked())
        self.editor.bind_list.setCurrentItem(self.item_for_row(1))
        self.assertEqual(self.editor.key_edit.text(), "Mod+B")
        self.editor.toggle_all_locks()
        self.assertFalse(self.editor.action_edit.isEnabled())
        self.editor.toggle_all_locks()
        self.assertTrue(self.editor.action_edit.isEnabled())
        self.assertFalse(self.editor.locked)
        image = self.item_for_row(0).icon(0).pixmap(QSize(16, 16)).toImage()
        self.assertTrue(all(image.pixelColor(x, y).alpha() == 0
                            for x in range(image.width()) for y in range(image.height())))

    def test_locked_and_unlocked_text_align(self):
        self.editor.t.item(1, 0).setText("Mod+A")
        self.editor.t.cellWidget(1, 2).setEditText("spawn foo")
        self.editor.lock_edit.setChecked(True)
        self.app.processEvents()
        view = self.editor.group_cards[""].findChild(QTreeView)
        text_positions = []
        for row in (0, 1):
            index = view.model().index(row, 0, view.rootIndex())
            option = QStyleOptionViewItem()
            option.initFrom(view)
            option.rect = view.visualRect(index)
            option.decorationSize = QSize(16, 16)
            view.itemDelegateForIndex(index).initStyleOption(option, index)
            text_positions.append(view.style().subElementRect(
                QStyle.SubElement.SE_ItemViewItemText, option, view).left())
        self.assertEqual(text_positions[0], text_positions[1])

    def test_add_duplicate_move_and_remove(self):
        self.editor.add_new_row()
        self.editor.key_edit.setText("Mod+C")
        self.editor.action_edit.setEditText("window-close")
        with patch.object(QInputDialog, "getText", return_value=("Mod+D", True)):
            self.editor.duplicate_selected()
        self.assertEqual(self.editor.key_edit.text(), "Mod+D")
        self.editor.move_selected(-1)
        self.assertEqual(list(self.editor.rows()), ["Mod+A", "Mod+B", "Mod+D", "Mod+C"])
        self.editor.remove()
        self.assertNotIn("Mod+D", self.editor.rows())
        self.editor.validate()
        self.editor.commit()
        self.assertIn("Mod+C", self.doc["keybinds"])
        self.assertNotIn("Mod+D", self.doc["keybinds"])

    def test_search_and_group_filter_do_not_change_bindings(self):
        self.editor.search.setText("window-close")
        self.assertTrue(self.item_for_row(0).isHidden())
        self.assertFalse(self.item_for_row(1).isHidden())
        self.editor.search.clear()
        self.editor.bind_list.setCurrentItem(self.item_for_row(0))
        with patch.object(QInputDialog, "getText", return_value=("Navigation", True)):
            self.editor.create_group()
        self.editor.group_edit.setCurrentText("Navigation")
        self.editor.group_filter.setCurrentText("All groups")
        self.editor.commit()
        self.assertEqual(self.editor.group_assignments["Mod+A"], "Navigation")
        self.assertEqual(len(self.editor.rows()), 2)

    def test_duplicate_shortcut_is_rejected(self):
        with (
            patch.object(QInputDialog, "getText", return_value=("Mod+B", True)),
            patch.object(QMessageBox, "warning") as warning,
        ):
            self.editor.duplicate_selected()
        warning.assert_called_once()
        self.assertEqual(self.editor.t.rowCount(), 2)

    def test_remove_multiple_selected_skips_locked_bindings(self):
        self.editor.lock_edit.setChecked(True)
        self.item_for_row(1).setSelected(True)
        self.editor.remove()
        self.assertIn("Mod+A", self.editor.rows())
        self.assertNotIn("Mod+B", self.editor.rows())

    def test_move_does_not_select_passed_positions(self):
        self.editor.add_new_row()
        self.editor.key_edit.setText("Mod+C")
        self.editor.action_edit.setEditText("window-close")
        for offset in (-1, -1, 1, 1):
            self.editor.move_selected(offset)
            self.app.processEvents()
            selected = self.editor.bind_list.selectedItems()
            self.assertEqual(len(selected), 1)
            self.assertIn("Mod+C", selected[0].text(0))
        self.editor.remove()
        self.assertEqual(set(self.editor.rows()), {"Mod+A", "Mod+B"})

    def test_lock_all_button_keeps_width_for_both_labels(self):
        button = self.editor.lock_all_btn
        self.app.processEvents()
        original = button.width()
        self.editor.toggle_all_locks()
        self.app.processEvents()
        self.assertEqual(button.width(), original)
        self.assertGreaterEqual(
            button.width(), button.fontMetrics().horizontalAdvance("Unlock all") + 20
        )
        self.editor.toggle_all_locks()
        self.app.processEvents()
        self.assertEqual(button.width(), original)

    def test_lock_button_keeps_size_hint_while_hovered(self):
        stylesheet = self.app.styleSheet()
        self.addCleanup(self.app.setStyleSheet, stylesheet)
        apply_interaction_styles(self.app)
        self.editor.resize(1000, 700)
        self.app.processEvents()
        button = self.editor.lock_all_btn
        QTest.mouseMove(self.editor.search, QPoint(5, 5))
        self.app.processEvents()
        unhovered_hint = button.sizeHint()
        QTest.mouseMove(button, button.rect().center())
        self.app.processEvents()
        self.assertEqual(button.sizeHint(), unhovered_hint)
        self.editor.toggle_all_locks()
        self.app.processEvents()
        unlock_hint = button.sizeHint()
        QTest.mouseMove(self.editor.search, QPoint(5, 5))
        self.app.processEvents()
        self.assertEqual(button.sizeHint(), unlock_hint)

    def test_lock_button_fills_action_row_when_theme_has_smaller_button_hint(self):
        stylesheet = self.app.styleSheet()
        self.addCleanup(self.app.setStyleSheet, stylesheet)
        self.app.setStyleSheet("QPushButton { padding: 10px; }")
        button = self.editor.lock_all_btn
        button.setStyleSheet("QPushButton { padding: 0px; }")
        self.editor.resize(1000, 700)
        self.app.processEvents()
        add_button = next(
            item for item in self.editor.findChildren(QPushButton) if item.text() == "Add"
        )
        self.assertEqual(button.height(), add_button.height())
        QTest.mouseClick(button, Qt.MouseButton.LeftButton)
        self.app.processEvents()
        self.assertEqual(button.height(), add_button.height())

    def test_group_collapse_search_and_short_descriptions(self):
        self.editor.action_edit.setEditText("window-close")
        self.editor.group_names = ["Windows", "Apps"]
        self.editor.refresh_group_controls()
        self.editor.group_edit.setCurrentText("Windows")
        self.editor.bind_list.setCurrentItem(self.item_for_row(1))
        self.editor.group_edit.setCurrentText("Apps")
        self.app.processEvents()
        tree = self.editor.bind_list
        groups = {tree.topLevelItem(i).text(0): tree.topLevelItem(i)
                  for i in range(tree.topLevelItemCount())}
        self.assertEqual(set(groups), {"Windows", "Apps"})
        child = groups["Windows"].child(0)
        self.assertIn("Mod+A", child.text(0))
        self.assertIn("Close", child.text(0))
        self.assertNotIn("window-close", child.text(0))
        self.assertEqual(child.toolTip(0), "window-close")
        groups["Windows"].setExpanded(False)
        self.editor.search.setText("window-close")
        self.assertTrue(tree.topLevelItem(0).isExpanded())
        self.editor.search.clear()
        groups = {tree.topLevelItem(i).text(0): tree.topLevelItem(i)
                  for i in range(tree.topLevelItemCount())}
        self.assertFalse(groups["Windows"].isExpanded())
        self.assertTrue(groups["Apps"].isExpanded())

    def test_default_split_is_even(self):
        self.editor.resize(1400, 800)
        self.app.processEvents()
        left, right = self.editor.splitter.sizes()
        self.assertLessEqual(abs(left - right), 2)
        splitter = self.editor.splitter
        self.assertGreaterEqual(
            splitter.widget(1).geometry().left() - splitter.widget(0).geometry().right() - 1,
            12,
        )
        self.assertEqual(splitter.handle(1).width(), 12)
        handle = splitter.handle(1)
        image = handle.grab().toImage()
        self.assertEqual(image.pixelColor(image.width() // 2, image.height() // 2),
                         splitter.palette().color(QPalette.ColorRole.Window))
        self.editor.splitter.moveSplitter(400, 1)
        self.editor.resize(1500, 800)
        self.app.processEvents()
        left, right = self.editor.splitter.sizes()
        self.assertLess(left, right - 100)

    def test_group_scrollbar_has_no_vertical_edge_line(self):
        stylesheet = self.app.styleSheet()
        self.addCleanup(self.app.setStyleSheet, stylesheet)
        apply_interaction_styles(self.app)
        self.editor.resize(900, 300)
        self.editor.group_names = ["One", "Two", "Three", "Four", "Five"]
        self.editor.refresh_group_controls()
        self.app.processEvents()
        scroll = self.editor.splitter.widget(0).findChild(QScrollArea)
        scrollbar = scroll.verticalScrollBar()
        self.assertTrue(scrollbar.isVisible())
        self.assertGreater(scrollbar.maximum(), 0)
        QTest.mouseMove(self.editor.search, QPoint(5, 5))
        self.app.processEvents()
        image = scrollbar.grab().toImage()
        background = scrollbar.palette().color(QPalette.ColorRole.Window)
        for y in range(image.height()):
            self.assertEqual(image.pixelColor(0, y), background)
            self.assertEqual(image.pixelColor(image.width() - 1, y), background)
        self.assertTrue(any(image.pixelColor(image.width() // 2, y) != background
                            for y in range(image.height())))
        thumb = scrollbar.palette().color(QPalette.ColorRole.Light)
        self.assertGreater(contrast_ratio(thumb, background), 1.4)
        self.assertTrue(any(image.pixelColor(image.width() // 2, y).name() == thumb.name()
                            for y in range(image.height())))
        scrollbar.setValue(scrollbar.maximum())
        self.assertEqual(scrollbar.value(), scrollbar.maximum())

    def test_shortcut_and_description_columns_align_across_groups(self):
        self.editor.resize(1400, 800)
        self.editor.group_names = ["Windows", "Apps"]
        self.editor.refresh_group_controls()
        self.editor.key_edit.setText("Mod+Shift+Control+Delete")
        self.editor.group_edit.setCurrentText("Windows")
        self.editor.bind_list.setCurrentItem(self.item_for_row(1))
        self.editor.group_edit.setCurrentText("Apps")
        self.app.processEvents()
        positions = []
        for group in ("Windows", "Apps"):
            view = self.editor.group_cards[group].findChild(QTreeView)
            view.setStyleSheet("QTreeView { background: #000000; color: #ffffff;"
                               " border: 0px; padding: 4px; }")
            index = view.model().index(0, 0, view.rootIndex())
            option = QStyleOptionViewItem()
            option.rect = view.visualRect(index)
            shortcut, description = view.itemDelegateForIndex(index).text_rects(option)
            positions.append((shortcut.left(), description.left()))
            self.assertGreater(description.width(), 0)
            view.clearSelection()
            self.app.processEvents()
            image = view.viewport().grab().toImage()
            self.assertTrue(any(
                image.pixelColor(x, y).lightness() > 150
                for x in range(description.left(), min(description.right() + 1, image.width()))
                for y in range(description.top(), min(description.bottom() + 1, image.height()))
            ))
            QTest.mouseClick(view.viewport(), Qt.MouseButton.LeftButton, pos=description.center())
            self.assertEqual(self.editor.t.currentRow(),
                             index.data(Qt.ItemDataRole.UserRole))
        self.assertEqual(positions[0], positions[1])

    def test_hidden_selection_cannot_be_removed(self):
        self.item_for_row(1).setSelected(True)
        self.editor.search.setText("window-close")
        self.assertEqual(len(self.editor.bind_list.selectedItems()), 1)
        self.editor.remove()
        self.assertEqual(list(self.editor.rows()), ["Mod+A"])
        self.editor.search.clear()
        self.editor.bind_list.setCurrentItem(self.item_for_row(0))
        self.item_for_row(0).parent().setExpanded(False)
        self.editor.remove()
        self.assertEqual(list(self.editor.rows()), ["Mod+A"])

    def test_custom_and_known_action_descriptions(self):
        self.assertEqual(short_action_description("spawn my-custom-app --verbose"),
                         "Run my-custom-app --verbose")
        self.assertIn("launcher", short_action_description(
            "spawn noctalia msg panel-toggle launcher").lower())
        self.assertEqual(short_action_description("unknown-action foo"), "unknown-action foo")
        for _, entries in actions.ACTION_CATEGORIES:
            for action, _ in entries:
                self.assertLessEqual(len(short_action_description(action)), 60)

    def test_group_filter_excludes_hidden_selected_rows(self):
        self.editor.group_names = ["Windows", "Apps"]
        self.editor.refresh_group_controls()
        self.editor.group_edit.setCurrentText("Windows")
        self.editor.bind_list.setCurrentItem(self.item_for_row(1))
        self.editor.group_edit.setCurrentText("Apps")
        self.app.processEvents()
        self.item_for_row(0).setSelected(True)
        self.editor.group_filter.setCurrentText("Windows")
        self.app.processEvents()
        self.assertTrue(self.item_for_row(1).isHidden())
        self.editor.remove()
        self.assertEqual(list(self.editor.rows()), ["Mod+B"])

    def test_interleaved_groups_preserve_backing_order_and_selection(self):
        self.editor.group_names = ["Windows", "Apps"]
        self.editor.refresh_group_controls()
        self.editor.group_edit.setCurrentText("Windows")
        self.editor.bind_list.setCurrentItem(self.item_for_row(1))
        self.editor.group_edit.setCurrentText("Apps")
        self.editor.add_new_row()
        self.editor.key_edit.setText("Mod+C")
        self.editor.action_edit.setEditText("window-close")
        self.editor.group_edit.setCurrentText("Windows")
        self.app.processEvents()
        self.assertEqual(list(self.editor.rows()), ["Mod+A", "Mod+B", "Mod+C"])
        self.editor.bind_list.setCurrentItem(self.item_for_row(2))
        self.editor.move_selected(-1)
        self.assertEqual(list(self.editor.rows()), ["Mod+A", "Mod+C", "Mod+B"])
        self.editor.validate()
        self.editor.commit()
        self.assertEqual(list(self.doc["keybinds"]), ["Mod+A", "Mod+C", "Mod+B"])
        self.editor.remove()
        self.assertEqual(list(self.editor.rows()), ["Mod+A", "Mod+B"])

    def test_group_cards_expand_and_resize_with_bindings(self):
        card = self.editor.group_cards[""]
        self.assertIsInstance(card, CollapsibleGroup)
        view = card.findChild(QTreeView)
        self.assertEqual(view.model(), self.editor.bind_list.model())
        self.assertEqual(view.selectionModel(), self.editor.bind_list.selectionModel())
        self.editor.resize(1100, 900)
        self.app.processEvents()
        expanded_height = card.height()
        QTest.mouseClick(card.header, Qt.MouseButton.LeftButton)
        self.app.processEvents()
        self.app.processEvents()
        self.assertFalse(card.header.isChecked())
        self.assertFalse(card.body.isVisible())
        self.assertLess(card.height(), expanded_height)
        QTest.keyClick(card.header, Qt.Key.Key_Space)
        self.app.processEvents()
        self.assertTrue(card.header.isChecked())
        self.assertTrue(card.body.isVisible())
        self.editor.add_new_row()
        self.app.processEvents()
        new_view = self.editor.group_cards[""].findChild(QTreeView)
        self.assertGreater(new_view.height(), view.height())

    def test_expanded_card_does_not_stretch_when_other_groups_collapse(self):
        self.editor.resize(1200, 900)
        self.editor.group_names = ["Windows", "Apps", "Media"]
        self.editor.refresh_group_controls()
        self.editor.group_edit.setCurrentText("Windows")
        self.editor.bind_list.setCurrentItem(self.item_for_row(1))
        self.editor.group_edit.setCurrentText("Apps")
        self.app.processEvents()
        card = self.editor.group_cards["Windows"]
        initial_height = card.height()
        expanded_scroll = self.editor.splitter.widget(0).findChild(QScrollArea)
        for group in ("Apps", "Media"):
            self.editor.group_cards[group].setExpanded(False)
        self.app.processEvents()
        self.assertEqual(card.height(), initial_height)
        self.assertLessEqual(card.height(), card.sizeHint().height() + 2)
        self.editor.resize(1200, 1100)
        self.app.processEvents()
        self.assertEqual(card.height(), initial_height)
        self.editor.resize(1200, 200)
        self.app.processEvents()
        self.assertGreater(expanded_scroll.verticalScrollBar().maximum(), 0)
        self.editor.resize(1200, 900)
        self.editor.group_cards["Apps"].setExpanded(True)
        self.app.processEvents()
        self.assertEqual(card.height(), initial_height)
        self.assertTrue(self.editor.group_cards["Apps"].body.isVisible())

    def test_group_list_background_has_rounded_corners(self):
        card = self.editor.group_cards[""]
        view = card.findChild(QTreeView)
        card.setStyleSheet(card.styleSheet().replace("palette(window)", "#eeeeee"))
        view.setStyleSheet(view.styleSheet().replace("palette(base)", "#111111"))
        self.editor.resize(1100, 900)
        self.app.processEvents()
        image = card.grab().toImage()
        position = view.mapTo(card, QPoint(0, 0))
        x, y = position.x(), position.y()
        width, height = view.width(), view.height()
        for dx, dy in ((0, 0), (width - 1, 0), (0, height - 1),
                       (width - 1, height - 1)):
            self.assertEqual(image.pixelColor(x + dx, y + dy).name(), "#eeeeee")
        for dx, dy in ((width // 2, 1), (width // 2, height - 2)):
            self.assertEqual(image.pixelColor(x + dx, y + dy).name(), "#111111")

    def test_cards_support_cross_group_selection(self):
        self.editor.group_names = ["Windows", "Apps", "Empty"]
        self.editor.refresh_group_controls()
        self.editor.group_edit.setCurrentText("Windows")
        self.editor.bind_list.setCurrentItem(self.item_for_row(1))
        self.editor.group_edit.setCurrentText("Apps")
        self.app.processEvents()
        self.assertIn("Empty", self.editor.group_cards)
        self.assertTrue(self.editor.group_cards["Empty"].isVisible())
        windows = self.editor.group_cards["Windows"].findChild(QTreeView)
        apps = self.editor.group_cards["Apps"].findChild(QTreeView)
        self.assertTrue(windows.isVisible())
        self.assertTrue(apps.isVisible())
        first = windows.model().index(0, 0, windows.rootIndex())
        second = apps.model().index(0, 0, apps.rootIndex())
        QTest.mouseClick(windows.viewport(), Qt.MouseButton.LeftButton,
                         pos=windows.visualRect(first).center())
        self.assertEqual(self.editor.key_edit.text(), "Mod+A")
        QTest.mouseClick(apps.viewport(), Qt.MouseButton.LeftButton,
                         Qt.KeyboardModifier.ControlModifier,
                         pos=apps.visualRect(second).center())
        self.assertEqual(self.editor.key_edit.text(), "Mod+B")
        self.assertEqual(len(self.editor.bind_list.selectedItems()), 2)
        self.editor.remove()
        self.assertEqual(list(self.editor.rows()), [])

    def test_add_opens_collapsed_group_and_clears_search(self):
        self.editor.group_cards[""].setExpanded(False)
        self.editor.search.setText("window-close")
        self.editor.add_new_row()
        self.app.processEvents()
        self.assertEqual(self.editor.search.text(), "")
        self.assertTrue(self.editor.group_cards[""].header.isChecked())
        self.assertTrue(self.editor.detail_card.isEnabled())
        self.editor.key_edit.setText("Mod+C")
        self.assertEqual(self.editor.t.item(2, 0).text(), "Mod+C")

    def test_group_creation_rename_and_deletion_update_cards(self):
        with patch.object(QInputDialog, "getText", return_value=("Apps", True)):
            self.editor.create_group()
        self.app.processEvents()
        self.assertTrue(self.editor.group_cards["Apps"].isVisible())
        self.editor.group_cards["Apps"].header.click()
        self.assertFalse(self.editor.group_cards["Apps"].header.isChecked())
        self.editor.add_new_row()
        self.assertTrue(self.editor.group_cards["Apps"].header.isChecked())
        self.editor.key_edit.setText("Mod+C")
        self.editor.action_edit.setEditText("window-close")
        with patch.object(QInputDialog, "getText", return_value=("Programs", True)):
            self.editor.rename_group()
        self.app.processEvents()
        self.assertNotIn("Apps", self.editor.group_cards)
        self.assertTrue(self.editor.group_cards["Programs"].isVisible())
        self.assertEqual(self.editor.t.cellWidget(2, 1).currentText(), "Programs")
        self.editor.t.cellWidget(2, 8).setChecked(True)
        with patch.object(QMessageBox, "question", return_value=QMessageBox.StandardButton.Yes):
            self.editor.delete_group()
        self.app.processEvents()
        self.assertNotIn("Programs", self.editor.group_cards)
        self.assertEqual(self.editor.t.cellWidget(2, 1).currentText(), "")
        self.assertIn("", self.editor.group_cards)
        self.assertEqual(self.item_for_row(2).parent().text(0), "Ungrouped")
        self.assertTrue(self.editor.t.cellWidget(2, 8).isChecked())
        self.editor.validate()
        self.editor.commit()
        self.assertEqual(self.doc["keybinds"]["Mod+C"], "window-close")
        self.assertNotIn("Mod+C", self.editor.group_assignments)


if __name__ == "__main__":
    unittest.main()

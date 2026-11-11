import os
import tempfile
import unittest
from unittest.mock import patch

from PySide6.QtGui import QPalette
from PySide6.QtWidgets import QApplication, QMessageBox, QPushButton, QScrollArea, QTableWidget

from umbriel_config_gui import desktop
from umbriel_config_gui.interaction_styles import apply_interaction_styles


class DefaultAppsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.tempdir = tempfile.TemporaryDirectory()
        self.addCleanup(self.tempdir.cleanup)
        self.path = os.path.join(self.tempdir.name, "mimeapps.list")
        path_patch = patch.object(desktop, "MIMEAPPS_PATH", self.path)
        path_patch.start()
        self.addCleanup(path_patch.stop)
        backup_patch = patch.object(
            desktop, "gui_backup_file", return_value=os.path.join(self.tempdir.name, "backup")
        )
        backup_patch.start()
        self.addCleanup(backup_patch.stop)
        apps_patch = patch.object(desktop, "installed_desktop_apps", return_value=[])
        apps_patch.start()
        self.addCleanup(apps_patch.stop)

    def make_page(self):
        page = desktop.DefaultApps()
        self.addCleanup(page.close)
        return page

    def test_scrollbar_has_no_vertical_edge(self):
        stylesheet = self.app.styleSheet()
        self.addCleanup(self.app.setStyleSheet, stylesheet)
        apply_interaction_styles(self.app)
        page = self.make_page()
        page.resize(750, 300)
        page.show()
        self.app.processEvents()
        bar = page.findChild(QScrollArea).verticalScrollBar()
        self.assertTrue(bar.isVisible())
        self.assertGreater(bar.maximum(), 0)
        image = bar.grab().toImage()
        background = bar.palette().color(QPalette.ColorRole.Window).name()
        self.assertTrue(all(image.pixelColor(0, y).name() == background
                            for y in range(image.height())))
        self.assertTrue(any(image.pixelColor(image.width() // 2, y).name() != background
                            for y in range(image.height())))
        bar.setValue(bar.maximum())
        self.assertEqual(bar.value(), bar.maximum())

    def test_role_cards_show_mime_types_and_save_custom_id(self):
        page = self.make_page()
        page.resize(650, 700)
        page.show()
        self.app.processEvents()
        self.assertFalse(page.findChildren(QTableWidget))
        self.assertEqual(len(page.role_selectors), len(desktop.DEFAULT_APP_ROLES))
        role, mimes = desktop.DEFAULT_APP_ROLES[0]
        page.role_selectors[role].setEditText("example.desktop")
        page.validate()
        page.commit()
        with open(self.path, encoding="utf-8") as file:
            defaults = desktop.parse_mimeapps_defaults(file.read().splitlines())
        for mime in mimes:
            self.assertEqual(defaults[mime], ["example.desktop"])

    def test_application_selectors_fit_typical_names_in_both_sections(self):
        app_id = "org.kde.dolphin.desktop"
        app_name = "Dolphin"
        with patch.object(desktop, "installed_desktop_apps", return_value=[(app_id, app_name)]):
            page = self.make_page()
        page._add_mime_row("application/example", app_id)
        page.mime_card.setExpanded(True)
        page.resize(900, 700)
        page.show()
        self.app.processEvents()
        role = page.role_selectors["File manager"]
        role.setCurrentIndex(role.findData(app_id))
        for selector in (role, page.mime_rows[0][2]):
            text_width = selector.fontMetrics().horizontalAdvance(selector.currentText())
            self.assertGreaterEqual(selector.width(), text_width + 30)

    def test_mixed_role_values_are_preserved_without_edits(self):
        original = "[Default Applications]\ntext/html=first.desktop;\napplication/xhtml+xml=second.desktop;\n"
        with open(self.path, "w", encoding="utf-8") as file:
            file.write(original)
        page = self.make_page()
        self.assertEqual(desktop.selected_app_id(page.role_selectors["Web browser"]), "<multiple>")
        page.validate()
        page.commit()
        with open(self.path, encoding="utf-8") as file:
            self.assertEqual(file.read(), original)
        self.assertFalse(page.changed)

    def test_file_type_search_edit_remove_and_refresh(self):
        with open(self.path, "w", encoding="utf-8") as file:
            file.write("[Default Applications]\napplication/json=old.desktop;\napplication/xml=xml.desktop;\n")
        page = self.make_page()
        page.mime_card.setExpanded(True)
        page.show()
        self.app.processEvents()
        page.mime_search.setText("json")
        self.assertTrue(page.mime_rows[0][0].isVisible())
        self.assertFalse(page.mime_rows[1][0].isVisible())
        selector = page.mime_rows[0][2]
        selector.setEditText("custom.desktop")
        page.refresh_apps()
        self.assertIs(page.mime_rows[0][2], selector)
        self.assertEqual(desktop.selected_app_id(selector), "custom.desktop")
        page._remove_mime_row(page.mime_rows[1][0])
        page.validate()
        page.commit()
        with open(self.path, encoding="utf-8") as file:
            defaults = desktop.parse_mimeapps_defaults(file.read().splitlines())
        self.assertEqual(defaults["application/json"], ["custom.desktop", "old.desktop"])
        self.assertNotIn("application/xml", defaults)

    def test_duplicate_mime_types_are_rejected_case_insensitively(self):
        page = self.make_page()
        page._add_mime_row("application/example", "one.desktop")
        page._add_mime_row("Application/Example", "two.desktop")
        with self.assertRaisesRegex(ValueError, "unique"):
            page.validate()

    def test_add_and_remove_file_type_using_controls(self):
        page = self.make_page()
        page.mime_card.setExpanded(True)
        with patch.object(desktop.QInputDialog, "getText", return_value=("application/example", True)):
            page.add_mime_type()
        row, mime_edit, selector = page.mime_rows[0]
        self.assertEqual(mime_edit.text(), "application/example")
        selector.setEditText("example.desktop")
        page.validate()
        page.commit()
        with open(self.path, encoding="utf-8") as file:
            defaults = desktop.parse_mimeapps_defaults(file.read().splitlines())
        self.assertEqual(defaults["application/example"], ["example.desktop"])
        remove_button = next(
            button for button in row.findChildren(QPushButton) if button.text() == "Remove"
        )
        remove_button.click()
        self.assertEqual(page.mime_rows, [])
        page.commit()
        with open(self.path, encoding="utf-8") as file:
            defaults = desktop.parse_mimeapps_defaults(file.read().splitlines())
        self.assertNotIn("application/example", defaults)

    def test_duplicate_add_is_rejected(self):
        page = self.make_page()
        page._add_mime_row("application/example", "example.desktop")
        with (
            patch.object(desktop.QInputDialog, "getText", return_value=("Application/Example", True)),
            patch.object(QMessageBox, "warning") as warning,
        ):
            page.add_mime_type()
        warning.assert_called_once()
        self.assertEqual(len(page.mime_rows), 1)


if __name__ == "__main__":
    unittest.main()

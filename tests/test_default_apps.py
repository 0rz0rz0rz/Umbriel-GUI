import os
import tempfile
import unittest
from unittest.mock import patch

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication, QAbstractItemView

from umbriel_config_gui import desktop


class DefaultAppsTableTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def test_role_mime_cells_align_and_scroll_only_when_needed(self):
        with tempfile.TemporaryDirectory() as directory:
            with patch.object(desktop, "MIMEAPPS_PATH", os.path.join(directory, "mimeapps.list")):
                with patch.object(desktop, "installed_desktop_apps", return_value=[]):
                    page = desktop.DefaultApps()
            self.addCleanup(page.close)
            page.resize(1800, 700)
            page.show()
            self.app.processEvents()

            table = page.roles
            self.assertFalse(table.horizontalScrollBar().isVisible())
            self.assertEqual(
                sum(table.columnWidth(column) for column in range(3)),
                table.viewport().width(),
            )
            self.assertEqual(
                table.horizontalScrollMode(), QAbstractItemView.ScrollMode.ScrollPerPixel
            )
            for row, (_, mimes) in enumerate(desktop.DEFAULT_APP_ROLES):
                item = table.item(row, 2)
                self.assertIsNone(table.cellWidget(row, 2))
                self.assertEqual(item.text(), ", ".join(mimes))
                self.assertEqual(item.toolTip(), item.text())
                self.assertFalse(item.flags() & Qt.ItemFlag.ItemIsEditable)
                self.assertEqual(table.visualItemRect(item).height(), table.rowHeight(row))

            page.resize(650, 700)
            self.app.processEvents()
            scrollbar = table.horizontalScrollBar()
            self.assertTrue(scrollbar.isVisible())
            self.assertGreater(scrollbar.maximum(), 0)
            self.assertLessEqual(scrollbar.height(), 8)
            scrollbar.setValue(scrollbar.maximum())
            self.assertGreater(scrollbar.value(), 0)
            page.resize(1800, 700)
            self.app.processEvents()
            self.assertFalse(scrollbar.isVisible())
            self.assertEqual(
                sum(table.columnWidth(column) for column in range(3)),
                table.viewport().width(),
            )

    def test_role_changes_still_update_its_mime_types(self):
        with tempfile.TemporaryDirectory() as directory:
            path = os.path.join(directory, "mimeapps.list")
            with patch.object(desktop, "MIMEAPPS_PATH", path):
                with patch.object(desktop, "installed_desktop_apps", return_value=[]):
                    page = desktop.DefaultApps()
                self.addCleanup(page.close)
                page.roles.cellWidget(0, 1).setEditText("example.desktop")
                page.validate()
                page.commit()
                with open(path, encoding="utf-8") as file:
                    defaults = desktop.parse_mimeapps_defaults(file.read().splitlines())
                for mime in desktop.DEFAULT_APP_ROLES[0][1]:
                    self.assertEqual(defaults[mime], ["example.desktop"])

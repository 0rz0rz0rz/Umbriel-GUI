import os
import tempfile
import unittest
from unittest.mock import patch

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QApplication,
    QDialog,
    QListWidget,
    QMainWindow,
    QMessageBox,
    QPushButton,
)

from umbriel_config_gui import state
from umbriel_config_gui.window import (
    Window,
    delete_backup_snapshots,
    list_backup_snapshots,
)


class BackupManagementTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.tempdir = tempfile.TemporaryDirectory()
        self.addCleanup(self.tempdir.cleanup)
        self.directory = os.path.join(self.tempdir.name, "backups")
        os.mkdir(self.directory)
        self.config_path = "/config/config.toml"

    def create_backup(self, name):
        path = os.path.join(self.directory, name)
        with open(path, "w", encoding="utf-8") as backup:
            backup.write("[general]\n")
        return path

    def test_lists_only_regular_backups_for_current_config_in_order(self):
        later = self.create_backup("config.toml.20260102.bak")
        earlier = self.create_backup("config.toml.20260101.bak")
        self.create_backup("other.toml.20260101.bak")
        os.mkdir(os.path.join(self.directory, "config.toml.20260103.bak"))

        self.assertEqual(
            list_backup_snapshots(self.directory, self.config_path),
            [earlier, later],
        )

    def test_deletes_only_marked_backups_and_rejects_outside_paths(self):
        marked = self.create_backup("config.toml.20260101.bak")
        unmarked = self.create_backup("config.toml.20260102.bak")
        outside = os.path.join(self.tempdir.name, "keep.txt")
        with open(outside, "w", encoding="utf-8") as file:
            file.write("keep")

        deleted, errors = delete_backup_snapshots(
            self.directory, self.config_path, [marked, outside]
        )

        self.assertEqual(deleted, [os.path.basename(marked)])
        self.assertTrue(os.path.exists(unmarked))
        self.assertTrue(os.path.exists(outside))
        self.assertEqual(len(errors), 1)
        self.assertIn("not a valid backup path", errors[0])

    def test_backup_window_deletes_only_checked_item(self):
        marked = self.create_backup("config.toml.20260102.bak")
        unmarked = self.create_backup("config.toml.20260101.bak")
        host = QMainWindow()
        self.addCleanup(host.close)

        def exec_dialog(dialog):
            backups = dialog.findChild(QListWidget)
            self.assertEqual(backups.count(), 2)
            self.assertEqual(backups.item(0).text(), os.path.basename(marked))
            select_all_button = next(
                button
                for button in dialog.findChildren(QPushButton)
                if button.text() == "Select all"
            )
            select_all_button.click()
            self.assertTrue(all(
                backups.item(index).checkState() == Qt.CheckState.Checked
                for index in range(backups.count())
            ))
            self.assertEqual(select_all_button.text(), "Deselect all")
            select_all_button.click()
            self.assertTrue(all(
                backups.item(index).checkState() == Qt.CheckState.Unchecked
                for index in range(backups.count())
            ))
            self.assertEqual(select_all_button.text(), "Select all")
            backups.item(0).setCheckState(Qt.CheckState.Checked)
            self.assertEqual(select_all_button.text(), "Select all")
            select_all_button.click()
            self.assertEqual(select_all_button.text(), "Deselect all")
            self.assertEqual(backups.item(1).checkState(), Qt.CheckState.Checked)
            backups.item(1).setCheckState(Qt.CheckState.Unchecked)
            delete_button = next(
                button
                for button in dialog.findChildren(QPushButton)
                if button.text() == "Delete marked"
            )
            delete_button.click()
            self.assertEqual(backups.count(), 1)
            return QDialog.DialogCode.Rejected

        with (
            patch.object(state, "PATH", self.config_path),
            patch("umbriel_config_gui.window.config_gui_data_dir", return_value=self.tempdir.name),
            patch("umbriel_config_gui.window.migrate_gui_directory"),
            patch(
                "umbriel_config_gui.window.QMessageBox.question",
                return_value=QMessageBox.StandardButton.Yes,
            ),
            patch.object(QDialog, "exec", exec_dialog),
        ):
            Window.restore_backup(host)

        self.assertFalse(os.path.exists(marked))
        self.assertTrue(os.path.exists(unmarked))

    def test_bulk_delete_can_be_cancelled_then_confirmed(self):
        snapshots = [
            self.create_backup("config.toml.20260101.bak"),
            self.create_backup("config.toml.20260102.bak"),
        ]
        host = QMainWindow()
        self.addCleanup(host.close)

        def exec_dialog(dialog):
            backups = dialog.findChild(QListWidget)
            buttons = {button.text(): button for button in dialog.findChildren(QPushButton)}
            self.assertFalse(buttons["Delete marked"].isEnabled())
            buttons["Select all"].click()
            self.assertTrue(buttons["Delete marked"].isEnabled())
            buttons["Delete marked"].click()
            self.assertTrue(all(os.path.exists(path) for path in snapshots))
            self.assertEqual(backups.count(), 2)
            buttons["Delete marked"].click()
            self.assertEqual(backups.count(), 0)
            self.assertFalse(buttons["Delete marked"].isEnabled())
            return QDialog.DialogCode.Rejected

        with (
            patch.object(state, "PATH", self.config_path),
            patch("umbriel_config_gui.window.config_gui_data_dir", return_value=self.tempdir.name),
            patch("umbriel_config_gui.window.migrate_gui_directory"),
            patch(
                "umbriel_config_gui.window.QMessageBox.question",
                side_effect=[QMessageBox.StandardButton.Cancel, QMessageBox.StandardButton.Yes],
            ),
            patch.object(QDialog, "exec", exec_dialog),
        ):
            Window.restore_backup(host)

        self.assertTrue(all(not os.path.exists(path) for path in snapshots))


if __name__ == "__main__":
    unittest.main()

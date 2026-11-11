import os
import tempfile
import unittest
from unittest.mock import patch

from PySide6.QtWidgets import QApplication, QPushButton, QTableWidget

from umbriel_config_gui import desktop


class UserDirsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.tempdir = tempfile.TemporaryDirectory()
        self.addCleanup(self.tempdir.cleanup)
        self.path = os.path.join(self.tempdir.name, "user-dirs.dirs")
        for name, value in (
            ("USER_DIRS", self.path),
            ("gui_backup_file", lambda _name: os.path.join(self.tempdir.name, "backup")),
        ):
            patcher = patch.object(desktop, name, value)
            patcher.start()
            self.addCleanup(patcher.stop)

    def test_edit_save_and_clear_preserves_unrelated_lines(self):
        original = '# User folders\nXDG_DOCUMENTS_DIR="$HOME/Documents"\nXDG_CUSTOM_DIR="/old"\n'
        with open(self.path, "w", encoding="utf-8") as file:
            file.write(original)
        page = desktop.UserDirs()
        self.addCleanup(page.close)
        page.resize(900, 700)
        page.show()
        self.app.processEvents()
        self.assertFalse(page.findChildren(QTableWidget))
        page.path_edits["DOCUMENTS"].setText("$HOME/Work")
        page.path_edits["CUSTOM"].clear()
        page.path_edits["MUSIC"].setText("/data/Music")
        page.validate()
        page.commit()
        with open(self.path, encoding="utf-8") as file:
            text = file.read()
        self.assertIn('# User folders\n', text)
        self.assertIn('XDG_DOCUMENTS_DIR="$HOME/Work"', text)
        self.assertIn('XDG_MUSIC_DIR="/data/Music"', text)
        self.assertNotIn("XDG_CUSTOM_DIR", text)
        with open(os.path.join(self.tempdir.name, "backup"), encoding="utf-8") as file:
            self.assertEqual(file.read(), original)
        page.commit()
        self.assertFalse(page.changed)

    def test_browse_and_validate_paths(self):
        page = desktop.UserDirs()
        self.addCleanup(page.close)
        home = os.path.expanduser("~")
        buttons = page.findChildren(QPushButton)
        browse = next(button for button in buttons if button.accessibleName() == "Browse Documents folder")
        with patch.object(desktop.QFileDialog, "getExistingDirectory", return_value=os.path.join(home, "Work")):
            browse.click()
        self.assertEqual(page.path_edits["DOCUMENTS"].text(), "$HOME/Work")
        page.path_edits["DOCUMENTS"].setText('bad"path')
        with self.assertRaisesRegex(ValueError, "double quotes"):
            page.validate()


if __name__ == "__main__":
    unittest.main()

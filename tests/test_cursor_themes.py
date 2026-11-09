import os
import tempfile
import unittest
from unittest.mock import patch

import tomlkit
from PySide6.QtWidgets import QApplication

from umbriel_config_gui import common, desktop, field_defs, field_widget, settings_layout, state
from umbriel_config_gui.common import MISSING
from umbriel_config_gui.field_widget import FieldWidget, apply_fields, installed_cursor_themes
from umbriel_config_gui.window import Window


class CursorThemeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def test_discovers_themes_in_xdg_and_legacy_locations(self):
        with tempfile.TemporaryDirectory() as home:
            data_home = os.path.join(home, "data")
            data_dir = os.path.join(home, "system")
            for root, name in (
                (os.path.join(home, ".icons"), "Legacy"),
                (os.path.join(data_home, "icons"), "User"),
                (os.path.join(data_dir, "icons"), "System"),
                (os.path.join(data_dir, "icons"), "User"),
            ):
                os.makedirs(os.path.join(root, name, "cursors"))
            os.makedirs(os.path.join(data_dir, "icons", "IconOnly", "scalable"))
            alias = os.path.join(data_home, "icons", "default")
            os.makedirs(alias)
            with open(os.path.join(alias, "index.theme"), "w", encoding="utf-8") as index:
                index.write("[Icon Theme]\nInherits=User\n")
            os.symlink(os.path.join(data_home, "icons", "User"),
                       os.path.join(data_home, "icons", "Linked"))
            env = {"HOME": home, "XDG_DATA_HOME": data_home, "XDG_DATA_DIRS": data_dir}
            with patch.dict(os.environ, env, clear=True):
                themes = installed_cursor_themes()
            self.assertEqual(
                [name for name in themes if name in {"default", "Legacy", "Linked", "System", "User", "IconOnly"}],
                ["default", "Legacy", "Linked", "System", "User"],
            )

    def test_xcursor_path_overrides_standard_locations(self):
        with tempfile.TemporaryDirectory() as home:
            custom = os.path.join(home, "custom")
            os.makedirs(os.path.join(custom, "Custom", "cursors"))
            os.makedirs(os.path.join(home, ".icons", "Ignored", "cursors"))
            env = {"HOME": home, "XCURSOR_PATH": os.pathsep.join(["~/custom", os.path.join(home, "missing")])}
            with patch.dict(os.environ, env, clear=True):
                self.assertEqual(installed_cursor_themes(), ["Custom"])

    def test_selection_custom_values_and_optional_save(self):
        field = next(field for title, fields in field_defs.TABS["Input"] if title == "Cursor"
                     for field in fields if field.path == ("input", "cursor", "theme"))
        with (
            patch.object(field_widget, "installed_cursor_themes", return_value=["Alpha", "Beta"]),
            patch.object(state, "ACTIVE_SCHEMA_OPTIONS", {
                "input.cursor.theme": {"values": ["schema-value"]}
            }),
        ):
            widget = FieldWidget(field, "Previously configured")
            self.addCleanup(widget.close)
            self.assertTrue(widget.w.isEditable())
            self.assertEqual(widget.w.currentText(), "Previously configured")
            self.assertGreaterEqual(widget.w.findText("Alpha"), 0)
            self.assertGreaterEqual(widget.w.findText("Beta"), 0)
            self.assertEqual(widget.w.findText("schema-value"), -1)
            doc = tomlkit.parse('[input.cursor]\ntheme = "Previously configured"\n')
            widget.w.setCurrentText("Beta")
            apply_fields(doc, [widget])
            self.assertEqual(doc["input"]["cursor"]["theme"], "Beta")
            widget.w.setEditText("My custom theme")
            apply_fields(doc, [widget])
            self.assertEqual(doc["input"]["cursor"]["theme"], "My custom theme")
            widget.check.setChecked(False)
            self.assertIsNone(widget.get())
            apply_fields(doc, [widget])
            self.assertNotIn("theme", doc["input"]["cursor"])

            unset = FieldWidget(field, MISSING)
            self.addCleanup(unset.close)
            self.assertIsNone(unset.get())
            self.assertFalse(unset.w.isEnabled())
            unset.check.setChecked(True)
            unset.w.setCurrentText("Alpha")
            self.assertEqual(unset.get(), "Alpha")

    def test_empty_theme_search_still_allows_custom_input(self):
        field = next(field for title, fields in field_defs.TABS["Input"] if title == "Cursor"
                     for field in fields if field.path == ("input", "cursor", "theme"))
        with patch.object(field_widget, "installed_cursor_themes", return_value=[]):
            widget = FieldWidget(field, "custom")
        self.addCleanup(widget.close)
        self.assertEqual(widget.get(), "custom")
        widget.w.setEditText("another")
        self.assertEqual(widget.get(), "another")

    def test_window_tracks_and_saves_cursor_selection(self):
        with tempfile.TemporaryDirectory() as directory:
            path = os.path.join(directory, "config.toml")
            with open(path, "w", encoding="utf-8") as config:
                config.write('[input.cursor]\ntheme = "Old"\n')
            with (
                patch.object(state, "PATH", path),
                patch.object(state, "ACTIVE_SCHEMA_OPTIONS", {}),
                patch.object(common, "GUI_DATA_DIR", os.path.join(directory, "data")),
                patch.object(settings_layout, "_GROUP_EXPANSION_PATH", os.path.join(directory, "state.json")),
                patch.object(settings_layout, "_group_expansion_states", {}),
                patch.object(field_widget, "installed_cursor_themes", return_value=["Alpha", "Beta"]),
                patch.object(desktop, "USER_DIRS", os.path.join(directory, "user-dirs.dirs")),
                patch.object(desktop, "MIMEAPPS_PATH", os.path.join(directory, "mimeapps.list")),
                patch.object(desktop, "installed_desktop_apps", return_value=[]),
                patch("umbriel_config_gui.window.load_umbriel_schema", side_effect=FileNotFoundError("test")),
            ):
                window = Window(path)
                self.addCleanup(window.deleteLater)
                self.assertEqual(window.windowTitle(), f"Umbriel Settings - {path}")
                window.rebuild_box.setChecked(False)
                window.validate_box.setChecked(False)
                window.side_tabs.nav.setCurrentRow(window.side_tabs.page_rows["Input"])
                self.app.processEvents()
                page = window.side_tabs.page_widgets["Input"]
                widget = next(field for field in page.findChildren(FieldWidget)
                              if field.f.path == ("input", "cursor", "theme"))
                window._dirty = False
                widget.w.setCurrentText("Beta")
                self.assertTrue(window._dirty)
                with patch.object(window, "confirm_save_diff", return_value=True):
                    self.assertTrue(window.save())
                with open(path, encoding="utf-8") as config:
                    self.assertEqual(tomlkit.parse(config.read())["input"]["cursor"]["theme"], "Beta")


if __name__ == "__main__":
    unittest.main()

import os
import tempfile
import unittest
from unittest.mock import patch

import tomlkit
from PySide6.QtCore import QPoint, Qt
from PySide6.QtGui import QColor
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication

from umbriel_config_gui import kde_titlebar, settings, state
from umbriel_config_gui.field_defs import TABS
from umbriel_config_gui.settings import apply_fields, form_page


class KdeTitleBarTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def test_previews_reload_and_explicit_import_preserves_alpha(self):
        with tempfile.TemporaryDirectory() as directory:
            config = os.path.join(directory, "qt6ct.conf")
            scheme = os.path.join(directory, "noctalia.colors")
            with open(config, "w", encoding="utf-8") as file:
                file.write(f"[Appearance]\ncustom_palette=true\ncolor_scheme_path={scheme}\n")

            def write_scheme(active, header="31,31,31"):
                replacement = scheme + ".tmp"
                with open(replacement, "w", encoding="utf-8") as file:
                    file.write(f"[WM]\nactiveBackground={active}\ninactiveBackground=4,5,6\n"
                               "activeForeground=7,8,9\ninactiveForeground=10,11,12\n"
                               f"[Colors:Header]\nBackgroundNormal={header}\n"
                               "[Colors:Header][Inactive]\nBackgroundNormal=19,19,19\n")
                os.replace(replacement, scheme)

            write_scheme("1,2,3")
            doc = tomlkit.parse("[colors.title_bar]\nbackground_unfocused = '#ABCDEF80' # keep\n")
            title_bar = next(group for group in TABS["Colors"] if group[0] == "Title bar")
            fields = []
            with (
                patch.object(kde_titlebar, "qt6ct_config_path", return_value=config),
                patch.object(state, "ACTIVE_SCHEMA_OPTIONS", {}),
                patch.object(settings, "load_group_expansion_states", return_value={}),
            ):
                page = form_page([title_bar], doc, fields, category="Colors")
                self.addCleanup(page.deleteLater)
                by_name = {field.f.path[-1]: field for field in fields}
                focused = by_name["background"]
                unfocused = by_name["background_unfocused"]
                self.assertEqual(focused.w.text(), "#010203FF")
                self.assertIsNone(focused.get())
                self.assertEqual(unfocused.get(), "#ABCDEF80")
                self.assertEqual(focused.kde_source.currentIndex(), 0)
                self.assertEqual(unfocused.kde_source.currentIndex(), -1)
                self.assertEqual(by_name["text"].w.text(), "#070809FF")
                apply_fields(doc, fields)
                self.assertNotIn("background", doc["colors"]["title_bar"])
                focused.kde_source.activate(2)
                self.assertEqual(focused.get(), "#1F1F1FFF")
                focused.opacity_spin.setValue(0.5)
                focused.kde_source.activate(1)
                self.assertEqual(focused.get(), "#01020380")
                focused.kde_source.activate(2)
                self.assertEqual(focused.get(), "#1F1F1F80")
                unfocused.kde_source.activate(2)
                self.assertEqual(unfocused.get(), "#13131380")
                unfocused.kde_source.activate(1)
                self.assertEqual(unfocused.get(), "#04050680")
                focused.kde_source.activate(1)
                self.assertEqual(focused.get(), "#01020380")
                focused.kde_source.activate(0)
                self.assertIsNone(focused.get())
                write_scheme("16,32,48", "32,33,34")
                QTest.qWait(900)
                self.assertEqual(focused.w.text(), "#10203080")
                self.assertEqual(unfocused.get(), "#04050680")
                focused.kde_source.activate(2)
                self.assertEqual(focused.get(), "#20212280")
                write_scheme("16,32,48", "51,52,53")
                QTest.qWait(900)
                self.assertEqual(focused.get(), "#20212280")
                focused.kde_source.activate(2)
                self.assertEqual(focused.get(), "#33343580")
                focused.kde_source.activate(0)
                unfocused.set_color("#AABBCC80")
                unfocused.check.setChecked(False)
                self.assertEqual(unfocused.w.text(), "#04050680")
                unfocused.check.setChecked(True)
                self.assertEqual(unfocused.kde_source.currentIndex(), -1)
                apply_fields(doc, fields)
                self.assertEqual(doc["colors"]["title_bar"]["background_unfocused"], "#04050680")
                self.assertIn("# keep", tomlkit.dumps(doc))
                self.assertNotIn("background", doc["colors"]["title_bar"])

    def test_missing_header_only_disables_background_import(self):
        with tempfile.TemporaryDirectory() as directory:
            config = os.path.join(directory, "qt6ct.conf")
            scheme = os.path.join(directory, "scheme.colors")
            with open(config, "w", encoding="utf-8") as file:
                file.write(f"[Appearance]\ncustom_palette=true\ncolor_scheme_path={scheme}\n")
            with open(scheme, "w", encoding="utf-8") as file:
                file.write("[WM]\nactiveBackground=1,2,3\ninactiveBackground=4,5,6\n")
            fields = []
            title_bar = next(group for group in TABS["Colors"] if group[0] == "Title bar")
            with (
                patch.object(kde_titlebar, "qt6ct_config_path", return_value=config),
                patch.object(state, "ACTIVE_SCHEMA_OPTIONS", {}),
                patch.object(settings, "load_group_expansion_states", return_value={}),
            ):
                page = form_page([title_bar], tomlkit.parse(""), fields, category="Colors")
                self.addCleanup(page.deleteLater)
                for name in ("background", "background_unfocused"):
                    field = next(field for field in fields if field.f.path[-1] == name)
                    self.assertTrue(field.kde_source.isSegmentEnabled(1))
                    self.assertFalse(field.kde_source.isSegmentEnabled(2))
                    self.assertIn("missing", field.kde_source.toolTip())
                    field.kde_source.activate(2)
                    self.assertEqual(field.kde_source.currentIndex(), 0)
                    self.assertIsNone(field.get())

    def test_invalid_or_missing_scheme_does_not_change_fields(self):
        with tempfile.TemporaryDirectory() as directory:
            config = os.path.join(directory, "qt6ct.conf")
            scheme = os.path.join(directory, "bad.colors")
            with open(config, "w", encoding="utf-8") as file:
                file.write(f"[Appearance]\ncustom_palette=true\ncolor_scheme_path={scheme}\n")
            with open(scheme, "w", encoding="utf-8") as file:
                file.write("[WM]\nactiveBackground=999,0,0\n"
                           "[Colors:Header]\nBackgroundNormal=1,2,3\n")
            fields = []
            title_bar = next(group for group in TABS["Colors"] if group[0] == "Title bar")
            with (
                patch.object(kde_titlebar, "qt6ct_config_path", return_value=config),
                patch.object(state, "ACTIVE_SCHEMA_OPTIONS", {}),
                patch.object(settings, "load_group_expansion_states", return_value={}),
            ):
                page = form_page([title_bar], tomlkit.parse(""), fields, category="Colors")
                self.addCleanup(page.deleteLater)
                field = next(field for field in fields if field.f.path[-1] == "background")
                self.assertEqual(field.w.text(), "#292933FF")
                self.assertFalse(field.kde_source.isSegmentEnabled(1))
                self.assertIn("Invalid", field.kde_source.toolTip())
                self.assertTrue(field.kde_source.isSegmentEnabled(2))
                field.kde_source.activate(2)
                self.assertEqual(field.get(), "#010203FF")
                os.remove(scheme)
                page.kde_titlebar_follower.refresh()
                self.assertFalse(field.kde_source.isSegmentEnabled(1))
                self.assertIn("unavailable", field.kde_source.toolTip())

    def test_pill_mouse_keyboard_and_custom_color(self):
        field = settings.FieldWidget(
            next(field for title, fields in TABS["Colors"] if title == "Title bar"
                 for field in fields if field.path[-1] == "background"),
            "#11223380",
        )
        self.addCleanup(field.close)
        field.set_kde_color(QColor("#445566"), "title")
        field.set_kde_background(QColor("#778899"), "background")
        field.show()
        self.app.processEvents()
        source = field.kde_source
        self.assertEqual(source.currentIndex(), -1)
        QTest.mouseClick(source, Qt.MouseButton.LeftButton, pos=QPoint(115, 20))
        self.assertEqual((source.currentIndex(), field.get()), (1, "#44556680"))
        QTest.keyClick(source, Qt.Key.Key_Right)
        self.assertEqual((source.currentIndex(), field.get()), (2, "#77889980"))
        with patch.object(settings.QColorDialog, "getColor", return_value=QColor("#AABBCC")):
            field.pick_color()
        self.assertEqual(source.currentIndex(), -1)
        self.assertEqual(field.get(), "#AABBCCFF")
        QTest.mouseClick(source, Qt.MouseButton.LeftButton, pos=QPoint(40, 20))
        self.assertEqual(source.currentIndex(), 0)
        self.assertIsNone(field.get())
        source.setSegmentAvailable(1, False)
        QTest.mouseClick(source, Qt.MouseButton.LeftButton, pos=QPoint(115, 20))
        self.assertEqual(source.currentIndex(), 0)
        QTest.keyClick(source, Qt.Key.Key_Right)
        self.assertEqual((source.currentIndex(), field.get()), (2, "#778899FF"))


if __name__ == "__main__":
    unittest.main()

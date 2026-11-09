import os
import tempfile
import unittest
from unittest.mock import patch

import tomlkit
from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QPalette
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QLabel, QSizePolicy

from umbriel_config_gui import common, desktop, settings_layout, state
from umbriel_config_gui.common import MISSING
from umbriel_config_gui.field_defs import F
from umbriel_config_gui.field_widget import FieldWidget, apply_fields
from umbriel_config_gui.window import Window


class SettingsSliderTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def test_schema_bounds_override_field_bounds_and_save_slider_value(self):
        field = F("Corner radius", "appearance.corner_radius", "int", 10, (0, 100), True)
        schema = {"appearance.corner_radius": {"min": 2, "max": 40, "default": 12}}
        with patch.object(state, "ACTIVE_SCHEMA_OPTIONS", schema):
            widget = FieldWidget(field, MISSING)
        self.assertEqual((widget.slider.minimum(), widget.slider.maximum()), (2, 40))
        self.assertEqual((widget.w.minimum(), widget.w.maximum()), (2, 40))
        self.assertEqual(widget.slider.value(), 12)
        self.assertFalse(widget.slider.isEnabled())
        self.assertIsNone(widget.get())

        widget.check.setChecked(True)
        self.assertTrue(widget.slider.isEnabled())
        widget.slider.setValue(30)
        self.assertEqual(widget.w.value(), 30)
        widget.w.setValue(15)
        self.assertEqual(widget.slider.value(), 15)
        widget.slider.setValue(100)
        self.assertEqual(widget.get(), 40)
        doc = tomlkit.parse("")
        apply_fields(doc, [widget])
        self.assertEqual(doc["appearance"]["corner_radius"], 40)
        widget.check.setChecked(False)
        self.assertFalse(widget.slider.isEnabled())
        apply_fields(doc, [widget])
        self.assertNotIn("corner_radius", doc["appearance"])

    def test_float_precision_negative_range_and_keyboard(self):
        field = F("Opacity", "opacity", "float", 0.0, (-1.0, 1.0), True)
        with patch.object(state, "ACTIVE_SCHEMA_OPTIONS", {}):
            widget = FieldWidget(field, 0.0)
        self.assertEqual((widget.slider.minimum(), widget.slider.maximum()), (-1000, 1000))
        self.assertEqual(widget.slider.value(), 0)
        widget.slider.setValue(-125)
        self.assertEqual(widget.get(), -0.125)
        widget.w.setValue(0.375)
        self.assertEqual(widget.slider.value(), 375)
        QTest.keyClick(widget.slider, Qt.Key.Key_Right)
        self.assertEqual(widget.get(), 0.376)
        widget.slider.setValue(-5000)
        self.assertEqual(widget.get(), -1.0)

    def test_unbounded_fields_keep_numeric_input_without_slider(self):
        field = F("Value", "value", "int", 1, None, False)
        with patch.object(state, "ACTIVE_SCHEMA_OPTIONS", {}):
            widget = FieldWidget(field, 1)
        self.assertIsNone(widget.slider)
        widget.w.setValue(25)
        self.assertEqual(widget.get(), 25)

    def test_list_fields_expand_with_window_width(self):
        field = F("Required include files", "include.files", "list", [], None, True)
        with patch.object(state, "ACTIVE_SCHEMA_OPTIONS", {}):
            widget = FieldWidget(field, [])
        self.assertEqual(widget.w.sizePolicy().horizontalPolicy(), QSizePolicy.Policy.Expanding)
        self.assertGreater(widget.w.maximumWidth(), 460)
        self.assertEqual(widget.get(), [])

    def test_title_bar_color_opacity_round_trip_and_palette_change(self):
        for name in ("background", "background_unfocused"):
            with self.subTest(name=name), patch.object(state, "ACTIVE_SCHEMA_OPTIONS", {}):
                field = F(name, f"colors.title_bar.{name}", "color", "#112233FF", None, True)
                widget = FieldWidget(field, "#12345680")
                self.addCleanup(widget.close)
                widget.show()
                self.app.processEvents()
                self.assertIs(widget.opacity_slider.parentWidget(), widget.opacity_widget)
                self.assertEqual(widget.opacity_slider.value(), 128)
                self.assertEqual(widget.opacity_spin.value(), 0.502)
                widget.opacity_slider.setValue(0)
                self.assertEqual(widget.get(), "#12345600")
                widget.opacity_spin.setValue(1.0)
                self.assertEqual(widget.get(), "#123456FF")
                widget.set_color("#ABCDEF40")
                self.assertEqual(widget.opacity_slider.value(), 64)
                self.assertEqual(widget.opacity_spin.value(), 0.251)
                palette = QPalette(widget.palette())
                palette.setColor(QPalette.ColorRole.Window, QColor("#345678"))
                widget.setPalette(palette)
                self.app.processEvents()
                self.assertEqual(widget.get(), "#ABCDEF40")
                doc = tomlkit.parse("[colors.title_bar]\n" + name + " = '#12345680' # keep\n")
                apply_fields(doc, [widget])
                self.assertEqual(doc["colors"]["title_bar"][name], "#ABCDEF40")
                self.assertIn("# keep", tomlkit.dumps(doc))
                widget.check.setChecked(False)
                self.assertFalse(widget.opacity_slider.isEnabled())
                self.assertFalse(widget.opacity_spin.isEnabled())
                apply_fields(doc, [widget])
                self.assertNotIn(name, doc["colors"]["title_bar"])

    def test_title_bar_unset_and_other_colors(self):
        with patch.object(state, "ACTIVE_SCHEMA_OPTIONS", {}):
            widget = FieldWidget(F("Background", "colors.title_bar.background", "color",
                                   "#112233FF", None, True), MISSING)
            other = FieldWidget(F("Text", "colors.title_bar.text", "color",
                                  "#FFFFFFFF", None, True), "#FFFFFFFF")
        self.addCleanup(widget.close)
        self.addCleanup(other.close)
        self.assertIsNone(widget.get())
        self.assertFalse(widget.opacity_slider.isEnabled())
        widget.check.setChecked(True)
        self.assertTrue(widget.opacity_slider.isEnabled())
        widget.opacity_spin.setValue(0.5)
        self.assertEqual(widget.get(), "#11223380")
        self.assertEqual(widget.opacity_spin.value(), 0.502)
        self.assertIsNone(other.opacity_slider)

    def test_title_bar_opacity_marks_window_dirty_and_saves(self):
        with tempfile.TemporaryDirectory() as directory:
            path = os.path.join(directory, "config.toml")
            with open(path, "w", encoding="utf-8") as config:
                config.write("[colors.title_bar]\nbackground = '#112233' # focused\n"
                             "background_unfocused = '#445566AA' # unfocused\n")
            with (
                patch.object(state, "PATH", path),
                patch.object(state, "ACTIVE_SCHEMA_OPTIONS", {}),
                patch.object(common, "GUI_DATA_DIR", os.path.join(directory, "data")),
                patch.object(settings_layout, "_GROUP_EXPANSION_PATH", os.path.join(directory, "state.json")),
                patch.object(settings_layout, "_group_expansion_states", {}),
                patch.object(desktop, "USER_DIRS", os.path.join(directory, "user-dirs.dirs")),
                patch.object(desktop, "MIMEAPPS_PATH", os.path.join(directory, "mimeapps.list")),
                patch.object(desktop, "installed_desktop_apps", return_value=[]),
                patch("umbriel_config_gui.window.load_umbriel_schema", return_value={"options": []}),
            ):
                window = Window(path)
                self.addCleanup(window.close)
                window.rebuild_box.setChecked(False)
                window.validate_box.setChecked(False)
                window.side_tabs.nav.setCurrentRow(window.side_tabs.page_rows["Colors"])
                window.show()
                self.app.processEvents()
                page = window.side_tabs.page_widgets["Colors"]
                widgets = {
                    field.f.path[-1]: field for field in page.findChildren(FieldWidget)
                    if field.f.path[:2] == ("colors", "title_bar")
                }
                window._dirty = False
                widgets["background"].set_kde_color(QColor("#AABBCC"), "test color")
                widgets["background"].kde_source.activate(1)
                self.assertTrue(window._dirty)
                window._dirty = False
                widgets["background"].set_kde_color(QColor("#112233"), "updated test color")
                widgets["background"].kde_source.activate(1)
                self.assertTrue(window._dirty)
                window._dirty = False
                widgets["background"].opacity_slider.setValue(128)
                self.assertTrue(window._dirty)
                widgets["background_unfocused"].opacity_spin.setValue(0.25)
                with patch.object(window, "confirm_save_diff", return_value=True):
                    self.assertTrue(window.save())
                with open(path, encoding="utf-8") as config:
                    text = config.read()
                values = tomlkit.parse(text)["colors"]["title_bar"]
                self.assertEqual(values["background"], "#11223380")
                self.assertEqual(values["background_unfocused"], "#44556640")
                self.assertIn("# focused", text)
                self.assertIn("# unfocused", text)

    def test_slider_marks_window_dirty_and_saves(self):
        with tempfile.TemporaryDirectory() as directory:
            path = os.path.join(directory, "config.toml")
            with open(path, "w", encoding="utf-8") as config:
                config.write("[appearance]\ncorner_radius = 20\n\n[input]\n# Keep this comment\nkeyboard_layout = 'us'\n")
            schema = {
                "options": [
                    {"path": "appearance.corner_radius", "type": "int",
                     "min": 0, "max": 60, "default": 10}
                ]
            }
            with (
                patch.object(state, "PATH", path),
                patch.object(state, "ACTIVE_SCHEMA_OPTIONS", {}),
                patch.object(common, "GUI_DATA_DIR", os.path.join(directory, "data")),
                patch.object(settings_layout, "_GROUP_EXPANSION_PATH", os.path.join(directory, "state.json")),
                patch.object(settings_layout, "_group_expansion_states", {}),
                patch.object(desktop, "USER_DIRS", os.path.join(directory, "user-dirs.dirs")),
                patch.object(desktop, "MIMEAPPS_PATH", os.path.join(directory, "mimeapps.list")),
                patch.object(desktop, "installed_desktop_apps", return_value=[]),
                patch("umbriel_config_gui.window.load_umbriel_schema", return_value=schema),
            ):
                window = Window(path)
                self.addCleanup(window.deleteLater)
                window.rebuild_box.setChecked(False)
                window.validate_box.setChecked(False)
                window.side_tabs.nav.setCurrentRow(window.side_tabs.page_rows["Appearance"])
                window.resize(930, 760)
                window.show()
                self.app.processEvents()
                page = window.side_tabs.page_widgets["Appearance"]
                widget = next(
                    field for field in page.findChildren(FieldWidget)
                    if field.f.path == ("appearance", "corner_radius")
                )
                self.assertTrue(widget.field_label.font().bold())
                self.assertEqual(widget.y(), widget.field_label.parentWidget().y())
                self.assertLess(widget.slider.geometry().right(), widget.width())
                window._dirty = False
                widget.slider.setValue(42)
                self.assertTrue(window._dirty)
                with patch.object(window, "confirm_save_diff", return_value=True):
                    self.assertTrue(window.save())
                self.assertIn("Input", window.side_tabs._lazy_pages)
                self.assertNotIn("Keybinds", window.side_tabs._lazy_pages)
                with open(path, encoding="utf-8") as config:
                    text = config.read()
                self.assertEqual(tomlkit.parse(text)["appearance"]["corner_radius"], 42)
                self.assertIn("# Keep this comment\nkeyboard_layout = 'us'", text)


if __name__ == "__main__":
    unittest.main()

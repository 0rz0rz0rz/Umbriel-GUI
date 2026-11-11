import unittest
from unittest.mock import patch

from PySide6.QtCore import QSize, Qt
from PySide6.QtGui import QColor, QIcon, QPalette
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QLineEdit, QWidget

from umbriel_config_gui import state
from umbriel_config_gui.common import MISSING, tomlkit
from umbriel_config_gui.editors import EntryEditor
from umbriel_config_gui.field_defs import F
from umbriel_config_gui.field_widget import FieldWidget
from umbriel_config_gui.sidebar import SideTabs
from umbriel_config_gui.sidebar_icons import _PAGE_PICTOGRAMS
from umbriel_config_gui.settings_layout import form_page


class SidebarSearchTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.tabs = SideTabs()
        self.addCleanup(self.tabs.close)
        for patcher in (
            patch.object(state, "ACTIVE_SCHEMA_OPTIONS", {}),
            patch(
            "umbriel_config_gui.settings_layout.load_group_expansion_states",
            return_value={},
            ),
            patch("umbriel_config_gui.settings_layout.save_group_expansion_state"),
        ):
            patcher.start()
            self.addCleanup(patcher.stop)
        self.tabs.addTab(QWidget(), "Base")

    def test_search_matches_fields_in_lazy_pages_after_debounce(self):
        fields = []

        def build_page():
            return form_page(
                [
                    (
                        "General options",
                        [F("Distinctive option", "general.enabled", "bool", False, None, True)],
                    )
                ],
                tomlkit.document(),
                fields,
                category="Deferred",
            )

        self.tabs.addLazyTab(build_page, "Deferred")
        with patch(
            "umbriel_config_gui.settings_layout.load_group_expansion_states",
            return_value={},
        ):
            self.tabs.search.setText("distinctive")
            QTest.qWait(250)

        self.assertEqual(len(fields), 1)
        self.assertFalse(self.tabs.nav.item(self.tabs.page_rows["Deferred"]).isHidden())
        self.assertIs(self.tabs.content.currentWidget(), self.tabs.stack)

    def test_clearing_search_before_debounce_keeps_pages_lazy(self):
        built = []
        self.tabs.addLazyTab(lambda: built.append(True) or QWidget(), "Deferred")

        self.tabs.search.setText("missing")
        self.tabs.search.clear()
        QTest.qWait(250)

        self.assertEqual(built, [])
        self.assertIn("Deferred", self.tabs._lazy_pages)

    def test_overridden_filter_compares_defaults_and_combines_with_search(self):
        fields = []
        doc = tomlkit.parse("[general]\na = 4\nb = 2\n")
        page = form_page(
            [
                ("First", [
                    F("First value", "general.a", "int", 1, None, True),
                    F("Default value", "general.b", "int", 2, None, True),
                    F("Unset value", "general.c", "int", 3, None, True),
                ]),
                ("Second", [F("Other value", "general.d", "bool", False, None, False)]),
            ],
            doc, fields, category="Options",
        )
        self.tabs.addTab(page, "Options")
        self.tabs.nav.setCurrentRow(self.tabs.page_rows["Options"])
        self.tabs.overridden.setChecked(True)
        QTest.qWait(250)

        first, equal, unset, other = fields
        self.assertTrue(first.search_form.isRowVisible(first.search_row))
        for field in (equal, unset, other):
            self.assertFalse(field.search_form.isRowVisible(field.search_row))
        self.assertTrue(other.search_group.isHidden())
        self.assertTrue(other.search_group.section_button.isHidden())
        self.assertFalse(self.tabs.nav.item(self.tabs.page_rows["Base"]).isHidden())

        self.tabs.search.setText("first")
        QTest.qWait(250)
        self.assertTrue(first.search_form.isRowVisible(first.search_row))
        first.w.setValue(1)
        QTest.qWait(250)
        self.assertFalse(first.search_form.isRowVisible(first.search_row))
        self.assertFalse(first.search_group.filter_notice.isHidden())
        self.tabs.search.clear()
        self.tabs.overridden.setChecked(False)
        QTest.qWait(250)
        self.assertTrue(first.search_form.isRowVisible(first.search_row))
        self.assertFalse(other.search_group.isHidden())
        self.assertFalse(other.search_group.section_button.isHidden())

    def test_filter_applies_to_pages_built_after_it_is_enabled(self):
        fields = []
        self.tabs.addLazyTab(
            lambda: form_page(
                [("General", [F("Value", "value", "int", 1, None, False)])],
                tomlkit.parse("value = 2\n"), fields, category="Deferred",
            ),
            "Deferred",
        )
        self.tabs.overridden.setChecked(True)
        QTest.qWait(250)
        self.tabs.nav.setCurrentRow(self.tabs.page_rows["Deferred"])
        QTest.qWait(250)
        self.assertEqual(len(fields), 1)
        self.assertTrue(fields[0].search_form.isRowVisible(fields[0].search_row))
        fields[0].w.setValue(1)
        QTest.qWait(250)
        self.assertFalse(fields[0].search_form.isRowVisible(fields[0].search_row))
        self.assertFalse(fields[0].search_group.filter_notice.isHidden())

    def test_overridden_filter_uses_schema_defaults(self):
        with patch.object(state, "ACTIVE_SCHEMA_OPTIONS", {"value": {"default": 4}}):
            widget = FieldWidget(F("Value", "value", "int", 1, None, True), 4)
        self.addCleanup(widget.close)
        self.assertFalse(widget.is_overridden())
        widget.w.setValue(1)
        self.assertTrue(widget.is_overridden())

    def test_filter_tracks_the_selected_entry(self):
        doc = tomlkit.parse("[[entry]]\nvalue = 2\n[[entry]]\nvalue = 1\n")
        with patch("umbriel_config_gui.editors.load_entry_labels", return_value=[]):
            page = EntryEditor(
                doc, "entry", "aot",
                [("General", [F("Value", "value", "int", 1, None, False)])],
                "Entries",
            )
        self.tabs.addTab(page, "Entries")
        self.tabs.nav.setCurrentRow(self.tabs.page_rows["Entries"])
        self.tabs.overridden.setChecked(True)
        QTest.qWait(250)
        self.assertTrue(page.fws[0].search_form.isRowVisible(page.fws[0].search_row))
        page.list.setCurrentRow(1)
        QTest.qWait(250)
        self.assertFalse(page.fws[0].search_form.isRowVisible(page.fws[0].search_row))
        self.assertFalse(page.fws[0].search_group.filter_notice.isHidden())
        page.list.setCurrentRow(0)
        QTest.qWait(250)
        self.assertTrue(page.fws[0].search_form.isRowVisible(page.fws[0].search_row))

    def test_default_comparison_handles_boolean_colors_and_invalid_toml(self):
        for field, current, expected in (
            (F("Optional", "optional", "bool", True, None, True), MISSING, False),
            (F("Optional", "optional", "bool", True, None, True), True, False),
            (F("Optional", "optional", "bool", True, None, True), False, True),
            (F("Color", "color", "color", "#112233", None, True), "#112233FF", False),
            (F("Color", "color", "color", "#112233", None, True), "#11223380", True),
        ):
            with self.subTest(field=field.label, current=current):
                widget = FieldWidget(field, current)
                self.addCleanup(widget.close)
                self.assertEqual(widget.is_overridden(), expected)

        raw = FieldWidget(F("Raw", "raw", "raw", [1], None, True), [1])
        self.addCleanup(raw.close)
        raw.w.setPlainText("[")
        self.assertTrue(raw.is_overridden())

    def test_color_and_command_changes_emit_filter_notifications(self):
        color = FieldWidget(
            F("Color", "color", "color", "#112233FF", None, True), "#112233FF"
        )
        commands = FieldWidget(
            F("Commands", "commands", "command_list", [], None, True), []
        )
        self.addCleanup(color.close)
        self.addCleanup(commands.close)
        changes = []
        color.valueChanged.connect(lambda: changes.append("color"))
        commands.valueChanged.connect(lambda: changes.append("commands"))
        color.set_color("#11223380")
        commands.add_command()
        entry = commands.w.findChild(QLineEdit)
        entry.setText("example")
        commands.remove_command_row(entry.parentWidget())
        self.assertIn("color", changes)
        self.assertGreaterEqual(changes.count("commands"), 3)
        self.assertTrue(color.is_overridden())
        self.assertFalse(commands.is_overridden())

    def test_section_shortcut_tracks_expansion_from_all_controls(self):
        fields = []
        page = form_page(
            [("General", [F("Value", "value", "int", 1, None, False)])],
            tomlkit.document(), fields, category="Options",
        )
        self.addCleanup(page.close)
        group = fields[0].search_group
        button = group.section_button
        self.assertTrue(button.isChecked())
        group.setExpanded(False)
        self.assertFalse(button.isChecked())
        button.click()
        self.assertTrue(group.header.isChecked())
        self.assertTrue(button.isChecked())
        button.click()
        self.assertFalse(group.header.isChecked())
        self.assertFalse(button.isChecked())
        group.header.click()
        self.assertTrue(button.isChecked())
        page.findChild(QWidget, "settingsOverview").click()
        self.assertFalse(group.header.isChecked())
        self.assertFalse(button.isChecked())

    def test_search_temporarily_expands_and_restores_shortcut_state(self):
        fields = []
        page = form_page(
            [("General", [F("Value", "value", "int", 1, None, False)])],
            tomlkit.document(), fields, category="Options",
        )
        self.tabs.addTab(page, "Options")
        group = fields[0].search_group
        group.setExpanded(False)
        self.tabs.search.setText("value")
        QTest.qWait(250)
        self.assertTrue(group.section_button.isChecked())
        self.tabs.search.clear()
        QTest.qWait(250)
        self.assertFalse(group.header.isChecked())
        self.assertFalse(group.section_button.isChecked())

    def test_shortcut_restores_and_persists_state_with_keyboard(self):
        fields = []
        with patch(
            "umbriel_config_gui.settings_layout.load_group_expansion_states",
            return_value={"Options": {"General": False}},
        ), patch("umbriel_config_gui.settings_layout.save_group_expansion_state") as save:
            page = form_page(
                [("General", [F("Value", "value", "int", 1, None, False)])],
                tomlkit.document(), fields, category="Options",
            )
            self.addCleanup(page.close)
            page.show()
            self.app.processEvents()
            button = fields[0].search_group.section_button
            self.assertFalse(button.isChecked())
            button.setFocus()
            QTest.keyClick(button, Qt.Key.Key_Space)
            self.assertTrue(fields[0].search_group.header.isChecked())
            save.assert_called_once_with("Options", "General", True)

    def test_noncollapsible_section_shortcut_stays_checked(self):
        fields = []
        page = form_page(
            [("General", [F("Value", "value", "int", 1, None, False)])],
            tomlkit.document(), fields, collapsible=False, category="Options",
        )
        self.addCleanup(page.close)
        button = fields[0].search_group.section_button
        button.click()
        self.assertTrue(button.isChecked())

    def test_sidebar_pictograms_follow_palette_and_have_no_color_fallbacks(self):
        for name in (*_PAGE_PICTOGRAMS, "Unknown page"):
            self.tabs.addTab(QWidget(), name)
        for text, selected in (("#f4f4f4", "#123456"), ("#252525", "#eeeeee")):
            palette = QPalette(self.tabs.nav.palette())
            palette.setColor(QPalette.ColorRole.Text, QColor(text))
            palette.setColor(QPalette.ColorRole.HighlightedText, QColor(selected))
            self.tabs.nav.setPalette(palette)
            for name in (*_PAGE_PICTOGRAMS, "Unknown page"):
                item = self.tabs.nav.item(self.tabs.page_rows[name])
                self.assertFalse(item.icon().isNull(), name)
                for mode, expected in ((QIcon.Mode.Normal, text), (QIcon.Mode.Selected, selected)):
                    image = item.icon().pixmap(QSize(32, 32), mode).toImage()
                    pixels = [
                        image.pixelColor(x, y)
                        for y in range(image.height())
                        for x in range(image.width())
                        if image.pixelColor(x, y).alpha() >= 128
                    ]
                    self.assertTrue(pixels, (name, mode))
                    target = QColor(expected)
                    for pixel in pixels:
                        self.assertLessEqual(
                            max(abs(pixel.red() - target.red()),
                                abs(pixel.green() - target.green()),
                                abs(pixel.blue() - target.blue())),
                            2, (name, mode, pixel.name()),
                        )


if __name__ == "__main__":
    unittest.main()

import os
import tempfile
import unittest
from unittest.mock import patch

from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication

from umbriel_config_gui import state
from umbriel_config_gui.common import tomlkit
from umbriel_config_gui.editors import EntryEditor
from umbriel_config_gui.field_defs import (
    INPUT_DEVICE, LAYER_RULE, OUTPUT_GROUPS, SCRATCHPAD, SECURITY_RULE,
    WINDOW_RULE_GROUPS, WORKSPACE_RULE_GROUPS,
)
from umbriel_config_gui.tables import EffectsPage


class EntryEditorLayoutTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        patchers = (
            patch.object(state, "PATH", os.path.join(directory.name, "config.toml")),
            patch.object(state, "ACTIVE_SCHEMA_OPTIONS", {}),
            patch("umbriel_config_gui.editors.load_entry_labels", return_value=[]),
            patch("umbriel_config_gui.settings_layout.load_group_expansion_states", return_value={}),
            patch("umbriel_config_gui.settings_layout.save_group_expansion_state"),
        )
        for patcher in patchers:
            patcher.start()
            self.addCleanup(patcher.stop)

    def cleanup_widget(self, widget):
        widget.close()
        widget.deleteLater()
        QTest.qWait(5)

    def test_long_rule_name_does_not_squeeze_detail_and_split_is_draggable(self):
        namespace = "very-long-layer-name-" * 35
        doc = tomlkit.document()
        entry = tomlkit.table()
        entry["match"] = {"namespace": namespace}
        doc["layer_rule"] = tomlkit.aot()
        doc["layer_rule"].append(entry)
        editor = EntryEditor(doc, "layer_rule", "aot", [("Layer rule", LAYER_RULE)], "[[layer_rule]]", False)
        self.addCleanup(self.cleanup_widget, editor)
        editor.resize(900, 600)
        editor.show()
        QTest.qWait(40)

        splitter = editor.splitter
        left, right = splitter.sizes()
        self.assertEqual(editor.width(), 900)
        self.assertGreater(right, left)
        self.assertGreater(right, 500)
        self.assertGreater(editor.list.horizontalScrollBar().maximum(), 0)
        self.assertIn(namespace, editor.list.item(0).text())
        self.assertEqual(splitter.handle(1).width(), 12)

        splitter.moveSplitter(500, 1)
        QTest.qWait(20)
        self.assertGreater(splitter.sizes()[0], left + 100)
        moved = splitter.sizes()[0]
        editor.commit()
        editor.refresh()
        QTest.qWait(20)
        self.assertEqual(splitter.sizes()[0], moved)
        self.assertEqual(doc["layer_rule"][0]["match"]["namespace"], namespace)
        editor.resize(1000, 600)
        QTest.qWait(20)
        self.assertGreater(splitter.sizes()[0], 350)

    def test_all_entry_editor_pages_have_resizable_panes(self):
        cases = (
            ("window_rule", "aot", WINDOW_RULE_GROUPS, "[[window_rule]]"),
            ("layer_rule", "aot", [("Layer rule", LAYER_RULE)], "[[layer_rule]]"),
            ("workspace", "aot", WORKSPACE_RULE_GROUPS, "[[workspace]]"),
            ("scratchpad", "aot", [("Scratchpad", SCRATCHPAD)], "[[scratchpad]]"),
            ("input.device", "aot", [("Device override", INPUT_DEVICE)], "[[input.device]]"),
            ("security_context_rule", "aot", [("Security rule", SECURITY_RULE)], "[[security_context_rule]]"),
            ("output", "map", OUTPUT_GROUPS, "Outputs (connector or monitor)"),
        )
        for path, mode, groups, title in cases:
            with self.subTest(page=title):
                editor = EntryEditor(tomlkit.document(), path, mode, groups, title)
                editor.resize(900, 600)
                editor.show()
                QTest.qWait(20)
                before = editor.splitter.sizes()
                editor.splitter.moveSplitter(500, 1)
                self.assertGreater(editor.splitter.sizes()[0], before[0] + 100)
                self.assertGreater(editor.splitter.sizes()[1], 0)
                editor.close()
                editor.deleteLater()
                QTest.qWait(5)

    def test_selected_entry_and_page_visibility_preserve_adjusted_split(self):
        doc = tomlkit.parse(
            '[[layer_rule]]\nmatch.namespace = "first"\n'
            '[[layer_rule]]\nmatch.namespace = "second"\n'
        )
        editor = EntryEditor(doc, "layer_rule", "aot", [("Layer rule", LAYER_RULE)], "[[layer_rule]]", False)
        self.addCleanup(self.cleanup_widget, editor)
        editor.resize(900, 600)
        editor.show()
        QTest.qWait(30)
        editor.splitter.moveSplitter(500, 1)
        adjusted = editor.splitter.sizes()

        editor.list.setCurrentRow(1)
        QTest.qWait(20)
        self.assertEqual(editor.cur, 1)
        self.assertEqual(editor.splitter.sizes(), adjusted)
        editor.hide()
        editor.show()
        QTest.qWait(20)
        self.assertEqual(editor.splitter.sizes(), adjusted)
        self.assertEqual(doc["layer_rule"][0]["match"]["namespace"], "first")
        self.assertEqual(doc["layer_rule"][1]["match"]["namespace"], "second")

    def test_effect_preset_and_pool_panes_are_resizable(self):
        page = EffectsPage(tomlkit.document())
        self.addCleanup(self.cleanup_widget, page)
        page.resize(900, 600)
        page.show()
        for index, editor in enumerate((page.presets, page.pools)):
            with self.subTest(tab=index):
                page.tabs.setCurrentIndex(index)
                QTest.qWait(20)
                before = editor.splitter.sizes()
                editor.splitter.moveSplitter(500, 1)
                self.assertGreater(editor.splitter.sizes()[0], before[0] + 100)
                self.assertGreater(editor.splitter.sizes()[1], 0)


if __name__ == "__main__":
    unittest.main()

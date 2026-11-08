import unittest

from PySide6.QtCore import QPoint, Qt
from PySide6.QtGui import QColor, QPalette
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication

from umbriel_config_gui.common import MISSING
from umbriel_config_gui.field_defs import F
from umbriel_config_gui.settings import FieldWidget
from umbriel_config_gui.widgets import KdeColorControl, SwitchCheckBox, TriStateControl


class SettingsSwitchTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def test_clicks_across_switch_toggle_in_both_directions(self):
        switch = SwitchCheckBox()
        switch.resize(switch.sizeHint())
        switch.show()
        self.addCleanup(switch.close)
        self.app.processEvents()

        for x in (4, 12, 22, 32, 38):
            with self.subTest(x=x):
                switch.setChecked(False)
                QTest.mouseClick(switch, Qt.MouseButton.LeftButton, pos=QPoint(x, 13))
                self.assertTrue(switch.isChecked())
                QTest.mouseClick(switch, Qt.MouseButton.LeftButton, pos=QPoint(x, 13))
                self.assertFalse(switch.isChecked())

    def test_release_outside_and_disabled_switch_do_not_toggle(self):
        switch = SwitchCheckBox()
        switch.resize(switch.sizeHint())
        switch.show()
        self.addCleanup(switch.close)
        self.app.processEvents()

        QTest.mousePress(switch, Qt.MouseButton.LeftButton, pos=QPoint(38, 13))
        QTest.mouseRelease(switch, Qt.MouseButton.LeftButton, pos=QPoint(45, 13))
        self.assertFalse(switch.isChecked())
        switch.setEnabled(False)
        QTest.mouseClick(switch, Qt.MouseButton.LeftButton, pos=QPoint(38, 13))
        self.assertFalse(switch.isChecked())

    def test_optional_field_switch_enables_and_disables_editor(self):
        widget = FieldWidget(F("Value", "value", "int", 1, None, True), MISSING)
        widget.show()
        self.addCleanup(widget.close)
        self.app.processEvents()

        switch = widget.check
        self.assertFalse(widget.w.isEnabled())
        QTest.mouseClick(switch, Qt.MouseButton.LeftButton, pos=QPoint(38, 13))
        self.assertTrue(widget.w.isEnabled())
        QTest.keyClick(switch, Qt.Key.Key_Space)
        self.assertFalse(widget.w.isEnabled())

    def test_selected_segments_round_only_the_outer_corners(self):
        for control_type in (TriStateControl, KdeColorControl):
            control = control_type()
            palette = QPalette(control.palette())
            palette.setColor(QPalette.ColorRole.Button, QColor("#202020"))
            palette.setColor(QPalette.ColorRole.Highlight, QColor("#00ff00"))
            control.setPalette(palette)
            control.show()
            self.addCleanup(control.close)
            self.app.processEvents()

            for index in range(3):
                with self.subTest(control=control_type.__name__, index=index):
                    control.setCurrentIndex(index)
                    image = control.grab().toImage()
                    left = 3 + 78 * index
                    for y in (4, 34):
                        self.assertEqual(image.pixelColor(left + 39, y).name(), "#00ff00")
                        for offset, rounded in ((1, index == 0), (76, index == 2)):
                            color = image.pixelColor(left + offset, y).name()
                            if rounded:
                                self.assertNotEqual(color, "#00ff00")
                            else:
                                self.assertEqual(color, "#00ff00")
                    for x in (left - 3, left + 80):
                        if 0 <= x < image.width():
                            self.assertNotEqual(image.pixelColor(x, 19).name(), "#00ff00")


if __name__ == "__main__":
    unittest.main()

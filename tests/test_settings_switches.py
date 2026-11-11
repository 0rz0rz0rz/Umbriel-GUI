import unittest

from PySide6.QtCore import QPoint, Qt
from PySide6.QtGui import QColor, QPalette
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication

from umbriel_config_gui.common import MISSING
from umbriel_config_gui.field_defs import F
from umbriel_config_gui.field_widget import FieldWidget
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

        for x in (4, 10, 17, 25, 30):
            with self.subTest(x=x):
                switch.setChecked(False)
                QTest.mouseClick(switch, Qt.MouseButton.LeftButton, pos=QPoint(x, 11))
                self.assertTrue(switch.isChecked())
                QTest.mouseClick(switch, Qt.MouseButton.LeftButton, pos=QPoint(x, 11))
                self.assertFalse(switch.isChecked())

    def test_release_outside_and_disabled_switch_do_not_toggle(self):
        switch = SwitchCheckBox()
        switch.resize(switch.sizeHint())
        switch.show()
        self.addCleanup(switch.close)
        self.app.processEvents()

        QTest.mousePress(switch, Qt.MouseButton.LeftButton, pos=QPoint(30, 11))
        QTest.mouseRelease(switch, Qt.MouseButton.LeftButton, pos=QPoint(35, 11))
        self.assertFalse(switch.isChecked())
        switch.setEnabled(False)
        QTest.mouseClick(switch, Qt.MouseButton.LeftButton, pos=QPoint(30, 11))
        self.assertFalse(switch.isChecked())

    def test_optional_field_switch_enables_and_disables_editor(self):
        widget = FieldWidget(F("Value", "value", "int", 1, None, True), MISSING)
        widget.show()
        self.addCleanup(widget.close)
        self.app.processEvents()

        switch = widget.check
        self.assertFalse(widget.w.isEnabled())
        QTest.mouseClick(switch, Qt.MouseButton.LeftButton, pos=QPoint(30, 11))
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
                    segment = (control.width() - 6) // 3
                    left = 3 + segment * index
                    for y in (4, control.height() - 6):
                        self.assertEqual(image.pixelColor(left + segment // 2, y).name(), "#00ff00")
                        for offset, rounded in ((1, index == 0), (segment - 2, index == 2)):
                            color = image.pixelColor(left + offset, y).name()
                            if rounded:
                                self.assertNotEqual(color, "#00ff00")
                            else:
                                self.assertEqual(color, "#00ff00")
                    for x in (left - 3, left + segment + 2):
                        if 0 <= x < image.width():
                            self.assertNotEqual(image.pixelColor(x, control.height() // 2).name(), "#00ff00")


if __name__ == "__main__":
    unittest.main()

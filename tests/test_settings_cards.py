import unittest

from PySide6.QtCore import QPoint, Qt
from PySide6.QtGui import QColor, QPalette
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QLabel, QLineEdit, QVBoxLayout, QWidget

from umbriel_config_gui.common import apply_interaction_styles
from umbriel_config_gui.settings import CollapsibleGroup


class SettingsCardTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def test_corners_remain_rounded_when_collapsed_and_expanded(self):
        original_palette = self.app.palette()
        self.addCleanup(self.app.setPalette, original_palette)
        palette = QPalette(original_palette)
        palette.setColor(QPalette.ColorRole.Window, QColor("#202020"))
        palette.setColor(QPalette.ColorRole.Midlight, QColor("#ffffff"))
        palette.setColor(QPalette.ColorRole.Highlight, QColor("#00ff00"))
        self.app.setPalette(palette)
        parent = QWidget()
        layout = QVBoxLayout(parent)
        card = CollapsibleGroup("Appearance", 0)
        card.form.addRow(QLabel("Example setting"))
        layout.addWidget(card, 0, Qt.AlignmentFlag.AlignTop)
        layout.addStretch()
        parent.resize(400, 200)
        parent.show()
        self.addCleanup(parent.close)

        for expanded in (False, True, False):
            card.setExpanded(expanded)
            QTest.qWait(20)
            image = card.grab().toImage()
            width, height = image.width(), image.height()
            self.assertEqual(card.property("cardCollapsed"), not expanded)
            self.assertEqual(card.body.isVisible(), expanded)
            self.assertLessEqual(card.header_background.geometry().left(), 3)
            self.assertGreaterEqual(card.header_background.geometry().right(), width - 4)
            for x, y in (
                (0, 0), (width - 1, 0), (0, height - 1), (width - 1, height - 1)
            ):
                self.assertLess(image.pixelColor(x, y).lightness(), 60)
            for hovered in (False, True):
                card._set_card_hovered(hovered)
                image = card.grab().toImage()
                for x, y in (
                    (width // 2, 0), (width // 2, 1),
                    (0, height // 2), (1, height // 2),
                ):
                    self.assertEqual(image.pixelColor(x, y).name(), "#ffffff")
                self.assertLess(image.pixelColor(0, 0).lightness(), 60)
                header_point = card.header_background.geometry().center()
                self.assertEqual(image.pixelColor(header_point).name(), "#ffffff" if hovered else "#202020")
                if expanded:
                    self.assertEqual(
                        image.pixelColor(width // 2, height - 8).name(),
                        "#ffffff" if hovered else "#202020",
                    )
            card._set_card_hovered(False)

    def test_hovered_line_edit_has_rounded_highlight(self):
        original_palette = self.app.palette()
        original_style = self.app.styleSheet()
        self.addCleanup(self.app.setPalette, original_palette)
        self.addCleanup(self.app.setStyleSheet, original_style)
        palette = QPalette(original_palette)
        palette.setColor(QPalette.ColorRole.Window, QColor("#202020"))
        palette.setColor(QPalette.ColorRole.Base, QColor("#101010"))
        palette.setColor(QPalette.ColorRole.Highlight, QColor("#00ff00"))
        self.app.setPalette(palette)
        apply_interaction_styles(self.app)
        parent = QWidget()
        layout = QVBoxLayout(parent)
        field = QLineEdit("2560x1440@165")
        layout.addWidget(field)
        parent.resize(240, 80)
        parent.show()
        self.addCleanup(parent.close)
        self.app.processEvents()
        QTest.mouseMove(field, QPoint(field.width() // 2, field.height() // 2))
        self.app.processEvents()

        image = field.grab().toImage()
        self.assertEqual(image.pixelColor(image.width() // 2, 0).name(), "#00ff00")
        self.assertNotEqual(image.pixelColor(0, 0).name(), "#00ff00")
        self.assertNotEqual(image.pixelColor(image.width() - 1, 0).name(), "#00ff00")

    def test_hovering_header_and_arrow_highlights_and_clears(self):
        parent = QWidget()
        layout = QVBoxLayout(parent)
        card = CollapsibleGroup("Blur", 0)
        layout.addWidget(card)
        layout.addStretch()
        parent.resize(400, 200)
        parent.show()
        self.addCleanup(parent.close)
        self.app.processEvents()

        header = card.header_background
        arrow = header.layout().itemAt(1).widget()
        for target, position in (
            (header, QPoint(3, header.height() // 2)),
            (card.header, card.header.rect().center()),
            (arrow, arrow.rect().center()),
        ):
            QTest.mouseMove(target, position)
            self.app.processEvents()
            self.assertTrue(card.property("cardHovered"))
        QTest.mouseMove(parent, QPoint(parent.width() - 1, parent.height() - 1))
        self.app.processEvents()
        self.assertFalse(card.property("cardHovered"))


if __name__ == "__main__":
    unittest.main()

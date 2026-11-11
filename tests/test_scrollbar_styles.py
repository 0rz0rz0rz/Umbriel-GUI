import unittest

from PySide6.QtCore import QPoint, Qt
from PySide6.QtGui import QColor, QPalette
from PySide6.QtTest import QTest
from PySide6.QtWidgets import (
    QApplication, QListWidget, QPlainTextEdit, QScrollArea, QScrollBar, QTableWidget,
    QTreeWidget, QTreeWidgetItem, QWidget,
)

from umbriel_config_gui.interaction_styles import apply_interaction_styles
from umbriel_config_gui.tables import tidy_table


class ScrollbarStyleTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        stylesheet = self.app.styleSheet()
        self.addCleanup(self.app.setStyleSheet, stylesheet)
        apply_interaction_styles(self.app)

    def test_vertical_scrollbars_in_all_widget_types(self):
        scroll = QScrollArea()
        content = QWidget()
        content.setFixedSize(600, 1000)
        scroll.setWidget(content)
        listing = QListWidget()
        listing.addItems([str(i) for i in range(100)])
        tree = QTreeWidget()
        tree.setHeaderLabels(["Items"])
        tree.addTopLevelItems([QTreeWidgetItem([str(i)]) for i in range(100)])
        table = QTableWidget(100, 4)
        tidy_table(table)
        text = QPlainTextEdit("\n".join(str(i) for i in range(100)))
        standalone = QScrollBar(Qt.Orientation.Vertical)
        standalone.setRange(0, 100)
        for widget in (scroll, listing, tree, table, text, standalone):
            self.addCleanup(widget.close)
            widget.resize(280, 180)
            widget.show()
        self.app.processEvents()
        for widget in (scroll, listing, tree, table, text, standalone):
            with self.subTest(widget=type(widget).__name__):
                bar = widget if widget is standalone else widget.verticalScrollBar()
                self.assertTrue(bar.isVisible())
                self.assertGreater(bar.maximum(), 0)
                self.assert_edges_clear(bar)
                bar.setValue(bar.maximum())
                self.assertEqual(bar.value(), bar.maximum())

    def test_scrollbar_uses_current_palette_for_light_and_dark_themes(self):
        original_palette = self.app.palette()
        self.addCleanup(self.app.setPalette, original_palette)
        for background, thumb in (("#202020", "#777777"), ("#eeeeee", "#666666")):
            with self.subTest(background=background):
                self.app.setStyleSheet("")
                palette = QPalette(original_palette)
                palette.setColor(QPalette.ColorRole.Window, QColor(background))
                palette.setColor(QPalette.ColorRole.Light, QColor(thumb))
                self.app.setPalette(palette)
                apply_interaction_styles(self.app)
                bar = QScrollBar(Qt.Orientation.Vertical)
                self.addCleanup(bar.close)
                bar.setRange(0, 100)
                bar.resize(20, 200)
                bar.show()
                QTest.mouseMove(bar, QPoint(0, bar.height() - 1))
                self.app.processEvents()
                self.assert_edges_clear(bar)
                image = bar.grab().toImage()
                self.assertTrue(any(image.pixelColor(image.width() // 2, y).name() == thumb
                                    for y in range(image.height())))
                bar.close()

    def assert_edges_clear(self, bar):
        image = bar.grab().toImage()
        background = bar.palette().color(QPalette.ColorRole.Window).name()
        for y in range(image.height()):
            self.assertEqual(image.pixelColor(0, y).name(), background)
            self.assertEqual(image.pixelColor(image.width() - 1, y).name(), background)
        self.assertTrue(any(image.pixelColor(image.width() // 2, y).name() != background
                            for y in range(image.height())))

if __name__ == "__main__":
    unittest.main()

import unittest

from PySide6.QtGui import QColor, QPalette
from PySide6.QtWidgets import QApplication, QAbstractItemView, QTableWidget

from umbriel_config_gui.tables import tidy_table


class TableStyleTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def test_tidy_table_uses_palette_aware_selection_and_headers(self):
        table = QTableWidget()
        self.addCleanup(table.close)
        palette = QPalette(table.palette())
        palette.setColor(QPalette.ColorRole.Base, QColor("#101010"))
        palette.setColor(QPalette.ColorRole.Mid, QColor("#303030"))
        palette.setColor(QPalette.ColorRole.Highlight, QColor("#00AAFF"))
        table.setPalette(palette)

        tidy_table(table)

        self.assertFalse(table.alternatingRowColors())
        self.assertFalse(table.showGrid())
        self.assertEqual(
            table.selectionBehavior(),
            QAbstractItemView.SelectionBehavior.SelectRows,
        )
        self.assertEqual(
            table.selectionMode(),
            QAbstractItemView.SelectionMode.ExtendedSelection,
        )
        self.assertIn("background: #101010", table.styleSheet())
        self.assertIn("border: 1px solid #303030", table.styleSheet())
        self.assertIn("border: 2px solid #00aaff", table.styleSheet())


if __name__ == "__main__":
    unittest.main()

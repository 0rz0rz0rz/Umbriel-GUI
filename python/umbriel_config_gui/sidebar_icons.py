"""Palette-aware, monochrome pictograms for the settings navigation."""

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QIcon, QPainter, QPalette, QPen, QPixmap, QPolygonF


_PICTOGRAMS = {
    "folder": (
        ("poly", 2, 5, 6, 5, 7.5, 7, 14, 7, 14, 13, 2, 13, 2, 5),
    ),
    "apps": (
        ("rect", 2, 2, 4, 4), ("rect", 9, 2, 4, 4),
        ("rect", 2, 9, 4, 4), ("rect", 9, 9, 4, 4),
    ),
    "sliders": (
        ("line", 2, 4, 14, 4), ("line", 2, 8, 14, 8), ("line", 2, 12, 14, 12),
        ("ellipse", 5, 2.5, 3, 3), ("ellipse", 10, 6.5, 3, 3),
        ("ellipse", 4, 10.5, 3, 3),
    ),
    "appearance": (
        ("rect", 2, 2, 12, 12), ("line", 4, 11, 11, 4),
        ("line", 4, 4, 6, 4), ("line", 5, 3, 5, 5),
        ("line", 10, 10, 13, 10), ("line", 11.5, 8.5, 11.5, 11.5),
    ),
    "colors": (
        ("ellipse", 2, 2, 12, 12), ("ellipse", 4.5, 4.5, 1, 1),
        ("ellipse", 8, 3.5, 1, 1), ("ellipse", 10.5, 6, 1, 1),
        ("ellipse", 6, 9, 2, 2),
    ),
    "motion": (
        ("ellipse", 2, 2, 12, 12), ("poly", 8, 4, 8, 8, 11, 10),
    ),
    "effects": (
        ("poly", 8, 1.5, 9.5, 6, 14, 8, 9.5, 9.5, 8, 14.5, 6.5, 9.5, 2, 8, 6.5, 6, 8, 1.5),
    ),
    "mouse": (
        ("round", 4.5, 1.5, 7, 13, 3.5, 3.5),
        ("line", 8, 2, 8, 6),
    ),
    "grid": (
        ("rect", 2, 2, 12, 12), ("line", 8, 2, 8, 14), ("line", 2, 8, 14, 8),
    ),
    "keyboard": (
        ("round", 1.5, 4, 13, 8, 1.5, 1.5),
        ("line", 3.5, 6.5, 4.5, 6.5), ("line", 7, 6.5, 8, 6.5),
        ("line", 10.5, 6.5, 11.5, 6.5), ("line", 5, 9.5, 11, 9.5),
    ),
    "window": (
        ("rect", 2, 3, 12, 10), ("line", 2, 6, 14, 6),
    ),
    "layers": (
        ("poly", 8, 2, 14, 5, 8, 8, 2, 5, 8, 2),
        ("poly", 2, 8, 8, 11, 14, 8), ("poly", 2, 11, 8, 14, 14, 11),
    ),
    "display": (
        ("round", 2, 2.5, 12, 8.5, 1, 1), ("line", 8, 11, 8, 13.5),
        ("line", 5, 13.5, 11, 13.5),
    ),
    "terminal": (
        ("round", 2, 2, 12, 12, 1.5, 1.5), ("poly", 4.5, 5, 7, 7.5, 4.5, 10),
        ("line", 8, 10, 11.5, 10),
    ),
    "shield": (
        ("poly", 8, 1.5, 13.5, 4, 13, 9, 11, 12, 8, 14.5, 5, 12, 3, 9, 2.5, 4, 8, 1.5),
        ("poly", 5.5, 8, 7.2, 9.5, 10.5, 6),
    ),
}

_PAGE_PICTOGRAMS = {
    "User folders": "folder", "Default apps": "apps", "General": "sliders",
    "Appearance": "appearance", "Colors": "colors", "Animation": "motion",
    "Animation curves": "motion", "Effects": "effects", "Input": "mouse",
    "Layout": "grid", "Workspaces": "grid", "Keybinds": "keyboard",
    "Window rules": "window", "Layer rules": "layers", "Workspace rules": "grid",
    "Outputs": "display", "Scratchpads": "terminal", "Input devices": "mouse",
    "Security rules": "shield", "Environment": "terminal",
}


def sidebar_icon(page_name, palette):
    """Draw a pictogram in the current text and selection colors."""
    pictogram = _PICTOGRAMS[_PAGE_PICTOGRAMS.get(page_name, "sliders")]
    icon = QIcon()
    for mode, color in (
        (QIcon.Mode.Normal, palette.color(QPalette.ColorRole.Text)),
        (QIcon.Mode.Selected, palette.color(QPalette.ColorRole.HighlightedText)),
        (QIcon.Mode.Disabled, palette.color(QPalette.ColorGroup.Disabled, QPalette.ColorRole.Text)),
    ):
        pixmap = QPixmap(32, 32)
        pixmap.fill(Qt.GlobalColor.transparent)
        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.scale(2, 2)
        pen = QPen(color, 1.2, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin)
        painter.setPen(pen)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        for operation, *coordinates in pictogram:
            if operation == "line":
                painter.drawLine(QPointF(*coordinates[:2]), QPointF(*coordinates[2:]))
            elif operation == "poly":
                points = QPolygonF([
                    QPointF(coordinates[i], coordinates[i + 1])
                    for i in range(0, len(coordinates), 2)
                ])
                painter.drawPolyline(points)
            elif operation == "rect":
                painter.drawRect(QRectF(*coordinates))
            elif operation == "ellipse":
                painter.drawEllipse(QRectF(*coordinates))
            elif operation == "round":
                painter.drawRoundedRect(QRectF(*coordinates[:4]), *coordinates[4:])
        painter.end()
        icon.addPixmap(pixmap, mode)
    return icon

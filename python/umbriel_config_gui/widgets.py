"""Reusable form widgets: switches, tri-state control, labels, sliders, flow layout."""


from .common import (
    contrast_ratio,
    mix_colors,
    QEvent,
    QCheckBox,
    QFont,
    QHBoxLayout,
    QLabel,
    QLayout,
    QPalette,
    QPainter,
    QPainterPath,
    QRect,
    QSize,
    QSizePolicy,
    QPushButton,
    QSlider,
    QVBoxLayout,
    QWidget,
    Qt,
    Signal,
)


class SwitchCheckBox(QCheckBox):
    """A native checkbox with a compact switch-shaped indicator."""

    def sizeHint(self):
        return QSize(44, 26)

    def hitButton(self, pos):
        return self.rect().contains(pos)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        x, y, width, height = 1, 2, 40, 22
        palette = self.palette()
        window = palette.color(QPalette.ColorRole.Window)
        text = palette.color(QPalette.ColorRole.WindowText)
        if not self.isEnabled():
            track = mix_colors(window, text, 0.12)
            thumb = mix_colors(window, text, 0.35)
        elif self.isChecked():
            group = QPalette.ColorGroup.Active
            track = palette.color(group, QPalette.ColorRole.Highlight)
            thumb = palette.color(group, QPalette.ColorRole.Base)
            if contrast_ratio(thumb, track) < 1.8:
                thumb = palette.color(group, QPalette.ColorRole.HighlightedText)
        else:
            track = mix_colors(window, text, 0.22)
            thumb = mix_colors(window, text, 0.7)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(track)
        painter.drawRoundedRect(x, y, width, height, height / 2, height / 2)
        thumb_x = x + (width - height if self.isChecked() else 0) + 3
        painter.setBrush(thumb)
        painter.drawEllipse(thumb_x, y + 3, height - 6, height - 6)
        if self.hasFocus():
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.setPen(palette.color(QPalette.ColorRole.Highlight))
            painter.drawRoundedRect(x - 1, y - 1, width + 2, height + 2, 12, 12)
        event.accept()


class TriStateControl(QWidget):
    """A segmented control for an optional boolean: default, on, or off."""

    LABELS = ("default", "on", "off")
    valueChanged = Signal(int)

    def __init__(self):
        super().__init__()
        self.setObjectName("triStateControl")
        self.setFixedSize(240, 40)
        self._index = 0
        self._hovered = False
        self.setMouseTracking(True)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setAccessibleName("Optional setting")
        self.setToolTip("Choose default, on, or off.")
        self.setCurrentIndex(0)

    def sizeHint(self):
        return QSize(240, 40)

    def currentIndex(self):
        """Return the selected segment index."""
        return self._index

    def setCurrentIndex(self, index):
        """Select default (0), on (1), or off (2)."""
        if not 0 <= index < len(self.LABELS):
            raise IndexError(f"Tri-state index out of range: {index}")
        if index != self._index:
            self._index = index
            self.update()
            self.valueChanged.emit(index)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        outer = self.rect().adjusted(1, 1, -1, -1)
        radius = outer.height() / 2
        palette = self.palette()
        painter.setPen(palette.color(
            QPalette.ColorRole.Highlight
            if self._hovered or self.hasFocus()
            else QPalette.ColorRole.Midlight
        ))
        painter.setBrush(palette.color(QPalette.ColorRole.Button))
        painter.drawRoundedRect(outer, radius, radius)

        track = self.rect().adjusted(3, 3, -3, -3)
        segment_width = track.width() / len(self.LABELS)
        selected_left = track.left() + segment_width * self._index
        selected = QPainterPath()
        selected.addRoundedRect(
            selected_left, track.top(), segment_width, track.height(),
            track.height() / 2, track.height() / 2,
        )
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(palette.color(QPalette.ColorRole.Highlight))
        painter.drawPath(selected)

        painter.setPen(palette.color(QPalette.ColorRole.Midlight))
        for divider_index in (1, 2):
            x = round(track.left() + segment_width * divider_index)
            if self._index not in (divider_index - 1, divider_index):
                painter.drawLine(x, int(track.top() + 5), x, int(track.bottom() - 5))

        for index, label in enumerate(self.LABELS):
            left = round(track.left() + segment_width * index)
            right = round(track.left() + segment_width * (index + 1))
            text_rect = QRect(left, track.top(), right - left, track.height())
            font = QFont(self.font())
            font.setBold(index == self._index)
            painter.setFont(font)
            painter.setPen(
                palette.color(
                    QPalette.ColorRole.HighlightedText
                    if index == self._index
                    else QPalette.ColorRole.Text
                )
            )
            painter.drawText(text_rect, Qt.AlignmentFlag.AlignCenter, label)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            index = min(
                len(self.LABELS) - 1,
                max(0, int((event.position().x() - 3) / (self.width() - 6) * len(self.LABELS))),
            )
            self.setCurrentIndex(index)
            self.setFocus()
            event.accept()
            return
        super().mousePressEvent(event)

    def keyPressEvent(self, event):
        if event.key() in (Qt.Key.Key_Left, Qt.Key.Key_Up):
            self.setCurrentIndex(max(0, self._index - 1))
        elif event.key() in (Qt.Key.Key_Right, Qt.Key.Key_Down):
            self.setCurrentIndex(min(len(self.LABELS) - 1, self._index + 1))
        elif event.key() == Qt.Key.Key_Home:
            self.setCurrentIndex(0)
        elif event.key() == Qt.Key.Key_End:
            self.setCurrentIndex(len(self.LABELS) - 1)
        else:
            super().keyPressEvent(event)
            return
        event.accept()

    def enterEvent(self, event):
        self._hovered = True
        self.update()
        super().enterEvent(event)

    def leaveEvent(self, event):
        self._hovered = False
        self.update()
        super().leaveEvent(event)


class WrappedLabel(QLabel):
    """Keep descriptions on one line when possible and wrap them when space is tight."""

    def __init__(self, text):
        super().__init__(text)
        font = QFont(self.font())
        font.setPointSize(9)
        self.setFont(font)
        self.setWordWrap(True)
        policy = QSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred
        )
        policy.setHeightForWidth(True)
        self.setSizePolicy(policy)
        self.setToolTip(text)

    def sizeHint(self):
        text_width = self.fontMetrics().horizontalAdvance(self.text())
        return QSize(max(200, text_width), self.fontMetrics().height())

    def minimumSizeHint(self):
        return QSize(0, self.fontMetrics().height())


class SettingLabel(QWidget):
    """Lay out a setting title and description with correct wrapped-row sizing."""

    def __init__(self, title, description):
        super().__init__()
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(2)
        layout.addWidget(title)
        layout.addWidget(description)
        policy = QSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred
        )
        policy.setHeightForWidth(True)
        self.setSizePolicy(policy)

    def heightForWidth(self, width):
        return self.layout().heightForWidth(width)

    def sizeHint(self):
        return self.layout().sizeHint()

    def minimumSizeHint(self):
        return QSize(0, self.layout().minimumSize().height())


class SettingRow(QWidget):
    """Keep the editor beside its label while allowing only the label to wrap."""

    def __init__(self, label, editor):
        super().__init__()
        self.setMinimumWidth(0)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(16)
        layout.addWidget(label, 1)
        layout.addWidget(editor)
        policy = QSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred
        )
        policy.setHeightForWidth(True)
        self.setSizePolicy(policy)

    def heightForWidth(self, width):
        return self.layout().heightForWidth(width)

    def minimumSizeHint(self):
        return QSize(0, self.layout().minimumSize().height())


class OverviewButton(QPushButton):
    """Keep the overview card tall enough to contain its laid-out labels."""

    def sizeHint(self):
        layout = self.layout()
        if layout is None:
            return super().sizeHint()
        hint = layout.sizeHint()
        return QSize(max(hint.width(), super().sizeHint().width()), hint.height() + 2)


class SettingSlider(QSlider):
    """A compact slider that does not change settings while scrolling a page."""

    HANDLE_SIZE = 18

    def __init__(self):
        super().__init__(Qt.Orientation.Horizontal)
        self.setMinimumWidth(150)
        self.setMaximumWidth(180)
        # Tall enough for the whole handle (and its hover outline) so it is never clipped.
        self.setFixedHeight(self.HANDLE_SIZE + 10)
        self._apply_style()

    def _apply_style(self):
        palette = self.palette()
        window = palette.color(QPalette.ColorRole.Window)
        text = palette.color(QPalette.ColorRole.WindowText)
        highlight = palette.color(QPalette.ColorRole.Highlight)
        groove = mix_colors(window, text, 0.28).name()
        off = mix_colors(window, text, 0.45).name()
        ring = highlight.darker(135).name()
        inset = (self.HANDLE_SIZE - 6) // 2
        self.setStyleSheet(
            f"QSlider::groove:horizontal {{ height: 6px; border-radius: 3px; background: {groove}; }}"
            f"QSlider::sub-page:horizontal {{ background: {highlight.name()}; border-radius: 3px; }}"
            f"QSlider::handle:horizontal {{ background: {highlight.name()};"
            f" border: 2px solid {ring}; width: {self.HANDLE_SIZE - 4}px;"
            f" height: {self.HANDLE_SIZE - 4}px; margin: -{inset}px 0; border-radius: {self.HANDLE_SIZE // 2}px; }}"
            f"QSlider::handle:horizontal:hover {{ border-color: {text.name()}; }}"
            f"QSlider::sub-page:horizontal:disabled {{ background: {groove}; }}"
            f"QSlider::handle:horizontal:disabled {{ background: {off}; border-color: {groove}; }}"
        )

    def changeEvent(self, event):
        super().changeEvent(event)
        if event.type() == QEvent.Type.PaletteChange and not getattr(self, "_styling", False):
            self._styling = True
            try:
                self._apply_style()
            finally:
                self._styling = False

    def wheelEvent(self, event):
        event.ignore()


class FlowLayout(QLayout):
    """Lay out section buttons in rows that wrap to the available page width."""

    def __init__(self, parent=None, horizontal_spacing=6, vertical_spacing=6):
        super().__init__(parent)
        self._items = []
        self._horizontal_spacing = horizontal_spacing
        self._vertical_spacing = vertical_spacing
        self.setContentsMargins(0, 0, 0, 0)

    def addItem(self, item):
        self._items.append(item)

    def count(self):
        return len(self._items)

    def itemAt(self, index):
        return self._items[index] if 0 <= index < len(self._items) else None

    def takeAt(self, index):
        return self._items.pop(index) if 0 <= index < len(self._items) else None

    def expandingDirections(self):
        return Qt.Orientations()

    def hasHeightForWidth(self):
        return True

    def heightForWidth(self, width):
        return self._do_layout(QRect(0, 0, width, 0), True)

    def setGeometry(self, rect):
        super().setGeometry(rect)
        self._do_layout(rect, False)

    def sizeHint(self):
        return self.minimumSize()

    def minimumSize(self):
        size = QSize()
        for item in self._items:
            size = size.expandedTo(item.minimumSize())
        margins = self.contentsMargins()
        return size + QSize(
            margins.left() + margins.right(),
            margins.top() + margins.bottom(),
        )

    def _do_layout(self, rect, test_only):
        margins = self.contentsMargins()
        left = rect.x() + margins.left()
        right = rect.x() + rect.width() - margins.right()
        x = left
        y = rect.y() + margins.top()
        row_height = 0

        for item in self._items:
            size = item.sizeHint()
            next_x = x + size.width() + self._horizontal_spacing
            if row_height and next_x - self._horizontal_spacing > right:
                x = left
                y += row_height + self._vertical_spacing
                next_x = x + size.width() + self._horizontal_spacing
                row_height = 0
            if not test_only:
                item.setGeometry(QRect(x, y, size.width(), size.height()))
            x = next_x
            row_height = max(row_height, size.height())

        return y + row_height + margins.bottom() - rect.y()

"""List and detail presentation for the keybind editor."""

from PySide6.QtCore import QItemSelectionModel, QPointF, QRect, Qt, QTimer
from PySide6.QtGui import QIcon, QPainter, QPalette, QPen, QPixmap
from PySide6.QtWidgets import (
    QAbstractItemView, QCheckBox, QCompleter, QLineEdit, QTreeWidget,
    QTreeView, QTreeWidgetItem, QScrollArea, QSizePolicy, QSpinBox, QSplitter,
    QStyle, QStyledItemDelegate, QStyleOptionViewItem, QVBoxLayout, QWidget,
)

from .actions import ACTION_CATEGORIES, ACTION_INFO
from .common import WheelSafeComboBox
from .keybinds import BIND_BOOL_OPTIONS, KeybindEditor as TableKeybindEditor
from .settings_layout import CollapsibleGroup


def _shorten_description(description):
    description = description.split(" (", 1)[0].split(". ", 1)[0]
    if len(description) > 60:
        return description[:57].rsplit(" ", 1)[0] + "..."
    return description


def short_action_description(action):
    """Describe known actions while keeping custom commands identifiable."""
    action = action.strip()
    if not action:
        return "(No action)"
    for _, actions in ACTION_CATEGORIES:
        for template, description in actions:
            if action == template:
                return _shorten_description(description)
    head, _, argument = action.partition(" ")
    if head == "spawn" and argument:
        return f"Run {argument}" if len(argument) <= 48 else f"Run {argument[:45]}..."
    if head in ACTION_INFO:
        return _shorten_description(ACTION_INFO[head][1])
    return action if len(action) <= 52 else action[:49] + "..."


def locked_key_icon(palette, locked=True):
    pixmap = QPixmap(16, 16)
    pixmap.fill(Qt.GlobalColor.transparent)
    if not locked:
        return QIcon(pixmap)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    pen = QPen(palette.color(QPalette.ColorRole.Text), 1.6)
    pen.setCapStyle(Qt.PenCapStyle.RoundCap)
    painter.setPen(pen)
    painter.drawEllipse(QPointF(5, 5), 3, 3)
    painter.drawLine(QPointF(7.2, 7.2), QPointF(13.5, 13.5))
    painter.drawLine(QPointF(11, 11), QPointF(12.5, 9.5))
    painter.drawLine(QPointF(13, 13), QPointF(14.5, 11.5))
    painter.end()
    return QIcon(pixmap)


class KeybindItemDelegate(QStyledItemDelegate):
    """Draw shortcut and description in consistent, independently elided columns."""

    def __init__(self, shortcut_width, parent):
        super().__init__(parent)
        self.shortcut_width = shortcut_width

    def text_rects(self, option):
        rect = option.rect
        start = rect.left() + 26
        available = max(0, rect.right() - start + 1)
        shortcut_width = min(self.shortcut_width, int(available * 0.45))
        shortcut = QRect(start, rect.top(), shortcut_width, rect.height())
        description = QRect(start + shortcut_width + 12, rect.top(),
                            max(0, available - shortcut_width - 12), rect.height())
        return shortcut, description

    def paint(self, painter, option, index):
        styled = QStyleOptionViewItem(option)
        self.initStyleOption(styled, index)
        styled.text = ""
        widget = styled.widget
        style = widget.style() if widget else self.parent().style()
        style.drawControl(QStyle.ControlElement.CE_ItemViewItem, styled, painter, widget)
        shortcut, description = self.text_rects(styled)
        painter.save()
        painter.setClipRect(styled.rect)
        painter.setFont(styled.font)
        role = (QPalette.ColorRole.HighlightedText
                if styled.state & QStyle.StateFlag.State_Selected else QPalette.ColorRole.Text)
        painter.setPen(styled.palette.color(role))
        for rect, text in ((shortcut, index.data(Qt.ItemDataRole.UserRole + 1)),
                           (description, index.data(Qt.ItemDataRole.UserRole + 2))):
            painter.drawText(rect, Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
                             styled.fontMetrics.elidedText(text, Qt.TextElideMode.ElideRight,
                                                           rect.width()))
        painter.restore()


class KeybindEditor(TableKeybindEditor):
    """Present the existing keybind editing model as a list and detail card."""

    def __init__(self, doc):
        super().__init__(doc)
        layout = self.layout()
        layout.removeWidget(self.t)
        self.t.hide()
        layout.removeWidget(self.desc)
        size_policy = self.lock_all_btn.sizePolicy()
        size_policy.setVerticalPolicy(QSizePolicy.Policy.Expanding)
        self.lock_all_btn.setSizePolicy(size_policy)
        original_lock_label = self.lock_all_btn.text()
        self.lock_all_btn.setText("Unlock all")
        self.lock_all_btn.setMinimumWidth(max(
            self.lock_all_btn.sizeHint().width(),
            self.lock_all_btn.fontMetrics().horizontalAdvance("Unlock all") + 20,
        ))
        self.lock_all_btn.setText(original_lock_label)

        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.setHandleWidth(12)
        splitter.setStyleSheet("QSplitter::handle { background: palette(window); }")
        self.splitter = splitter
        layout.insertWidget(1, splitter, 1)
        list_panel = QWidget()
        list_layout = QVBoxLayout(list_panel)
        list_layout.setContentsMargins(0, 0, 0, 0)
        self.search = QLineEdit()
        self.search.setPlaceholderText("Search keybinds...")
        self.search.setAccessibleName("Search keybinds")
        self.search.setProperty("dirtyTrackingConnected", True)
        list_layout.addWidget(self.search)
        self.bind_list = QTreeWidget()
        self.bind_list.setHeaderHidden(True)
        self.bind_list.setAccessibleName("Keybinds")
        self.bind_list.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.bind_list.setProperty("dirtyTrackingConnected", True)
        self.bind_list.hide()
        group_scroll = QScrollArea()
        group_scroll.setWidgetResizable(True)
        group_scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        group_contents = QWidget()
        self.group_layout = QVBoxLayout(group_contents)
        self.group_layout.setContentsMargins(0, 0, 0, 0)
        self.group_layout.setSpacing(10)
        self.group_layout.addStretch()
        group_scroll.setWidget(group_contents)
        list_layout.addWidget(group_scroll)
        self.group_cards = {}
        splitter.addWidget(list_panel)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        details = QWidget()
        details_layout = QVBoxLayout(details)
        details_layout.setContentsMargins(0, 0, 0, 0)
        self.detail_card = CollapsibleGroup(
            "Selected keybind", 1, description="Edit the selected shortcut and action."
        )
        self.detail_card.header.setProperty("dirtyTrackingConnected", True)
        form = self.detail_card.form
        self.key_edit = QLineEdit()
        self.group_edit = WheelSafeComboBox()
        self.action_edit = WheelSafeComboBox()
        self.action_edit.setEditable(True)
        self.action_edit.setModel(self.model)
        completer = QCompleter(self.model, self.action_edit)
        completer.setFilterMode(Qt.MatchFlag.MatchContains)
        completer.setCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
        self.action_edit.setCompleter(completer)
        self.action_edit.activated.connect(
            lambda index: self.picked(self.action_edit, self.action_edit.itemText(index))
        )
        completer.activated.connect(
            lambda text: QTimer.singleShot(0, lambda: self.picked(self.action_edit, text))
        )
        self.option_edits = []
        form.addRow("Shortcut", self.key_edit)
        form.addRow("Group", self.group_edit)
        form.addRow("Action", self.action_edit)
        for _, label in BIND_BOOL_OPTIONS:
            combo = WheelSafeComboBox()
            combo.addItems(["-", "true", "false"])
            self.option_edits.append(combo)
            form.addRow(label, combo)
        self.cooldown_edit = QSpinBox()
        self.cooldown_edit.setRange(0, 10000)
        self.cooldown_edit.setSpecialValueText("off")
        form.addRow("Cooldown (ms)", self.cooldown_edit)
        self.submap_edit = QLineEdit()
        form.addRow("Submap after", self.submap_edit)
        self.lock_edit = QCheckBox("Prevent editing or removal")
        form.addRow("Locked", self.lock_edit)
        form.addRow(self.desc)
        details_layout.addWidget(self.detail_card)
        details_layout.addStretch(1)
        scroll.setWidget(details)
        splitter.addWidget(scroll)
        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 1)
        splitter.setSizes([10000, 10000])
        self._splitter_adjusted = False
        splitter.splitterMoved.connect(self._splitter_moved)

        self._loading_detail = False
        self._sync_pending = False
        self._collapsed_groups = set()
        self.search.textChanged.connect(self._sync_list)
        self.bind_list.currentItemChanged.connect(self._select_item)
        self.bind_list.itemSelectionChanged.connect(self._select_items)
        self.bind_list.itemExpanded.connect(self._group_expanded)
        self.bind_list.itemCollapsed.connect(self._group_collapsed)
        self.key_edit.textChanged.connect(self._write_detail)
        self.group_edit.currentIndexChanged.connect(self._write_detail)
        self.action_edit.editTextChanged.connect(self._write_detail)
        for combo in self.option_edits:
            combo.currentIndexChanged.connect(self._write_detail)
        self.cooldown_edit.valueChanged.connect(self._write_detail)
        self.submap_edit.textChanged.connect(self._write_detail)
        self.lock_edit.toggled.connect(self._write_detail)
        self.t.itemChanged.connect(self._schedule_sync)
        self.t.model().rowsInserted.connect(self._schedule_sync)
        self.t.model().rowsRemoved.connect(self._schedule_sync)
        self._sync_list()
        if self.t.rowCount():
            self._select_backing_row(0)
        else:
            self._select_row(-1)

    def _group_expanded(self, item):
        if not self.search.text().strip():
            self._collapsed_groups.discard(item.data(0, Qt.ItemDataRole.UserRole))
        card = self.group_cards.get(item.data(0, Qt.ItemDataRole.UserRole))
        if card:
            card.setExpanded(True)

    def _group_collapsed(self, item):
        if not self.search.text().strip():
            self._collapsed_groups.add(item.data(0, Qt.ItemDataRole.UserRole))
        card = self.group_cards.get(item.data(0, Qt.ItemDataRole.UserRole))
        if card:
            card.setExpanded(False)
        for index in range(item.childCount()):
            item.child(index).setSelected(False)
        current = self.bind_list.currentItem()
        if current and current.parent() == item:
            self._select_row(-1)
        self._select_items()

    def _splitter_moved(self, *_args):
        self._splitter_adjusted = True

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if hasattr(self, "splitter") and not self._splitter_adjusted:
            QTimer.singleShot(0, self._balance_splitter)

    def _balance_splitter(self):
        if not self._splitter_adjusted:
            self.splitter.setSizes([10000, 10000])

    def _select_item(self, item, _previous):
        row = item.data(0, Qt.ItemDataRole.UserRole) if item and item.parent() else -1
        self._select_row(row)

    def _select_backing_row(self, row):
        for group_index in range(self.bind_list.topLevelItemCount()):
            group = self.bind_list.topLevelItem(group_index)
            for index in range(group.childCount()):
                item = group.child(index)
                if item.data(0, Qt.ItemDataRole.UserRole) == row:
                    self.bind_list.setCurrentItem(item)
                    return

    def _schedule_sync(self, *_args):
        if not hasattr(self, "bind_list") or self._sync_pending:
            return
        self._sync_pending = True
        QTimer.singleShot(0, self._sync_list)

    def _sync_list(self, *_args, preserve_selection=True):
        self._sync_pending = False
        row = self.t.currentRow()
        selected = (
            {item.data(0, Qt.ItemDataRole.UserRole)
             for item in self.bind_list.selectedItems() if item.parent()}
            if preserve_selection else set()
        )
        for card in self.group_cards.values():
            self.group_layout.removeWidget(card)
            card.hide()
            card.deleteLater()
        self.group_cards.clear()
        self.bind_list.blockSignals(True)
        self.bind_list.clear()
        terms = self.search.text().casefold().split()
        groups = {}
        row_items = {}
        key_icon = locked_key_icon(self.palette())
        empty_icon = locked_key_icon(self.palette(), locked=False)
        shortcut_width = max(
            (self.fontMetrics().horizontalAdvance(
                self.t.item(index, 0).text().strip() or "(New shortcut)")
             for index in range(self.t.rowCount())),
            default=0,
        ) + 8
        for index in range(self.t.rowCount()):
            key = self.t.item(index, 0).text().strip() or "(New shortcut)"
            action = self.t.cellWidget(index, 2).currentText().strip()
            group = self.t.cellWidget(index, 1).currentText()
            text = f"{key}  —  {short_action_description(action)}"
            if group not in groups:
                heading = QTreeWidgetItem(self.bind_list, [group or "Ungrouped"])
                heading.setData(0, Qt.ItemDataRole.UserRole, group)
                heading.setFlags(heading.flags() & ~Qt.ItemFlag.ItemIsSelectable)
                groups[group] = heading
            item = QTreeWidgetItem(groups[group], [text])
            item.setData(0, Qt.ItemDataRole.UserRole, index)
            item.setData(0, Qt.ItemDataRole.UserRole + 1, key)
            item.setData(0, Qt.ItemDataRole.UserRole + 2, short_action_description(action))
            item.setToolTip(0, action)
            if self.t.cellWidget(index, 8).isChecked():
                item.setIcon(0, key_icon)
                item.setData(0, Qt.ItemDataRole.AccessibleDescriptionRole, "Locked")
            else:
                item.setIcon(0, empty_icon)
                item.setData(0, Qt.ItemDataRole.AccessibleDescriptionRole, "Unlocked")
            row_items[index] = item
            searchable = f"{key} {action} {group} {text}".casefold()
            item.setHidden(
                self.t.isRowHidden(index)
                or not all(term in searchable for term in terms)
            )
        for group in self.group_names:
            if group not in groups:
                heading = QTreeWidgetItem(self.bind_list, [group])
                heading.setData(0, Qt.ItemDataRole.UserRole, group)
                heading.setFlags(heading.flags() & ~Qt.ItemFlag.ItemIsSelectable)
                groups[group] = heading
        for group, heading in groups.items():
            if heading.childCount():
                hidden = all(heading.child(i).isHidden() for i in range(heading.childCount()))
            else:
                selected_group = self.group_filter.currentText()
                hidden = bool(terms) or selected_group not in ("All groups", group)
            heading.setHidden(hidden)
            heading.setExpanded(bool(terms) or group not in self._collapsed_groups)
            card = CollapsibleGroup(group or "Ungrouped", int(heading.isExpanded()))
            card.header.setProperty("dirtyTrackingConnected", True)
            card.header.toggled.connect(heading.setExpanded)
            view = QTreeView()
            view.setItemDelegate(KeybindItemDelegate(shortcut_width, view))
            view.setModel(self.bind_list.model())
            view.setSelectionModel(self.bind_list.selectionModel())
            view.setRootIndex(self.bind_list.indexFromItem(heading))
            view.setHeaderHidden(True)
            view.setRootIsDecorated(False)
            view.setItemsExpandable(False)
            view.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
            view.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
            view.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
            view.setFrameShape(QTreeView.Shape.NoFrame)
            view.setStyleSheet(
                "QTreeView { background: palette(base); border: 0px solid transparent;"
                " border-radius: 10px; padding: 4px; }"
            )
            view.setAccessibleName(f"{group or 'Ungrouped'} keybinds")
            view.setProperty("dirtyTrackingConnected", True)
            visible_count = 0
            for index in range(heading.childCount()):
                hidden = heading.child(index).isHidden()
                view.setRowHidden(index, view.rootIndex(), hidden)
                visible_count += not hidden
            row_height = max(view.sizeHintForRow(0), view.fontMetrics().height() + 8)
            view.setFixedHeight(max(1, visible_count * row_height) + 8)
            card.form.addRow(view)
            self.group_cards[group] = card
            self.group_layout.insertWidget(self.group_layout.count() - 1, card)
            card.setVisible(not heading.isHidden())
        visible = {
            index for index, item in row_items.items()
            if not item.isHidden() and item.parent().isExpanded()
        }
        if not preserve_selection:
            selected = {row}
        selected &= visible
        if row in selected:
            self.bind_list.setCurrentItem(
                row_items[row], 0, QItemSelectionModel.SelectionFlag.NoUpdate
            )
        for index in selected:
            row_items[index].setSelected(True)
        self.bind_list.blockSignals(False)
        self._select_row(row if row in selected else -1)
        self._select_items()

    def _select_items(self):
        selection = self.t.selectionModel()
        selection.clearSelection()
        for item in self.bind_list.selectedItems():
            if not item.parent():
                continue
            row = item.data(0, Qt.ItemDataRole.UserRole)
            selection.select(
                self.t.model().index(row, 0),
                QItemSelectionModel.SelectionFlag.Select | QItemSelectionModel.SelectionFlag.Rows,
            )

    def _select_row(self, row):
        self._loading_detail = True
        try:
            valid = 0 <= row < self.t.rowCount()
            self.detail_card.setEnabled(valid)
            if not valid:
                self.t.setCurrentCell(-1, -1)
                return
            self.t.setCurrentCell(row, 0)
            self.key_edit.setText(self.t.item(row, 0).text())
            self.group_edit.clear()
            self.group_edit.addItem("")
            self.group_edit.addItems(self.group_names)
            self.group_edit.setCurrentText(self.t.cellWidget(row, 1).currentText())
            self.action_edit.setEditText(self.t.cellWidget(row, 2).currentText())
            for index, combo in enumerate(self.option_edits, start=3):
                combo.setCurrentIndex(self.t.cellWidget(row, index).currentIndex())
            self.cooldown_edit.setValue(self.t.cellWidget(row, 6).value())
            self.submap_edit.setText(self.t.item(row, 7).text())
            locked = self.t.cellWidget(row, 8).isChecked()
            self.lock_edit.setChecked(locked)
            self._set_detail_locked(locked)
        finally:
            self._loading_detail = False

    def _set_detail_locked(self, locked):
        for widget in (
            self.key_edit, self.group_edit, self.action_edit, *self.option_edits,
            self.cooldown_edit, self.submap_edit,
        ):
            widget.setEnabled(not locked)

    def _write_detail(self, *_args):
        if self._loading_detail:
            return
        row = self.t.currentRow()
        if not 0 <= row < self.t.rowCount():
            return
        self.t.item(row, 0).setText(self.key_edit.text())
        self.t.cellWidget(row, 1).setCurrentText(self.group_edit.currentText())
        self.t.cellWidget(row, 2).setEditText(self.action_edit.currentText())
        for index, combo in enumerate(self.option_edits, start=3):
            self.t.cellWidget(row, index).setCurrentIndex(combo.currentIndex())
        self.t.cellWidget(row, 6).setValue(self.cooldown_edit.value())
        self.t.item(row, 7).setText(self.submap_edit.text())
        self.t.cellWidget(row, 8).setChecked(self.lock_edit.isChecked())
        self._set_detail_locked(self.lock_edit.isChecked())
        self._schedule_sync()

    def apply_group_filter(self, group):
        super().apply_group_filter(group)
        self._schedule_sync()

    def refresh_group_controls(self):
        super().refresh_group_controls()
        if hasattr(self, "bind_list"):
            self._sync_list()

    def add_new_row(self):
        self.search.clear()
        super().add_new_row()
        row = self.t.rowCount() - 1
        self._collapsed_groups.discard(self.t.cellWidget(row, 1).currentText())
        self.t.setCurrentCell(row, 0)
        self._sync_list(preserve_selection=False)

    def remove(self):
        super().remove()
        self._sync_list(preserve_selection=False)

    def duplicate_selected(self):
        count = self.t.rowCount()
        super().duplicate_selected()
        row = self.t.currentRow()
        if self.t.rowCount() > count and 0 <= row < self.t.rowCount():
            self.search.clear()
            self._collapsed_groups.discard(self.t.cellWidget(row, 1).currentText())
        self._sync_list(preserve_selection=False)

    def move_selected(self, offset):
        super().move_selected(offset)
        self._sync_list(preserve_selection=False)

    def toggle_all_locks(self):
        super().toggle_all_locks()
        self._sync_list()

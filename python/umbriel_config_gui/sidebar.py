"""Navigation sidebar: persisted page order and the section/page tab list."""

from .common import (
    GUI_DATA_DIR,
    QAbstractItemView,
    QEvent,
    QFrame,
    QFont,
    QFontMetrics,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPalette,
    QScrollBar,
    QSize,
    QStackedWidget,
    QTimer,
    QVBoxLayout,
    QWidget,
    Qt,
    json,
    os,
    write_text_file,
)
from .editors import EntryEditor
from .field_widget import FieldWidget
from .setting_help import CATEGORY_HELP
from .sidebar_icons import sidebar_icon
from .settings_layout import (
    SETTING_SECTION_BUTTON_HEIGHT,
    SETTING_SECTION_BUTTON_FONT_SIZE,
)
from .widgets import SwitchCheckBox


SIDEBAR_ORDER_PATH = os.path.join(GUI_DATA_DIR, "gui-sidebar-order.json")

def load_sidebar_order(default_order):
    """Load the user-defined Umbriel settings order, preserving newly added pages."""
    try:
        with open(SIDEBAR_ORDER_PATH, encoding="utf-8") as file:
            order = json.load(file)
        if not isinstance(order, list):
            raise ValueError("the saved sidebar order must be a JSON array")
    except FileNotFoundError:
        return list(default_order)
    except (OSError, ValueError) as error:
        QMessageBox.warning(
            None,
            "Could not load sidebar order",
            f"The saved sidebar order could not be loaded: {error}",
        )
        return list(default_order)

    available = set(default_order)
    ordered = []
    for name in order:
        if isinstance(name, str) and name in available and name not in ordered:
            ordered.append(name)
    ordered.extend(name for name in default_order if name not in ordered)
    return ordered


def save_sidebar_order(order):
    """Persist the user's Umbriel settings order."""
    try:
        write_text_file(SIDEBAR_ORDER_PATH, json.dumps(order, indent=2))
    except OSError as error:
        QMessageBox.warning(
            None,
            "Could not save sidebar order",
            f"The sidebar order could not be saved: {error}",
        )


class _SidebarListWidget(QListWidget):
    """Allow internal reordering only below the fixed desktop entries and divider."""

    def __init__(self, fixed_rows, reordered):
        super().__init__()
        self.fixed_rows = fixed_rows
        self.reordered = reordered
        self.setDragDropMode(QAbstractItemView.DragDropMode.InternalMove)
        self.setDefaultDropAction(Qt.DropAction.MoveAction)
        self.setDragEnabled(True)
        self.setAcceptDrops(True)
        self.setDropIndicatorShown(True)

    def changeEvent(self, event):
        super().changeEvent(event)
        if event.type() == QEvent.Type.PaletteChange:
            for row in range(self.count()):
                item = self.item(row)
                name = item.data(Qt.ItemDataRole.UserRole)
                if isinstance(name, str):
                    item.setIcon(sidebar_icon(name, self.palette()))

    def dropEvent(self, event):
        source_row = self.currentRow()
        target_row = self.indexAt(event.position().toPoint()).row()
        if source_row < self.fixed_rows:
            event.ignore()
            return
        if target_row < self.fixed_rows:
            last_row = self.count() - 1
            below_list = (
                target_row == -1
                and last_row >= self.fixed_rows
                and event.position().y()
                >= self.visualItemRect(self.item(last_row)).bottom()
            )
            if not below_list:
                event.ignore()
                return

        super().dropEvent(event)
        if event.isAccepted():
            QTimer.singleShot(0, self.reordered)


class SideTabs(QWidget):
    """Vertical navigation: section headings and page names on the left, the selected page on the right.

    Offers addTab(widget, name) like QTabWidget, plus addSection(title) for a non-clickable heading.
    """

    def __init__(self):
        """Create searchable navigation and the stacked page area beside it."""
        super().__init__()
        lay = QHBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)
        self.pages = {}  # list row -> stack index (heading rows have no page)
        self.page_rows = {}
        self.page_widgets = {}
        self._lazy_pages = {}
        self._search_fields = {}
        self._search_generation = 0
        self._row_names = {}
        self._separator_rows = set()
        self.settings_title = QLabel("Settings")
        title_font = QFont(self.settings_title.font())
        title_font.setBold(True)
        title_font.setPointSize(10)
        self.settings_title.setFont(title_font)
        self.settings_title.setContentsMargins(4, 2, 4, 2)
        self.search = QLineEdit()
        self.search.setPlaceholderText("Search settings...")
        self.search.setClearButtonEnabled(True)
        self.search.setStyleSheet(
            "QLineEdit {"
            " background: palette(window);"
            " border: 1px solid palette(midlight);"
            " border-radius: 8px;"
            " padding: 5px 8px;"
            "}"
            "QLineEdit:hover { border-color: palette(highlight); }"
        )
        self.nav = _SidebarListWidget(3, self._sync_navigation_order)
        self.nav.setToolTip("Drag Umbriel settings to change their order.")
        self.nav.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.nav.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.nav.setIconSize(QSize(16, 16))
        self.base_font = QFont(self.nav.font())
        self.base_font.setPointSize(SETTING_SECTION_BUTTON_FONT_SIZE)
        self.nav.setFont(self.base_font)
        item_height = SETTING_SECTION_BUTTON_HEIGHT - 2 * (3 + 2)
        self.nav_scrollbar = QScrollBar(Qt.Orientation.Vertical)
        self.nav_scrollbar.setFixedWidth(self.nav_scrollbar.sizeHint().width())
        scrollbar_policy = self.nav_scrollbar.sizePolicy()
        scrollbar_policy.setRetainSizeWhenHidden(True)
        self.nav_scrollbar.setSizePolicy(scrollbar_policy)
        internal_scrollbar = self.nav.verticalScrollBar()
        internal_scrollbar.rangeChanged.connect(self._sync_navigation_scrollbar)
        internal_scrollbar.valueChanged.connect(self.nav_scrollbar.setValue)
        self.nav_scrollbar.valueChanged.connect(internal_scrollbar.setValue)
        self.nav.setStyleSheet(
            "QListWidget { background: transparent; border: 0; outline: 0; }"
            "QListWidget::item {"
            f" height: {item_height}px; padding: 2px 8px;"
            " margin: 1px 3px;"
            " border: 1px solid transparent; border-radius: 8px; }"
            "QListWidget::item:hover { background: palette(midlight);"
            " color: palette(text); }"
            "QListWidget::item:selected {"
            " background: palette(highlight); color: palette(highlighted-text);"
            " border-color: palette(highlight); font-weight: 600; }"
        )
        self.stack = QStackedWidget()
        self.content = QStackedWidget()
        self.content.addWidget(self.stack)
        self.no_results = QLabel("No matching options")
        self.no_results.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.no_results.setForegroundRole(QPalette.ColorRole.PlaceholderText)
        self.content.addWidget(self.no_results)
        right = QWidget()
        right_layout = QVBoxLayout(right)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setSpacing(0)
        filter_bar = QHBoxLayout()
        self.filter_bar = filter_bar
        filter_bar.setContentsMargins(18, 4, 18, 0)
        filter_bar.addStretch()
        filter_label = QLabel("Overridden")
        self.overridden = SwitchCheckBox()
        self.overridden.setAccessibleName("Show overridden settings only")
        self.overridden.setToolTip(
            "Show settings whose current values differ from their schema defaults "
            "(or the GUI defaults when schema metadata is unavailable). "
            "Unset settings are hidden; non-field editors are not filtered. "
            "Values inherited from included configs are not resolved."
        )
        filter_label.setBuddy(self.overridden)
        filter_bar.addWidget(filter_label)
        filter_bar.addWidget(self.overridden)
        right_layout.addLayout(filter_bar)
        right_layout.addWidget(self.content, 1)
        self._updating_search = False
        self._search_timer = QTimer(self)
        self._search_timer.setSingleShot(True)
        self._search_timer.setInterval(150)
        self._search_timer.timeout.connect(self._apply_search_results)
        left = QWidget()
        left.setObjectName("settingsSidebar")
        left.setAutoFillBackground(True)
        self.left_panel = left
        left_layout = QGridLayout(left)
        left_layout.setContentsMargins(8, 8, 10, 8)
        left_layout.setSpacing(8)
        left_layout.setColumnMinimumWidth(1, self.nav_scrollbar.width())
        left_layout.setColumnStretch(0, 1)
        left_layout.addWidget(self.settings_title, 0, 0, 1, 2)
        left_layout.addWidget(self.search, 1, 0, 1, 2)
        left_layout.addWidget(self.nav, 2, 0)
        left_layout.addWidget(self.nav_scrollbar, 2, 1)
        left_layout.setRowStretch(2, 1)
        lay.addWidget(left)
        lay.addWidget(right, 1)
        self._sync_navigation_scrollbar(
            internal_scrollbar.minimum(), internal_scrollbar.maximum()
        )
        self.nav.currentRowChanged.connect(self.show_row)
        self.search.textChanged.connect(self.update_search_results)
        self.overridden.toggled.connect(self.update_search_results)

    def set_schema_bar(self, schema_bar):
        """Keep schema information available in the page toolbar."""
        self.filter_bar.insertLayout(0, schema_bar, 1)

    def _sync_navigation_scrollbar(self, minimum, maximum):
        """Mirror the hidden list scrollbar in the sidebar's outer edge."""
        internal_scrollbar = self.nav.verticalScrollBar()
        self.nav_scrollbar.setRange(minimum, maximum)
        self.nav_scrollbar.setPageStep(internal_scrollbar.pageStep())
        self.nav_scrollbar.setSingleStep(internal_scrollbar.singleStep())
        self.nav_scrollbar.setValue(internal_scrollbar.value())
        self.nav_scrollbar.setVisible(maximum > minimum)

    def _sync_navigation_order(self):
        """Refresh page-row mappings after a drag and save the new order."""
        self.pages.clear()
        self.page_rows.clear()
        self._row_names.clear()
        order = []
        for row in range(self.nav.count()):
            name = self.nav.item(row).data(Qt.ItemDataRole.UserRole)
            if not isinstance(name, str):
                continue
            order.append(name)
            self.pages[row] = self.stack.indexOf(self.page_widgets[name])
            self.page_rows[name] = row
            self._row_names[row] = name
        selected_row = self.nav.currentRow()
        self.show_row(selected_row)
        save_sidebar_order(order)

    def size_navigation(self):
        """Size the sidebar so search and navigation labels fit."""
        selected_font = QFont(self.base_font)
        selected_font.setBold(True)
        label_width = max(
            (
                max(
                    QFontMetrics(self.nav.item(row).font()).horizontalAdvance(
                        self.nav.item(row).text()
                    ),
                    QFontMetrics(selected_font).horizontalAdvance(
                        self.nav.item(row).text()
                    ),
                )
                for row in range(self.nav.count())
            ),
            default=0,
        )
        item_spacing = (
            2 * (8 + 1 + 3) + self.nav.iconSize().width() + 4
            + 2 * self.nav.frameWidth()
        )
        nav_width = label_width + item_spacing
        search_chrome_width = 2 * 8 + 2 + 24
        search_width = (
            self.search.fontMetrics().horizontalAdvance(self.search.placeholderText())
            + search_chrome_width
        )
        content_width = max(nav_width, search_width) + 12
        margins = self.left_panel.layout().contentsMargins()
        self.left_panel.setFixedWidth(
            content_width
            + self.nav_scrollbar.width()
            + margins.left()
            + margins.right()
        )
        self.nav.setFixedWidth(content_width)
        self.search.setFixedWidth(content_width)

    def show_row(self, row):
        """Show the page belonging to the selected list row (headings have none)."""
        if row in self.pages:
            page_name = self._row_names[row]
            self._materialize_page(page_name)
            self.stack.setCurrentIndex(self.pages[row])
            if self.overridden.isChecked():
                self.update_search_results(self.search.text())

    def addTab(self, widget, name):
        """Add a page under `name`; the first page added is selected automatically."""
        self._add_tab(widget, name)

    def addLazyTab(self, factory, name):
        """Add a page that is built only when selected or explicitly requested."""
        self._add_tab(QWidget(), name, factory)

    def addSeparator(self):
        """Add a non-selectable divider between groups of sidebar pages."""
        row = self.nav.count()
        item = QListWidgetItem()
        item.setFlags(Qt.ItemFlag.NoItemFlags)
        line = QFrame()
        line.setFrameShape(QFrame.Shape.HLine)
        line.setFrameShadow(QFrame.Shadow.Sunken)
        item.setSizeHint(QSize(0, line.sizeHint().height() + 4))
        self.nav.addItem(item)
        self.nav.setItemWidget(item, line)
        self._separator_rows.add(row)

    def _add_tab(self, widget, name, factory=None):
        row = self.nav.count()
        item = QListWidgetItem(name)
        item.setIcon(sidebar_icon(name, self.nav.palette()))
        help_text = CATEGORY_HELP.get(name, f"Configure {name.lower()} settings.")
        if row >= 3:
            help_text += "\nDrag to reorder settings."
        item.setToolTip(help_text)
        item.setFont(self.base_font)
        item.setData(Qt.ItemDataRole.UserRole, name)
        self.nav.addItem(item)
        self.size_navigation()
        self.pages[row] = self.stack.addWidget(widget)
        self.page_rows[name] = row
        self.page_widgets[name] = widget
        self._row_names[row] = name
        if factory is not None:
            self._lazy_pages[name] = factory
        self._watch_entry_editor(widget)
        if len(self.pages) == 1:
            self.nav.setCurrentRow(row)

    def _watch_entry_editor(self, widget):
        if isinstance(widget, EntryEditor):
            widget.list.currentRowChanged.connect(
                lambda _row, page=widget: self._entry_selection_changed(page)
            )

    def _entry_selection_changed(self, page):
        for name, registered_page in self.page_widgets.items():
            if registered_page is page:
                self._search_fields.pop(name, None)
                break
        self.update_search_results(self.search.text())

    def _materialize_page(self, name):
        factory = self._lazy_pages.get(name)
        if factory is None:
            return
        widget = factory()
        placeholder = self.page_widgets[name]
        index = self.stack.indexOf(placeholder)
        self.stack.removeWidget(placeholder)
        placeholder.deleteLater()
        self.pages[self.page_rows[name]] = self.stack.insertWidget(index, widget)
        self.page_widgets[name] = widget
        self._search_fields.pop(name, None)
        del self._lazy_pages[name]
        self._watch_entry_editor(widget)

    def materialize(self, name):
        """Build the page registered under `name` if it is still deferred."""
        self._materialize_page(name)

    def ensureAllPages(self):
        """Build all deferred pages for operations that inspect every page."""
        for name in tuple(self._lazy_pages):
            self._materialize_page(name)

    def preloadPages(self):
        """Build deferred pages one per event-loop tick so the UI stays responsive."""
        def step():
            if not self._lazy_pages:
                return
            current = self.stack.currentWidget()
            for name in tuple(self._lazy_pages):
                if self.page_widgets.get(name) is not current:
                    self._materialize_page(name)
                    break
            else:
                return
            QTimer.singleShot(0, step)
        QTimer.singleShot(0, step)

    def update_search_results(self, query):
        """Debounce search updates before filtering settings pages."""
        if self._updating_search:
            return
        self._search_generation += 1
        self._search_timer.start()

    def _apply_search_results(self):
        """Build deferred pages incrementally before applying a cross-page search."""
        query = self.search.text()
        generation = self._search_generation
        if query.strip() and self._lazy_pages:
            self._materialize_search_page(generation, query)
            return
        self._filter_search_results(query)

    def _materialize_search_page(self, generation, query):
        if generation != self._search_generation:
            return
        if not query.strip():
            self._filter_search_results(query)
            return
        name = next(iter(self._lazy_pages), None)
        if name is None:
            self._filter_search_results(query)
            return
        self._materialize_page(name)
        QTimer.singleShot(
            0, lambda: self._materialize_search_page(generation, query)
        )

    def _filter_search_results(self, query):
        """Filter materialized option pages, preserving their normal layout."""
        self._updating_search = True
        try:
            query = query.strip().casefold()
            self.nav.setDragEnabled(not query)
            self.nav.setAcceptDrops(not query)
            terms = query.split()
            matching_pages = []
            for row in self._separator_rows:
                self.nav.item(row).setHidden(bool(query))
            for page_name, page in self.page_widgets.items():
                fields = self._search_fields.get(page_name)
                if fields is None:
                    fields = tuple(page.findChildren(FieldWidget))
                    self._search_fields[page_name] = fields
                    for field_widget in fields:
                        if not field_widget.property("sidebarFilterConnected"):
                            field_widget.valueChanged.connect(self._field_changed)
                            field_widget.setProperty("sidebarFilterConnected", True)
                groups = set()
                matched_groups = set()
                filtering = bool(query) or self.overridden.isChecked()
                for field_widget in fields:
                    group = field_widget.search_group
                    groups.add(group)
                    if not filtering:
                        field_widget.search_form.setRowVisible(
                            field_widget.search_row, True
                        )
                        if field_widget.opacity_row is not None:
                            field_widget.search_form.setRowVisible(field_widget.opacity_row, True)
                        continue

                    group.rememberSearchState()
                    searchable = getattr(field_widget, "_sidebar_search_text", None)
                    if searchable is None:
                        searchable = " ".join(
                            (
                                field_widget.f.label,
                                ".".join(field_widget.f.path),
                                field_widget.search_group_title,
                                page_name,
                                field_widget.help_button.toolTip(),
                            )
                        ).casefold()
                        field_widget._sidebar_search_text = searchable
                    matches = all(term in searchable for term in terms) and (
                        not self.overridden.isChecked() or field_widget.is_overridden()
                    )
                    field_widget.search_form.setRowVisible(
                        field_widget.search_row, matches
                    )
                    if field_widget.opacity_row is not None:
                        field_widget.search_form.setRowVisible(field_widget.opacity_row, matches)
                    if matches:
                        matched_groups.add(group)

                if filtering:
                    for group in groups:
                        group_matches = group in matched_groups
                        group.setVisible(group_matches)
                        if hasattr(group, "section_button"):
                            group.section_button.setVisible(group_matches)
                        if group_matches:
                            group.setExpanded(True)
                else:
                    for group in groups:
                        group.restoreSearchState()
                        if hasattr(group, "section_button"):
                            group.section_button.setVisible(True)
                notices = {
                    group.filter_notice for group in groups
                    if hasattr(group, "filter_notice")
                }
                for notice in notices:
                    notice.setVisible(
                        self.overridden.isChecked()
                        and not any(group.filter_notice is notice for group in matched_groups
                                    if hasattr(group, "filter_notice"))
                    )

                if matched_groups:
                    matching_pages.append(page_name)
                self.nav.item(self.page_rows[page_name]).setHidden(
                    bool(query) and not bool(matched_groups)
                )

            if not query:
                for row in range(self.nav.count()):
                    self.nav.item(row).setHidden(False)
                self.content.setCurrentWidget(self.stack)
                return

            current_page = self.stack.currentWidget()
            current_has_matches = any(
                self.page_widgets.get(name) is current_page for name in matching_pages
            )
            if matching_pages and not current_has_matches:
                self.nav.setCurrentRow(self.page_rows[matching_pages[0]])

            self.content.setCurrentWidget(
                self.stack if matching_pages else self.no_results
            )
        finally:
            self._updating_search = False

    def _field_changed(self):
        if self.overridden.isChecked():
            self.update_search_results(self.search.text())


# Sidebar layout: section heading -> page names (any page not listed ends up under "Other").

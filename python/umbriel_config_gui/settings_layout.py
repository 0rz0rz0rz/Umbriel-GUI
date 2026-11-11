"""Settings page layout, collapsible groups, and saved expansion state."""

import json
import os

from .common import (
    MISSING, GUI_DATA_DIR, QEvent, QFont, QFormLayout, QGroupBox, QHBoxLayout,
    QLabel, QMessageBox, QPainter, QPalette, QSizePolicy, QPushButton,
    QScrollArea, QToolButton, QVBoxLayout, QWidget, Qt, getp,
    normalize_optional_includes, migrate_gui_file, py, textwrap, write_text_file,
)
from .field_widget import FieldWidget
from .kde_titlebar import KdeTitleBarFollower, TITLE_BAR_KEYS
from .setting_help import CATEGORY_HELP, GROUP_HELP, setting_description
from .widgets import FlowLayout, OverviewButton, SettingLabel, SettingRow, WrappedLabel


class CollapsibleGroup(QGroupBox):
    """A settings group whose fields only show while its header checkbox is ticked.

    The header says "(using defaults)" when none of the group's keys are in the
    config file, or "(N set)" when some are. Groups with keys already in the file
    open automatically; everything else starts collapsed to save space.
    Collapsing never changes the file: hidden fields keep their values.
    """

    def __init__(self, title, n_set, collapsible=True, description=""):
        """Create the header checkbox (when collapsible) and the hidden/visible body that holds the form rows."""
        super().__init__()
        self.header = None
        self.search_original_expanded = None
        self.body = QWidget()
        self.setObjectName("settingsCard")
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Maximum)
        self.setStyleSheet(
            "QGroupBox#settingsCard {"
            " background: palette(window);"
            " border: 2px solid palette(midlight);"
            " border-radius: 18px;"
            " margin: 0px;"
            "}"
            "QGroupBox#settingsCard[cardCollapsed=\"true\"] {"
            " border-radius: 14px;"
            "}"
        )
        self.setProperty("cardHovered", False)
        self._hover_targets = []
        if description:
            self.setAccessibleDescription(description)
        self.form = QFormLayout(self.body)
        self.form.setHorizontalSpacing(16)
        self.form.setVerticalSpacing(5)
        self.form.setContentsMargins(12, 2, 12, 10)
        self.form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.ExpandingFieldsGrow)
        self.form.setLabelAlignment(Qt.AlignmentFlag.AlignLeft)
        self.form.setFormAlignment(Qt.AlignmentFlag.AlignTop)
        self.form.setRowWrapPolicy(QFormLayout.RowWrapPolicy.WrapLongRows)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)
        self.header_background = QWidget()
        self.header_background.setObjectName("settingsCardHeader")
        header_row = QHBoxLayout(self.header_background)
        header_row.setContentsMargins(8, 0, 8, 0)
        if collapsible:
            header = QPushButton()
            self.header = header
            header.setText(title)
            header.setCheckable(True)
            header.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
            header.setFixedHeight(SETTING_SECTION_BUTTON_HEIGHT)
            header.setFlat(True)
            header_font = QFont(header.font())
            header_font.setPointSize(SETTING_SECTION_BUTTON_FONT_SIZE)
            header_font.setBold(True)
            header.setFont(header_font)
            header.setStyleSheet(
                "QPushButton { text-align: left; background: transparent; border: 2px solid transparent; }"
                "QPushButton:hover { border-color: transparent; border-radius: 8px; }"
                "QPushButton:checked { background: transparent; }"
            )
            header.setAccessibleDescription(description)
            header.setToolTip(description)
            arrow = QToolButton()
            arrow.setAutoRaise(True)
            arrow.setFixedSize(24, 24)
            arrow.setStyleSheet(
                "QToolButton { background: transparent; border: 2px solid transparent; }"
                "QToolButton:hover { border-color: transparent; border-radius: 8px; }"
            )
            arrow.setAccessibleName(f"Toggle {title}")
            arrow.setToolTip("Expand or collapse this section")
            self.header_background.installEventFilter(self)
            self._hover_targets.append(self.header_background)

            def update_arrow(expanded):
                arrow.setArrowType(
                    Qt.ArrowType.DownArrow if expanded else Qt.ArrowType.RightArrow
                )

            header.toggled.connect(update_arrow)
            arrow.clicked.connect(lambda _checked=False: header.toggle())
            update_arrow(n_set > 0)
            header_row.addWidget(header, 1)
            header_row.addWidget(arrow)
        else:
            heading = QLabel(title)
            heading_font = QFont(heading.font())
            heading_font.setBold(True)
            heading_font.setPointSize(13)
            heading.setFont(heading_font)
            header_row.addWidget(heading)
            header_row.addStretch(1)
            self.help_button = QToolButton()
            self.help_button.setText("?")
            self.help_button.setAutoRaise(True)
            self.help_button.setFixedSize(20, 20)
            self.help_button.setAccessibleName(f"Help for {title}")
            self.help_button.setToolTip("\n".join(textwrap.fill(line, width=42) for line in description.splitlines()))
            header_row.addWidget(self.help_button)
        lay.addWidget(self.header_background)
        lay.addWidget(self.body)
        if collapsible:
            # Set visibility only after the body has its parent: reparenting resets it.
            header.toggled.connect(self.body.setVisible)
            header.toggled.connect(self._update_collapsed_style)
            header.setChecked(n_set > 0)
            self.body.setVisible(n_set > 0)
            self._update_collapsed_style(n_set > 0)

    def _update_collapsed_style(self, expanded):
        self.setProperty("cardCollapsed", not expanded)
        self.style().unpolish(self)
        self.style().polish(self)
        self.update()

    def paintEvent(self, event):
        super().paintEvent(event)
        if self.property("cardHovered"):
            painter = QPainter(self)
            painter.setRenderHint(QPainter.RenderHint.Antialiasing)
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(self.palette().color(QPalette.ColorRole.Midlight))
            radius = 12 if self.property("cardCollapsed") else 16
            painter.drawRoundedRect(self.rect().adjusted(2, 2, -2, -2), radius, radius)

    def eventFilter(self, watched, event):
        if watched in self._hover_targets:
            if event.type() == QEvent.Type.Enter:
                self._set_card_hovered(True)
            elif event.type() == QEvent.Type.Leave:
                self._set_card_hovered(False)
        return super().eventFilter(watched, event)

    def _set_card_hovered(self, hovered):
        if self.property("cardHovered") == hovered:
            return
        self.setProperty("cardHovered", hovered)
        self.update()

    def setExpanded(self, expanded):
        """Expand or collapse the group while keeping its header checkbox in sync."""
        if self.header is not None:
            self.header.setChecked(expanded)

    def rememberSearchState(self):
        """Remember whether the group was expanded before a search temporarily opens it."""
        if self.search_original_expanded is None:
            self.search_original_expanded = (
                self.header.isChecked() if self.header is not None else True
            )

    def restoreSearchState(self):
        """Restore the group's visibility and expansion state after search is cleared."""
        self.setVisible(True)
        if self.search_original_expanded is not None:
            self.setExpanded(self.search_original_expanded)
            self.search_original_expanded = None


_GROUP_EXPANSION_PATH = os.path.join(
    GUI_DATA_DIR, "gui-state.json"
)
_group_expansion_states = None


def load_group_expansion_states():
    """Load saved section expansion states, falling back to defaults if unavailable."""
    global _group_expansion_states
    if _group_expansion_states is not None:
        return _group_expansion_states
    try:
        migrate_gui_file(
            os.path.join(
                os.environ.get("XDG_CONFIG_HOME") or os.path.expanduser("~/.config"),
                "umbriel",
                "gui-state.json",
            ),
            _GROUP_EXPANSION_PATH,
        )
        with open(_GROUP_EXPANSION_PATH, encoding="utf-8") as file:
            data = json.load(file)
        if not isinstance(data, dict):
            raise ValueError("the saved GUI state must be a JSON object")
        _group_expansion_states = {}
        for page, groups in data.items():
            if isinstance(page, str) and isinstance(groups, dict):
                _group_expansion_states[page] = {
                    title: expanded
                    for title, expanded in groups.items()
                    if isinstance(title, str) and isinstance(expanded, bool)
                }
    except FileNotFoundError:
        _group_expansion_states = {}
    except (OSError, ValueError) as error:
        QMessageBox.warning(
            None,
            "Could not load GUI state",
            f"Section expansion states could not be loaded: {error}",
        )
        _group_expansion_states = {}
    return _group_expansion_states


def save_group_expansion_state(page, title, expanded):
    """Persist the user's expanded/collapsed state for a settings section."""
    states = load_group_expansion_states()
    states.setdefault(page, {})[title] = bool(expanded)
    try:
        write_text_file(_GROUP_EXPANSION_PATH, json.dumps(states, indent=2))
    except OSError as error:
        QMessageBox.warning(
            None,
            "Could not save GUI state",
            f"Section expansion state could not be saved: {error}",
        )


SIDEBAR_SECTIONS = [
    ("Desktop", ["User folders", "Default apps"]),
    ("Basics", ["General"]),
    ("Look", ["Appearance", "Colors", "Animation", "Animation curves", "Effects"]),
    ("Behavior", ["Input", "Layout", "Workspaces"]),
    ("Bindings", ["Keybinds"]),
    ("Rules and devices", ["Window rules", "Layer rules", "Workspace rules", "Outputs",
                           "Scratchpads", "Input devices", "Security rules", "Environment"]),
]

SETTING_SECTION_BUTTON_FONT_SIZE = 10
SETTING_SECTION_BUTTON_HEIGHT = 32


def form_page(groups, doc, store, collapsible=True, category="", schema_prefix=""):
    """Build a scrollable page from [(title, [Field, ...]), ...].

    Every field gets a FieldWidget (also appended to `store` so saving can read
    them). `doc` is the table the field paths are looked up in: the whole config
    for normal tabs, or one rule/output entry for the rule editors.
    """
    page = QWidget()
    page.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
    page_layout = QHBoxLayout(page)
    page_layout.setContentsMargins(18, 4, 18, 10)
    page_layout.setSpacing(0)
    content = QWidget()
    content.setMinimumWidth(0)
    content.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
    page_layout.addWidget(content, 1)
    v = QVBoxLayout(content)
    v.setContentsMargins(0, 0, 0, 0)
    v.setSpacing(8)

    overview = OverviewButton()
    overview.setObjectName("settingsOverview")
    overview.setCursor(Qt.CursorShape.PointingHandCursor)
    overview.setAccessibleName(category or "Settings overview")
    overview.setAccessibleDescription(
        "Click to expand or collapse all settings sections."
    )
    overview.setToolTip(
        "Click to expand or collapse all settings sections.\n"
        "Only settings you choose to override are written; unset values keep Umbriel's defaults."
        + ("\n" + CATEGORY_HELP[category] if category in CATEGORY_HELP else "")
    )
    overview.setStyleSheet(
        "QPushButton#settingsOverview {"
        " background: transparent;"
        " border: 0px;"
        " border-radius: 8px;"
        " text-align: left;"
        "}"
        "QPushButton#settingsOverview:hover {"
        " background: palette(alternate-base);"
        "}"
    )
    overview_layout = QVBoxLayout(overview)
    overview_layout.setContentsMargins(6, 4, 6, 4)
    page_title = QLabel(category or "Settings")
    page_title.setObjectName("pageTitle")
    title_font = QFont(page_title.font())
    title_font.setBold(True)
    title_font.setPointSize(13)
    page_title.setFont(title_font)
    page_title.setForegroundRole(QPalette.ColorRole.Highlight)
    page_title.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
    overview_layout.addWidget(page_title)
    v.addWidget(overview)

    section_navigation = QWidget()
    section_navigation.setObjectName("sectionNavigation")
    section_navigation.setMinimumWidth(0)
    section_navigation.setSizePolicy(
        QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum
    )
    section_navigation_policy = section_navigation.sizePolicy()
    section_navigation_policy.setHeightForWidth(True)
    section_navigation.setSizePolicy(section_navigation_policy)
    section_layout = FlowLayout(section_navigation)

    section_buttons = []
    section_groups = []
    kde_fields = []
    saved_expansion_states = load_group_expansion_states().get(category, {})
    group_page = QWidget()
    group_page.setMinimumWidth(0)
    group_page.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
    group_layout = QVBoxLayout(group_page)
    group_layout.setContentsMargins(0, 0, 0, 0)
    group_layout.setSpacing(8)
    filter_notice = QLabel("No settings differ from their defaults.")
    filter_notice.setForegroundRole(QPalette.ColorRole.PlaceholderText)
    filter_notice.setWordWrap(True)
    filter_notice.hide()
    group_layout.addWidget(filter_notice)
    for title, fields in groups:
        n_set = sum(1 for f in fields if getp(doc, f.path) is not MISSING)
        group_description = GROUP_HELP.get(title)
        if group_description is None and title.startswith("Hot corner:"):
            corner = title.partition(":")[2].strip()
            group_description = f"Set the trigger delay and action for the {corner} screen corner."
        if group_description is None:
            group_description = f"Settings for {title.lower()}."
        box = CollapsibleGroup(title, n_set, collapsible, group_description)
        box.filter_notice = filter_notice
        section_groups.append(box)
        if box.header is not None:
            if title in saved_expansion_states:
                box.setExpanded(saved_expansion_states[title])
            else:
                box.setExpanded(True)

            def save_expansion(expanded, group=box, group_title=title):
                if group.search_original_expanded is None:
                    save_group_expansion_state(category, group_title, expanded)

            box.header.toggled.connect(save_expansion)
        for f in fields:
            current = getp(doc, f.path)
            if f.path == ("include", "optional", "files") and current is not MISSING:
                current = normalize_optional_includes(py(current))
            schema_path = ".".join(part for part in (schema_prefix, ".".join(f.path)) if part)
            fw = FieldWidget(f, current, schema_path)
            if category == "Colors" and f.path in TITLE_BAR_KEYS:
                kde_fields.append(fw)
            if f.kind == "str" and fw.schema_option and fw.schema_option.get("format") == "effect":
                fw.w.setPlaceholderText("Effect preset name")
            elif f.kind in ("list", "strorlist"):
                fw.w.setPlaceholderText("Comma-separated values" if f.kind == "list" else "Text or TOML array")
            help_description = setting_description(f, category or title, title)
            fw.help_button.setToolTip(help_description)
            field_title = QLabel(f.label)
            title_font = QFont(field_title.font())
            title_font.setBold(True)
            title_font.setPointSize(10)
            field_title.setFont(title_font)
            description_text = (
                help_description
                if category
                else setting_description(f, "Settings", title)
            ).partition(
                "\nApplies to:"
            )[0]
            description_text = " ".join(description_text.splitlines())
            description_text = description_text.partition(
                " Leave this setting unset to omit its key"
            )[0]
            description_text = description_text.partition(
                " This value is written directly to the config."
            )[0]
            description_text = description_text.partition(" Options:")[0]
            if f.kind == "combo":
                description_text += " Choose or type a custom value."
            description = WrappedLabel(description_text)
            description.setForegroundRole(QPalette.ColorRole.PlaceholderText)
            label_widget = SettingLabel(field_title, description)
            row_widget = SettingRow(label_widget, fw)
            fw.field_label = field_title
            fw.search_group = box
            fw.search_group_title = title
            fw.search_form = box.form
            fw.search_row = row_widget
            store.append(fw)
            box.form.addRow(row_widget)
            if fw.opacity_widget is not None:
                opacity_title = QLabel(f"{f.label} opacity")
                opacity_title.setFont(title_font)
                opacity_description = WrappedLabel("Color opacity: 0.0 is transparent, 1.0 is opaque.")
                opacity_description.setForegroundRole(QPalette.ColorRole.PlaceholderText)
                opacity_row = SettingRow(SettingLabel(opacity_title, opacity_description), fw.opacity_widget)
                fw.opacity_row = opacity_row
                fw.opacity_help.setToolTip("Color opacity: 0.0 is transparent, 1.0 is opaque.")
                fw.opacity_widget.setFixedWidth(fw.sizeHint().width())
                box.form.addRow(opacity_row)
        group_layout.addWidget(box, 0, Qt.AlignmentFlag.AlignTop)

        section_button = QToolButton()
        section_button.setText(title)
        section_button.setCheckable(True)
        section_button.setChecked(box.header.isChecked() if box.header is not None else True)
        section_button.setAutoRaise(True)
        section_button.setFixedHeight(SETTING_SECTION_BUTTON_HEIGHT)
        section_font = QFont(section_button.font())
        section_font.setPointSize(SETTING_SECTION_BUTTON_FONT_SIZE)
        section_button.setFont(section_font)
        section_button.setToolTip(f"Expand or collapse {title}" if box.header is not None else f"Go to {title}")
        section_button.setStyleSheet(
            "QToolButton {"
            " border: 1px solid palette(midlight);"
            " border-radius: 9px;"
            " padding: 4px 10px;"
            " background: palette(window);"
            " color: palette(text);"
            "}"
            "QToolButton:checked {"
            " border-color: palette(highlight);"
            " background: palette(highlight);"
            " color: palette(highlighted-text);"
            "}"
            "QToolButton:hover { border-color: palette(text); }"
        )
        box.section_button = section_button
        section_buttons.append(section_button)
        section_layout.addWidget(section_button)

    group_layout.addStretch(1)
    v.insertWidget(1, section_navigation)

    sections_scroll = QScrollArea()
    sections_scroll.setObjectName("settingsSectionsScroll")
    sections_scroll.setWidgetResizable(True)
    sections_scroll.setFrameShape(QScrollArea.Shape.NoFrame)
    sections_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
    sections_scroll.setWidget(group_page)
    v.addWidget(sections_scroll, 1)

    def navigate_to_group(index, checked):
        group = section_groups[index]
        if group.header is not None:
            group.setExpanded(checked)
        else:
            section_buttons[index].setChecked(True)
        if checked or group.header is None:
            sections_scroll.ensureWidgetVisible(group, 0, 12)

    for index, (group, button) in enumerate(zip(section_groups, section_buttons)):
        button.clicked.connect(
            lambda checked, group_index=index: navigate_to_group(group_index, checked)
        )
        if group.header is not None:
            group.header.toggled.connect(button.setChecked)

    def toggle_all_groups():
        expand = not all(
            group.header.isChecked()
            for group in section_groups
            if group.header is not None
        )
        for group in section_groups:
            group.setExpanded(expand)

    overview.clicked.connect(toggle_all_groups)

    if kde_fields:
        page.kde_titlebar_follower = KdeTitleBarFollower(kde_fields, page)

    return page

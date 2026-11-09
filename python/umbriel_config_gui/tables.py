"""Key/value and named-map table editors, plus animation curve and effect pages."""

from .common import (
    ENV_NAME_RE,
    MISSING,
    QAbstractItemView,
    QFont,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QPalette,
    QPushButton,
    QTabWidget,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
    RESERVED_ENV,
    ensure_table,
    getp,
    py,
    tomlkit,
    totext,
)
from .editors import EntryEditor
from .field_defs import EFFECT_POOL_GROUPS, EFFECT_PRESET_GROUPS


# ----------------------------------------------------------- key/value tables
def parse_opts(text):
    """Parse the keybind options column ('repeat=false, allow_when_locked=true') into a dict with real booleans/ints."""
    out = {}
    for part in filter(None, (p.strip() for p in text.split(","))):
        k, _, v = part.partition("=")
        v = v.strip()
        out[k.strip()] = (v == "true") if v in ("true", "false") else int(v) if v.lstrip("-").isdigit() else v
    return out


def fmt_opts(o):
    """Format an options dict back into the 'key=value, key=value' text shown in the table."""
    return ", ".join(f"{k}={str(v).lower() if isinstance(v, bool) else v}" for k, v in o.items())


def tidy_table(t):
    """Match the app's compact table styling with subtle border emphasis instead of filled selection blocks."""
    palette = t.palette()
    base = palette.color(QPalette.ColorRole.Base)
    border = palette.color(QPalette.ColorRole.Mid)
    header = palette.color(QPalette.ColorRole.Button)
    header_text = palette.color(QPalette.ColorRole.ButtonText)
    text = palette.color(QPalette.ColorRole.Text)
    highlight = palette.color(QPalette.ColorRole.Highlight)

    t.setAlternatingRowColors(False)
    t.setShowGrid(False)
    t.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
    t.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
    t.setStyleSheet(
        f"QTableWidget {{"
        f"  background: {base.name()};"
        f"  color: {text.name()};"
        f"  border: 1px solid {border.name()};"
        f"  border-radius: 10px;"
        f"  gridline-color: transparent;"
        f"  selection-background-color: transparent;"
        f"  selection-color: {text.name()};"
        f"}}"
        f"QTableWidget::item {{"
        f"  padding: 6px 8px;"
        f"  border: 0;"
        f"  border-radius: 6px;"
        f"}}"
        f"QTableWidget::item:selected {{"
        f"  background: transparent;"
        f"  border: 2px solid {highlight.name()};"
        f"  border-radius: 6px;"
        f"  padding: 0;"
        f"}}"
        f"QHeaderView::section {{"
        f"  background: {header.name()};"
        f"  color: {header_text.name()};"
        f"  padding: 8px 10px;"
        f"  border: 0;"
        f"  border-bottom: 1px solid {border.name()};"
        f"  border-radius: 0;"
        f"  font-weight: 600;"
        f"}}"
        f"QHeaderView::section:horizontal {{"
        f"  border-right: 1px solid {border.name()};"
        f"}}"
        f"QHeaderView::section:vertical {{"
        f"  border-bottom: 1px solid {border.name()};"
        f"}}"
    )
    t.verticalHeader().setVisible(False)
    t.verticalHeader().setDefaultSectionSize(34)
    t.horizontalHeader().setMinimumHeight(34)


class KVTable(QWidget):
    """Editable two- or three-column table for key -> value tables: keybinds (with options) and [environment]."""
    def __init__(self, doc, path, heads, options):
        """Create the table and fill it from the config table at `path`. With `options=True`, entries given as {action=..., repeat=...} are split into action and options columns."""
        super().__init__()
        self.doc, self.path, self.options = doc, tuple(path.split(".")), options
        lay = QVBoxLayout(self)
        self.t = QTableWidget(0, len(heads))
        tidy_table(self.t)
        self.t.setHorizontalHeaderLabels(heads)
        column_help = (
            ["Shortcut", "Action to run", "Optional per-shortcut settings"]
            if options
            else ["Environment variable name", "Value exposed to the session and applications"]
        )
        for column, description in enumerate(column_help):
            self.t.horizontalHeaderItem(column).setToolTip(description)
        hdr = self.t.horizontalHeader()
        hdr.setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        hdr.setStretchLastSection(True)
        self.t.setColumnWidth(0, 220)
        if options:
            self.t.setColumnWidth(1, 300)
        lay.addWidget(self.t)
        row = QHBoxLayout()
        add, rem = QPushButton("Add"), QPushButton("Remove selected")
        add.clicked.connect(lambda: self.add_row("", "", ""))
        rem.clicked.connect(self.remove)
        row.addWidget(add)
        row.addWidget(rem)
        row.addStretch()
        lay.addLayout(row)
        if options:
            lay.addWidget(QPushButton("Options column: e.g.  repeat=false, allow_when_locked=true", enabled=False))
        self.orig = {}
        c = getp(doc, self.path)
        if c is not MISSING:
            for k, v in c.items():
                if options and not isinstance(v, str):
                    a, o = str(v.get("action", "")), {x: py(y) for x, y in v.items() if x != "action"}
                else:
                    a, o = str(v), {}
                self.orig[str(k)] = (a, o)
                self.add_row(str(k), a, fmt_opts(o))

    def add_row(self, k, a, o):
        """Append a row with the given key, value and (optional) options text."""
        r = self.t.rowCount()
        self.t.insertRow(r)
        for i, txt in enumerate((k, a, o)[:self.t.columnCount()]):
            self.t.setItem(r, i, QTableWidgetItem(txt))

    def remove(self):
        """Remove the rows that are currently selected."""
        for r in sorted({i.row() for i in self.t.selectedItems()}, reverse=True):
            self.t.removeRow(r)

    def rows(self):
        """Read the table into {key: (value, options)}, skipping rows with an empty key or value."""
        out = {}
        for r in range(self.t.rowCount()):
            cell = lambda c: (self.t.item(r, c).text().strip() if self.t.item(r, c) else "")
            if cell(0) and cell(1):
                out[cell(0)] = (cell(1), parse_opts(cell(2)) if self.options else {})
        return out

    def validate(self):
        """Check for duplicate names and invalid environment variables."""
        names = [
            self.t.item(row, 0).text().strip()
            for row in range(self.t.rowCount())
            if self.t.item(row, 0) and self.t.item(row, 0).text().strip()
        ]
        duplicates = sorted({name for name in names if names.count(name) > 1})
        if duplicates:
            raise ValueError(f"{'.'.join(self.path)}: duplicate name(s): {', '.join(duplicates)}")
        rows = self.rows()
        if self.path == ("environment",):
            for name in rows:
                if not ENV_NAME_RE.fullmatch(name):
                    raise ValueError(f'Environment: "{name}" is not a valid variable name')
                if name in RESERVED_ENV:
                    raise ValueError(f"Environment: {name} is owned by Umbriel and cannot be set here")

    def commit(self):
        """Write only the changed/added/removed rows into the config; unchanged lines keep their original formatting."""
        rows = self.rows()
        if not rows and getp(self.doc, self.path) is MISSING:
            return
        tbl = ensure_table(self.doc, self.path)
        for k in list(tbl.keys()):
            if k not in rows:
                del tbl[k]
        for k, (a, o) in rows.items():
            if self.orig.get(k) == (a, o):
                continue
            if o:
                it = tomlkit.inline_table()
                it["action"] = a
                for x, y in o.items():
                    it[x] = y
                tbl[k] = it
            else:
                tbl[k] = a
        self.orig = rows


class RawValueMapEditor(QWidget):
    """Edit a named TOML map whose values are arrays or tables."""

    def __init__(self, doc, path, title, value_kind, example):
        super().__init__()
        self.doc, self.path = doc, tuple(path.split("."))
        self.value_kind = value_kind
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel(title))
        self.t = QTableWidget(0, 2)
        tidy_table(self.t)
        self.t.setHorizontalHeaderLabels(["Name", "Value (TOML)"])
        self.t.horizontalHeaderItem(0).setToolTip("Name referenced by an animation event or effect pool.")
        self.t.horizontalHeaderItem(1).setToolTip("Enter the value in valid TOML syntax.")
        header = self.t.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        header.setStretchLastSection(True)
        layout.addWidget(self.t, 1)
        controls = QHBoxLayout()
        add_button, remove_button = QPushButton("Add"), QPushButton("Remove selected")
        add_button.clicked.connect(lambda: self.add_row("", ""))
        remove_button.clicked.connect(self.remove_rows)
        controls.addWidget(add_button)
        controls.addWidget(remove_button)
        controls.addStretch()
        layout.addLayout(controls)
        hint = QLabel(example)
        hint.setWordWrap(True)
        hint_font = QFont(hint.font())
        hint_font.setPointSize(9)
        hint.setFont(hint_font)
        layout.addWidget(hint)
        self.original = {}
        values = getp(doc, self.path)
        if values is not MISSING:
            for name, value in values.items():
                rendered = totext(py(value))
                self.original[str(name)] = rendered
                self.add_row(str(name), rendered)

    def add_row(self, name, value):
        row = self.t.rowCount()
        self.t.insertRow(row)
        self.t.setItem(row, 0, QTableWidgetItem(name))
        self.t.setItem(row, 1, QTableWidgetItem(value))

    def remove_rows(self):
        for row in sorted({item.row() for item in self.t.selectedItems()}, reverse=True):
            self.t.removeRow(row)

    def rows(self):
        values = {}
        for row in range(self.t.rowCount()):
            name_item, value_item = self.t.item(row, 0), self.t.item(row, 1)
            name = name_item.text().strip() if name_item else ""
            text = value_item.text().strip() if value_item else ""
            if not name and not text:
                continue
            if not name or not text:
                raise ValueError(f"{self.path[-1]} row {row + 1}: enter both a name and a TOML value")
            if name in values:
                raise ValueError(f"{self.path[-1]}: duplicate name {name!r}")
            try:
                value = tomlkit.parse("value = " + text + "\n")["value"]
            except Exception as e:
                raise ValueError(f"{name}: invalid TOML value ({e})")
            if self.value_kind == "array" and not isinstance(value, tomlkit.items.Array):
                raise ValueError(f"{name}: expected a TOML array")
            if self.value_kind == "table" and not isinstance(
                value, (tomlkit.items.InlineTable, tomlkit.items.Table)
            ):
                raise ValueError(f"{name}: expected a TOML table")
            values[name] = value
        return values

    def validate(self):
        self.rows()

    def commit(self):
        rows = self.rows()
        if not rows and getp(self.doc, self.path) is MISSING:
            return
        table = ensure_table(self.doc, self.path)
        for name in list(table.keys()):
            if name not in rows:
                del table[name]
        for name, value in rows.items():
            if self.original.get(name) != totext(py(value)):
                table[name] = value
        self.original = {name: totext(py(value)) for name, value in rows.items()}


class AnimationCurvesPage(QWidget):
    """Edit reusable Bézier and spring curves defined under [animation]."""

    def __init__(self, doc):
        super().__init__()
        layout = QVBoxLayout(self)
        self.tabs = QTabWidget()
        self.beziers = RawValueMapEditor(
            doc, "animation.beziers", "Named Bézier curves", "array",
            'A Bézier curve shapes the timing of an animation. Enter four numbers in order: '
            'the start-point x/y and end-point x/y, for example [0.05, 0.9, 0.1, 1.0]. '
            'The first and third numbers (x coordinates) must be between 0 and 1. Give the curve '
            'a name here, then type that name into an animation event’s Curve setting, for example '
            'curve = "soft" in [animation.windows_in].',
        )
        self.springs = RawValueMapEditor(
            doc, "animation.springs", "Named spring curves", "table",
            'A spring curve controls how an animation moves and settles. Enter damping and stiffness '
            'as a TOML table, for example { damping = 0.5, stiffness = 200 }. Lower damping allows '
            'more overshoot; higher damping reduces it. Higher stiffness settles faster. Give the '
            'spring a name here, then use that name in an animation event’s Curve setting, for example '
            'curve = "bouncy" in [animation.windows_in]. Valid ranges: damping 0.01–5, stiffness 1–10000.',
        )
        self.tabs.addTab(self.beziers, "Bézier")
        self.tabs.addTab(self.springs, "Springs")
        layout.addWidget(self.tabs)

    def validate(self):
        self.beziers.validate()
        for name, points in self.beziers.rows().items():
            points = py(points)
            if (not isinstance(points, list) or len(points) != 4
                    or not all(isinstance(point, (int, float)) and not isinstance(point, bool)
                               for point in points)):
                raise ValueError(f"{name}: Bézier curves need exactly four numbers: [x1, y1, x2, y2]")
            if not (0 <= points[0] <= 1 and 0 <= points[2] <= 1):
                raise ValueError(f"{name}: Bézier curves need x1 and x2 between 0 and 1")
        self.springs.validate()

    def commit(self):
        self.beziers.commit()
        self.springs.commit()


class EffectsPage(QWidget):
    """Edit named effect presets and pools in their respective TOML maps."""

    def __init__(self, doc):
        super().__init__()
        layout = QVBoxLayout(self)
        hint = QLabel(
            'A preset names one shader effect. Add a preset, choose its kind, and set its shader file '
            '(relative paths are resolved from the config file). To enable it, use the preset name in '
            'the matching [effects] selector, a window/output rule, or an animation event’s effect '
            'setting. A pool groups existing presets of the same kind: list their names under Choose, '
            'pick a selection policy, then select the pool name where you would select a preset. Umbriel '
            'chooses a pool member for each eligible window or output. Presets and pools need valid '
            'shader files and references; Save validation reports problems.'
        )
        hint.setWordWrap(True)
        hint_font = QFont(hint.font())
        hint_font.setPointSize(9)
        hint.setFont(hint_font)
        layout.addWidget(hint)
        self.tabs = QTabWidget()
        self.presets = EntryEditor(
            doc, "effects.preset", "map", EFFECT_PRESET_GROUPS, "Effect presets"
        )
        self.pools = EntryEditor(
            doc, "effects.pool", "map", EFFECT_POOL_GROUPS, "Effect pools"
        )
        self.tabs.addTab(self.presets, "Presets")
        self.tabs.addTab(self.pools, "Pools")
        layout.addWidget(self.tabs)

    def validate(self):
        self.presets.validate()
        self.pools.validate()

    def commit(self):
        self.presets.commit()
        self.pools.commit()

"""Keybind editor with GUI-only groups and locks."""

from . import state
from .common import (
    MISSING,
    QCheckBox,
    QCompleter,
    QFont,
    QHBoxLayout,
    QHeaderView,
    QInputDialog,
    QLabel,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QTableWidget,
    QTableWidgetItem,
    QTimer,
    QVBoxLayout,
    QWidget,
    Qt,
    WheelSafeComboBox,
    config_gui_data_dir,
    ensure_table,
    getp,
    json,
    migrate_gui_file,
    os,
    py,
    re,
    tomlkit,
    write_text_file,
)
from .tables import tidy_table
from .actions import (
    ACTION_INFO,
    ARG_HELP,
    REQUIRED_ARG_ACTIONS,
    build_action_model,
    migrate_action,
    reduce_template,
)


def lock_file():
    """Return the keybind-lock file under the GUI data directory."""
    return os.path.join(config_gui_data_dir(state.PATH), "gui-locked-keybinds.json")


def load_locked():
    """Return the set of keybind keys locked in the GUI."""
    migrate_gui_file(
        os.path.join(os.path.dirname(state.PATH), "gui-locked-keybinds.json"),
        lock_file(),
    )
    try:
        with open(lock_file(), encoding="utf-8") as f:
            return set(json.load(f))
    except (OSError, ValueError):
        return set()


def save_locked(keys):
    """Write locked keybind keys to GUI data without touching the Umbriel config."""
    try:
        write_text_file(lock_file(), json.dumps(sorted(keys), indent=1))
    except OSError as error:
        QMessageBox.warning(
            None,
            "Could not save keybind locks",
            f"Keybind lock state could not be saved: {error}",
        )


# Known per-bind options with their own columns (anything else is preserved untouched).
BIND_BOOL_OPTIONS = [("repeat", "Repeat"), ("allow_when_locked", "When locked"),
                     ("allow_when_inhibited", "When inhibited")]
KEYBIND_GROUPS_MARKER = "# Umbriel Config GUI keybind groups: "


def parse_keybind_groups(text):
    """Read GUI-only keybind groups from the TOML comment metadata."""
    metadata = {}
    for line in text.splitlines():
        if line.startswith(KEYBIND_GROUPS_MARKER):
            try:
                parsed = json.loads(line[len(KEYBIND_GROUPS_MARKER):])
            except json.JSONDecodeError:
                continue
            if isinstance(parsed, dict):
                metadata = parsed
    names = metadata.get("groups", [])
    groups = []
    if isinstance(names, list):
        groups.extend(
            name.strip() for name in names
            if isinstance(name, str) and name.strip()
        )
    assignments = metadata.get("assignments", {})
    if not isinstance(assignments, dict):
        assignments = {}
    for group in assignments.values():
        if isinstance(group, str) and group.strip() and group.strip() not in groups:
            groups.append(group.strip())
    return groups, {
        key: group.strip()
        for key, group in assignments.items()
        if isinstance(key, str) and isinstance(group, str) and group.strip()
    }


def write_keybind_groups(text, groups, assignments):
    """Persist keybind group labels in an ignored TOML comment inside [keybinds]."""
    newline = "\r\n" if "\r\n" in text else "\n"
    lines = text.splitlines(keepends=True)
    lines = [
        line for line in lines
        if not line.lstrip().startswith(KEYBIND_GROUPS_MARKER)
    ]
    groups = list(dict.fromkeys(group.strip() for group in groups if group.strip()))
    assignments = {
        key: group for key, group in assignments.items()
        if key and group in groups
    }
    if not groups and not assignments:
        return "".join(lines)

    section_header = re.compile(r"^\[keybinds\][ \t]*(?:#.*)?\r?\n?$")
    start = next(
        (index for index, line in enumerate(lines) if section_header.match(line)),
        None,
    )
    if start is None:
        if lines and not lines[-1].endswith(("\n", "\r")):
            lines[-1] += newline
        lines.append("[keybinds]" + newline)
        start = len(lines) - 1
    payload = json.dumps(
        {"groups": groups, "assignments": assignments},
        ensure_ascii=False,
        separators=(",", ":"),
    )
    lines.insert(start + 1, KEYBIND_GROUPS_MARKER + payload + newline)
    return "".join(lines)


class KeybindEditor(QWidget):
    """Keybind table with an action dropdown and a column for every per-bind option.

    Action: an editable dropdown listing all Umbriel actions (type to filter, or
    write your own, e.g. `spawn firefox`). Options: repeat, allow_when_locked,
    allow_when_inhibited, cooldown_ms and submap. Unknown extra keys on a bind
    are kept as they are.
    """

    HEADS = [
        "Key", "Group", "Action", "Repeat", "When locked", "When inhibited",
        "Cooldown (ms)", "Submap after", "Locked",
    ]

    def __init__(self, doc):
        """Build the keybind table, group controls, and action help."""
        super().__init__()
        self.doc, self.path = doc, ("keybinds",)
        self.model = build_action_model()
        self.locked = load_locked()
        lay = QVBoxLayout(self)
        group_bar = QHBoxLayout()
        group_bar.addWidget(QLabel("Show:"))
        self.group_filter = WheelSafeComboBox()
        self.group_filter.addItem("All groups")
        self.group_filter.currentTextChanged.connect(self.apply_group_filter)
        group_bar.addWidget(self.group_filter)
        self.new_group_btn = QPushButton("New group")
        self.rename_group_btn = QPushButton("Rename")
        self.delete_group_btn = QPushButton("Delete")
        self.new_group_btn.clicked.connect(self.create_group)
        self.rename_group_btn.clicked.connect(self.rename_group)
        self.delete_group_btn.clicked.connect(self.delete_group)
        group_bar.addWidget(self.new_group_btn)
        group_bar.addWidget(self.rename_group_btn)
        group_bar.addWidget(self.delete_group_btn)
        group_bar.addStretch()
        lay.addLayout(group_bar)
        self.t = QTableWidget(0, len(self.HEADS))
        tidy_table(self.t)
        self.t.setHorizontalHeaderLabels(self.HEADS)
        for column, description in enumerate((
            "Key or key combination that triggers this binding.",
            "Optional custom category for organizing keybinds; saved as GUI metadata in this config file.",
            "Action run when the key is pressed; type to search or enter a custom action.",
            "Repeat the action while the key is held.",
            "Allow this binding while the session is locked.",
            "Allow this binding when an application inhibits shortcuts.",
            "Minimum time between repeated activations, in milliseconds.",
            "Submap entered by this binding; use it to create multi-key shortcut groups.",
            "Prevent editing or removal of this binding in the GUI.",
        )):
            self.t.horizontalHeaderItem(column).setToolTip(description)
        for col, width in enumerate((150, 140, 300, 85, 100, 110, 110, 180, 70)):
            self.t.setColumnWidth(col, width)
        hdr = self.t.horizontalHeader()
        hdr.setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        hdr.setSectionResizeMode(2, hdr.ResizeMode.Stretch)
        self.t.currentCellChanged.connect(self.current_changed)
        lay.addWidget(self.t)
        self.move_up, self.move_down = QPushButton("↑"), QPushButton("↓")
        self.move_up.setToolTip("Move keybind up")
        self.move_down.setToolTip("Move keybind down")
        self.move_up.setEnabled(False)
        self.move_down.setEnabled(False)
        self.move_up.clicked.connect(lambda: self.move_selected(-1))
        self.move_down.clicked.connect(lambda: self.move_selected(1))
        self.desc = QLabel("Pick a row to see what its action does. Options left at \"-\" are not written (Umbriel's default applies).")
        self.desc.setWordWrap(True)
        desc_font = QFont(self.desc.font())
        desc_font.setPointSize(9)
        self.desc.setFont(desc_font)
        lay.addWidget(self.desc)
        row = QHBoxLayout()
        add, rem = QPushButton("Add"), QPushButton("Remove selected")
        duplicate = QPushButton("Duplicate selected")
        self.lock_all_btn = QPushButton("Lock all")
        self.lock_all_btn.clicked.connect(self.toggle_all_locks)
        add.clicked.connect(self.add_new_row)
        rem.clicked.connect(self.remove)
        duplicate.clicked.connect(self.duplicate_selected)
        row.addWidget(add)
        row.addWidget(rem)
        row.addWidget(duplicate)
        row.addWidget(self.lock_all_btn)
        row.addWidget(self.move_up)
        row.addWidget(self.move_down)
        row.addStretch()
        lay.addLayout(row)
        self.orig = {}
        self.migrated = 0
        self.pending_new_keys = []
        self.session_new_keys = set()
        self.group_names, self.group_assignments = parse_keybind_groups(doc.as_string())
        self.refresh_group_controls()
        kb = getp(doc, self.path)
        if kb is not MISSING:
            for k, v in kb.items():
                if isinstance(v, str):
                    a, o = str(v), {}
                else:
                    a, o = str(v.get("action", "")), {x: py(y) for x, y in v.items() if x != "action"}
                self.orig[str(k)] = (a, o)
                fixed = migrate_action(a)
                if fixed != a:
                    self.migrated += 1
                self.add_row(str(k), fixed, o, self.group_assignments.get(str(k), ""))
        self.apply_group_filter(self.group_filter.currentText())
        self.update_lock_all_button()
        if self.migrated:
            self.desc.setText(f"{self.migrated} keybind(s) used the old colon syntax and were converted "
                              "to the current one. Save to write the change.")

    def add_row(self, key, action, opts, group="", row=None):
        """Append a row: key text, action dropdown, option dropdowns, cooldown spinbox, submap text."""
        r = self.t.rowCount() if row is None else row
        self.t.insertRow(r)
        known = {k for k, _ in BIND_BOOL_OPTIONS} | {"cooldown_ms", "submap"}
        key_item = QTableWidgetItem(key)
        key_item.setData(Qt.ItemDataRole.UserRole, {k: v for k, v in opts.items() if k not in known})
        self.t.setItem(r, 0, key_item)
        group_box = WheelSafeComboBox()
        group_box.addItem("")
        group_box.addItems(self.group_names)
        group_box.setCurrentText(group if group in self.group_names else "")
        self.t.setCellWidget(r, 1, group_box)
        group_box.currentTextChanged.connect(
            lambda _text: self.apply_group_filter(self.group_filter.currentText())
        )
        cb = WheelSafeComboBox()
        cb.setEditable(True)
        cb.setModel(self.model)
        cb.setEditText(action)
        comp = QCompleter(self.model, cb)
        comp.setFilterMode(Qt.MatchFlag.MatchContains)
        comp.setCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
        cb.setCompleter(comp)
        cb.activated.connect(lambda i, cb=cb: self.picked(cb, cb.itemText(i)))
        comp.activated.connect(lambda txt, cb=cb: QTimer.singleShot(0, lambda: self.picked(cb, txt)))
        cb.editTextChanged.connect(lambda _t, cb=cb: self.show_desc(self.row_of(cb)))
        self.t.setCellWidget(r, 2, cb)
        for col, (name, _) in enumerate(BIND_BOOL_OPTIONS, start=3):
            c = WheelSafeComboBox()
            c.addItems(["-", "true", "false"])
            if name in opts:
                c.setCurrentIndex(1 if opts[name] else 2)
            self.t.setCellWidget(r, col, c)
        sp = QSpinBox()
        sp.setRange(0, 10000)
        sp.setSpecialValueText("off")
        sp.setValue(int(opts.get("cooldown_ms", 0)))
        self.t.setCellWidget(r, 6, sp)
        self.t.setItem(r, 7, QTableWidgetItem(str(opts.get("submap", ""))))
        lock = QCheckBox()
        lock.setToolTip("Locked binds cannot be edited or removed here until you untick this")
        lock.toggled.connect(lambda on, lock=lock: self.on_lock(lock, on))
        self.t.setCellWidget(r, 8, lock)
        if key in self.locked:
            lock.blockSignals(True)
            lock.setChecked(True)
            lock.blockSignals(False)
            self.set_row_locked(lock, True, persist=False, row=r)

    def add_new_row(self):
        """Add a blank binding, assigning it to the currently selected group when applicable."""
        group = self.group_filter.currentText()
        self.add_row("", "", {}, "" if group == "All groups" else group)
        self.update_lock_all_button()

    def refresh_group_controls(self):
        """Refresh group filters and row selectors while preserving current assignments."""
        selected_filter = self.group_filter.currentText()
        self.group_filter.blockSignals(True)
        self.group_filter.clear()
        self.group_filter.addItem("All groups")
        self.group_filter.addItems(self.group_names)
        self.group_filter.setCurrentText(
            selected_filter if selected_filter in self.group_names else "All groups"
        )
        self.group_filter.blockSignals(False)
        for row in range(self.t.rowCount()):
            box = self.t.cellWidget(row, 1)
            selected = box.currentText()
            box.blockSignals(True)
            box.clear()
            box.addItem("")
            box.addItems(self.group_names)
            box.setCurrentText(selected if selected in self.group_names else "")
            box.blockSignals(False)
        self.apply_group_filter(self.group_filter.currentText())

    def apply_group_filter(self, group):
        """Show all keybinds or only those assigned to the selected group."""
        if not hasattr(self, "t"):
            return
        selected_group = "" if group == "All groups" else group
        for row in range(self.t.rowCount()):
            self.t.setRowHidden(
                row,
                bool(selected_group) and self.t.cellWidget(row, 1).currentText() != selected_group,
            )
        if hasattr(self, "rename_group_btn"):
            self.rename_group_btn.setEnabled(bool(selected_group))
            self.delete_group_btn.setEnabled(bool(selected_group))

    def create_group(self):
        """Create a named keybind group."""
        name, accepted = QInputDialog.getText(self, "New keybind group", "Group name:")
        name = name.strip()
        if not accepted or not name:
            return
        if any(existing.casefold() == name.casefold() for existing in self.group_names):
            QMessageBox.warning(self, "Group already exists", f'A group named "{name}" already exists.')
            return
        self.group_names.append(name)
        self.refresh_group_controls()
        self.group_filter.setCurrentText(name)

    def rename_group(self):
        """Rename the group currently selected in the group filter."""
        old_name = self.group_filter.currentText()
        if old_name == "All groups":
            return
        new_name, accepted = QInputDialog.getText(
            self, "Rename keybind group", "New group name:", text=old_name
        )
        new_name = new_name.strip()
        if not accepted or not new_name:
            return
        if any(
            existing != old_name and existing.casefold() == new_name.casefold()
            for existing in self.group_names
        ):
            QMessageBox.warning(self, "Group already exists", f'A group named "{new_name}" already exists.')
            return
        self.group_names[self.group_names.index(old_name)] = new_name
        for row in range(self.t.rowCount()):
            box = self.t.cellWidget(row, 1)
            if box.currentText() == old_name:
                box.setCurrentText(new_name)
        self.refresh_group_controls()
        self.group_filter.setCurrentText(new_name)

    def delete_group(self):
        """Remove the selected group and unassign its keybinds."""
        name = self.group_filter.currentText()
        if name == "All groups":
            return
        answer = QMessageBox.question(
            self,
            "Delete keybind group",
            f'Delete "{name}"? Its keybinds will become ungrouped.',
            QMessageBox.StandardButton.Delete | QMessageBox.StandardButton.Cancel,
            QMessageBox.StandardButton.Cancel,
        )
        if answer != QMessageBox.StandardButton.Delete:
            return
        self.group_names.remove(name)
        for row in range(self.t.rowCount()):
            box = self.t.cellWidget(row, 1)
            if box.currentText() == name:
                box.setCurrentIndex(0)
        self.refresh_group_controls()

    def row_of(self, widget, col=2):
        """Return the table row holding `widget` in column `col` (rows shift when others are removed)."""
        for r in range(self.t.rowCount()):
            if self.t.cellWidget(r, col) is widget:
                return r
        return -1

    def on_lock(self, box, on):
        """Lock or unlock a row: grey out its inputs, remember the choice in the sidecar file."""
        self.set_row_locked(box, on)
        self.update_lock_all_button()

    def set_row_locked(self, box, on, persist=True, row=None):
        """Set a row's enabled state and optionally persist the lock sidecar."""
        r = self.row_of(box, 8) if row is None else row
        if r < 0:
            return
        key_item, sub_item = self.t.item(r, 0), self.t.item(r, 7)
        for col in range(2, 7):
            self.t.cellWidget(r, col).setEnabled(not on)
        self.t.cellWidget(r, 1).setEnabled(not on)
        for item in (key_item, sub_item):
            flags = item.flags() | Qt.ItemFlag.ItemIsEditable
            item.setFlags(flags & ~Qt.ItemFlag.ItemIsEditable if on else flags)
        key = key_item.text().strip()
        if key:
            (self.locked.add if on else self.locked.discard)(key)
            if persist:
                save_locked(self.locked)

    def update_lock_all_button(self):
        """Label the bulk lock control with the action it will perform."""
        locked = [
            self.t.cellWidget(row, 8).isChecked()
            for row in range(self.t.rowCount())
        ]
        self.lock_all_btn.setText("Unlock all" if locked and all(locked) else "Lock all")

    def toggle_all_locks(self):
        """Lock every binding, or unlock every binding when all are already locked."""
        if not self.t.rowCount():
            return
        lock_all = not all(
            self.t.cellWidget(row, 8).isChecked()
            for row in range(self.t.rowCount())
        )
        for row in range(self.t.rowCount()):
            box = self.t.cellWidget(row, 8)
            if box.isChecked() == lock_all:
                continue
            box.blockSignals(True)
            box.setChecked(lock_all)
            box.blockSignals(False)
            self.set_row_locked(box, lock_all, persist=False)
        save_locked(self.locked)
        self.update_lock_all_button()

    def picked(self, cb, text):
        """A dropdown entry was chosen: insert it, trimming optional/placeholder arguments so it is ready to edit."""
        if text.startswith("-- "):
            return
        cb.setEditText(reduce_template(text))
        self.desc.setText(self.describe(text))
        cb.lineEdit().setFocus()

    def describe(self, action):
        """Return a one-line explanation for an action string, plus a hint for its argument if it takes one."""
        head = action.split()[0] if action.split() else ""
        info = ACTION_INFO.get(head)
        if not info:
            return "Custom action. See docs.noctalia.dev/umbriel/actions for the full list."
        template, text = info
        args = template.partition(" ")[2]
        m = re.search(r"<([a-z-]+)", args)
        if m:
            text += f"\nArguments: {args}  -  {ARG_HELP.get(m.group(1), '')}"
        return f"{head}: {text}"

    def show_desc(self, r):
        """Update the description line for the action in row `r`."""
        if 0 <= r < self.t.rowCount():
            cb = self.t.cellWidget(r, 2)
            if cb is not None and cb.currentText().strip():
                self.desc.setText(self.describe(cb.currentText().strip()))

    def current_changed(self, row, *_):
        """Update the selected action description and row-move button states."""
        self.show_desc(row)
        self.move_up.setEnabled(row > 0)
        self.move_down.setEnabled(0 <= row < self.t.rowCount() - 1)

    def move_selected(self, offset):
        """Move one row without rebuilding the other keybind widgets."""
        row = self.t.currentRow()
        target = row + offset
        if not 0 <= row < self.t.rowCount() or not 0 <= target < self.t.rowCount():
            return
        key = self.t.item(row, 0).text() if self.t.item(row, 0) else ""
        action = self.t.cellWidget(row, 2).currentText()
        group = self.t.cellWidget(row, 1).currentText()
        options = self.row_opts(row)
        locked = self.t.cellWidget(row, 8).isChecked()
        self.t.removeRow(row)
        if locked and key:
            self.locked.add(key)
        self.add_row(key, action, options, group, row=target)
        if locked:
            self.locked.add(key)
            self.t.cellWidget(target, 8).setChecked(True)
        self.update_lock_all_button()
        self.t.setCurrentCell(target, 0)
        self.apply_group_filter(self.group_filter.currentText())

    def remove(self):
        """Remove the selected rows, skipping locked ones (untick Locked first to delete those)."""
        skipped = 0
        for r in sorted({i.row() for i in self.t.selectedIndexes()}, reverse=True):
            if self.t.cellWidget(r, 8).isChecked():
                skipped += 1
            else:
                self.t.removeRow(r)
        if skipped:
            self.desc.setText(f"{skipped} locked bind(s) were not removed. Untick Locked to delete them.")
        self.update_lock_all_button()

    def duplicate_selected(self):
        """Copy the selected binding's action and options under a new shortcut."""
        row = self.t.currentRow()
        if not 0 <= row < self.t.rowCount():
            return
        source_key = self.t.item(row, 0).text().strip()
        key, accepted = QInputDialog.getText(
            self, "Duplicate keybind", "New shortcut (for example Super+Shift+Q):"
        )
        key = key.strip()
        if not accepted or not key:
            return
        normalized = " ".join(key.casefold().split())
        existing = {
            " ".join(
                (self.t.item(index, 0).text() if self.t.item(index, 0) else "").casefold().split()
            )
            for index in range(self.t.rowCount())
        }
        if normalized in existing:
            QMessageBox.warning(self, "Shortcut already exists", f'"{key}" is already in use.')
            return
        action = self.t.cellWidget(row, 2).currentText()
        group = self.t.cellWidget(row, 1).currentText()
        self.add_row(key, action, self.row_opts(row), group)
        self.update_lock_all_button()
        self.t.setCurrentCell(self.t.rowCount() - 1, 0)
        self.desc.setText(f'Duplicated "{source_key}" as "{key}".')

    def row_opts(self, r):
        """Collect the option columns of row `r` into a dict (unset options are left out, unknown extras are kept)."""
        o = {}
        for col, (name, _) in enumerate(BIND_BOOL_OPTIONS, start=3):
            idx = self.t.cellWidget(r, col).currentIndex()
            if idx:
                o[name] = idx == 1
        if self.t.cellWidget(r, 6).value():
            o["cooldown_ms"] = self.t.cellWidget(r, 6).value()
        sub = self.t.item(r, 7).text().strip() if self.t.item(r, 7) else ""
        if sub:
            o["submap"] = sub
        o.update(self.t.item(r, 0).data(Qt.ItemDataRole.UserRole) or {})
        return o

    def rows(self):
        """Read the table into {key: (action, options)}, skipping rows without a key or action."""
        out = {}
        for r in range(self.t.rowCount()):
            k = self.t.item(r, 0).text().strip() if self.t.item(r, 0) else ""
            a = self.t.cellWidget(r, 2).currentText().strip()
            if k and a:
                out[k] = (a, self.row_opts(r))
        return out

    def validate(self):
        """Reject conflicting shortcuts and incomplete actions."""
        seen = {}
        for row in range(self.t.rowCount()):
            key = self.t.item(row, 0).text().strip() if self.t.item(row, 0) else ""
            if not key:
                continue
            normalized = " ".join(key.casefold().split())
            if normalized in seen:
                raise ValueError(
                    f'Keybind conflict: "{key}" duplicates shortcut "{seen[normalized]}".'
                )
            seen[normalized] = key
        for k, (a, _) in self.rows().items():
            words = a.split()
            if words and words[0] == "spawn" and (len(words) == 1 or a.strip() == "spawn <cmd...>"):
                raise ValueError(f'Keybind "{k}": write a command after "spawn".')
            if re.search(r"<[^>]+>", a) and words and words[0] != "spawn":
                raise ValueError(f'Keybind "{k}": "{a}" still needs its argument (replace the <...> part).')
            if len(words) == 1 and words[0] in REQUIRED_ARG_ACTIONS:
                raise ValueError(f'Keybind "{k}": "{a}" needs an argument, e.g. "{ACTION_INFO[words[0]][0]}".')

    def commit(self):
        """Write only changed/added/removed binds into [keybinds]; untouched lines keep their formatting."""
        rows = self.rows()
        if not rows and getp(self.doc, self.path) is MISSING and not self.group_names:
            return
        # The in-memory TOML document never holds the relocated position (it is only fixed in the
        # saved text), so keys added in this session must be re-placed on EVERY save, not only the first.
        self.session_new_keys.update(key for key in rows if key not in self.orig)
        self.pending_new_keys = [key for key in rows if key in self.session_new_keys]
        tbl = ensure_table(self.doc, self.path)
        for k in list(tbl.keys()):
            if k not in rows and k not in self.locked:  # locked binds are never deleted
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
        self.reorder_table(tbl, list(rows))
        self.orig = rows
        self.group_assignments = {}
        for row in range(self.t.rowCount()):
            key = self.t.item(row, 0).text().strip()
            group = self.t.cellWidget(row, 1).currentText()
            if key in rows and group:
                self.group_assignments[key] = group

    def reorder_table(self, table, order):
        """Reorder key/value slots to match the editor while keeping comments in place."""
        container = table.value
        body = container.body
        entries = {key.key: (key, value) for key, value in body if key is not None}
        positions = [index for index, (key, _) in enumerate(body) if key is not None]
        ordered_keys = [key for key in order if key in entries]
        ordered_keys.extend(key for key in container.keys() if key not in ordered_keys)
        if not positions or ordered_keys == [key.key for key, _ in body if key is not None]:
            return
        values = {key: dict.__getitem__(container, key) for key in ordered_keys}
        for position, key_name in zip(positions, ordered_keys):
            body[position] = entries[key_name]
        container._map.clear()
        for index, (key, _) in enumerate(body):
            if key is not None:
                container._map[key] = index
        dict.clear(container)
        for key_name in ordered_keys:
            dict.__setitem__(container, key_name, values[key_name])

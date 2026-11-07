"""Specialized editors for rules, keybinds, effects, and desktop associations."""

from . import state
from .common import (
    MISSING,
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFont,
    QGridLayout,
    QInputDialog,
    QLabel,
    QLineEdit,
    QListWidget,
    QMessageBox,
    QPalette,
    QPushButton,
    QScrollArea,
    QSplitter,
    QVBoxLayout,
    QWidget,
    Qt,
    copy,
    ensure_table,
    getp,
    json,
    load_entry_labels,
    putp,
    save_entry_labels,
    shutil,
    subprocess,
    tomlkit,
    totext,
)
from .settings import (
    apply_fields,
    form_page,
)


class EntryEditor(QWidget):
    """Edits [[array_of_tables]] (mode 'aot') or [table.<name>] maps (mode 'map')."""

    def __init__(self, doc, path, mode, groups, title, collapsible=True):
        """Build the list on the left and the form area on the right. `path` locates the rules in the config; `mode` is 'aot' for [[rules]] or 'map' for [table.name] entries."""
        super().__init__()
        self.doc, self.path, self.mode = doc, tuple(path.split(".")), mode
        self.groups, self.collapsible, self.title = groups, collapsible, title
        if mode == "map":
            self.schema_prefix = ".".join(self.path) + ".<name>"
        else:
            self.schema_prefix = ".".join(self.path) + "[]"
        self.category = {
            "Outputs (connector or monitor)": "Outputs",
            "[[window_rule]]": "Window rules",
            "[[layer_rule]]": "Layer rules",
            "[[workspace]]": "Workspace rules",
            "[[security_context_rule]]": "Security rules",
            "[[scratchpad]]": "Scratchpads",
            "[[input.device]]": "Input devices",
        }.get(title, title)
        self.config_path = state.PATH
        self.labels_key = ".".join(self.path)
        self.custom_labels = load_entry_labels(self.config_path, self.labels_key) if mode == "aot" else []
        self.fws, self.cur = [], -1
        split = QSplitter()
        split.setCollapsible(0, False)
        left = QWidget()
        self.left_panel = left
        lv = QVBoxLayout(left)
        heading = QLabel(title)
        heading_font = QFont(heading.font())
        heading_font.setBold(True)
        heading_font.setPointSize(13)
        heading.setFont(heading_font)
        lv.addWidget(heading)
        if self.path == ("output",) and mode == "map":
            output_help = QLabel(
                "Inspect connected displays to see their supported modes and suggested config keys. "
                "Use the monitor identity to follow a display between ports, or its connector name "
                "to target a physical port."
            )
            output_help.setWordWrap(True)
            output_help.setForegroundRole(QPalette.ColorRole.PlaceholderText)
            output_help_font = QFont(output_help.font())
            output_help_font.setPointSize(9)
            output_help.setFont(output_help_font)
            lv.addWidget(output_help)
            inspect_button = QPushButton("Inspect connected outputs…")
            inspect_button.clicked.connect(self.inspect_outputs)
            lv.addWidget(inspect_button)
        self.list = QListWidget()
        self.list.setSpacing(2)
        self.list.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        lv.addWidget(self.list)
        row = QGridLayout()
        row.setContentsMargins(0, 0, 0, 0)
        row.setHorizontalSpacing(4)
        row.setVerticalSpacing(4)
        add, rem = QPushButton("Add"), QPushButton("Remove")
        self.duplicate_button = QPushButton("Duplicate")
        self.rename_button = QPushButton("Rename")
        self.move_up, self.move_down = QPushButton("↑"), QPushButton("↓")
        self.duplicate_button.setToolTip("Create a copy of the selected rule or table")
        self.rename_button.setToolTip("Set a GUI-only label for the selected rule")
        self.move_up.setToolTip("Move entry up (rules are applied in order)")
        self.move_down.setToolTip("Move entry down (rules are applied in order)")
        add.clicked.connect(self.add)
        rem.clicked.connect(self.remove)
        self.duplicate_button.clicked.connect(self.duplicate)
        self.rename_button.clicked.connect(self.rename)
        self.move_up.clicked.connect(lambda: self.move(-1))
        self.move_down.clicked.connect(lambda: self.move(1))
        row.addWidget(add, 0, 0)
        row.addWidget(rem, 0, 1)
        row.addWidget(self.duplicate_button, 0, 2)
        if mode == "aot":
            row.addWidget(self.rename_button, 1, 0)
            row.addWidget(self.move_up, 1, 1)
            row.addWidget(self.move_down, 1, 2)
        lv.addLayout(row)
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        split.addWidget(left)
        split.addWidget(self.scroll)
        split.setStretchFactor(0, 0)
        split.setStretchFactor(1, 1)
        QVBoxLayout(self).addWidget(split)
        self.refresh()
        self.list.currentRowChanged.connect(self.select)

    def size_entry_list(self):
        """Fit the fixed left pane to its longest entry label and controls."""
        labels = [self.list.item(i).text() for i in range(self.list.count())]
        labels.append(self.left_panel.findChild(QLabel).text())
        text_width = max(self.list.fontMetrics().horizontalAdvance(label) for label in labels)
        list_width = text_width + 40
        self.list.setFixedWidth(list_width)
        layout = self.left_panel.layout()
        margins = layout.contentsMargins()
        pane_width = max(list_width, layout.sizeHint().width() - margins.left() - margins.right())
        self.left_panel.setFixedWidth(pane_width + margins.left() + margins.right())

    # container access
    def container(self, create=False):
        """Return the config object holding the entries (an array of tables or a table of tables), optionally creating it."""
        c = getp(self.doc, self.path)
        if c is MISSING and create:
            c = tomlkit.aot() if self.mode == "aot" else ensure_table(self.doc, self.path)
            if self.mode == "aot":
                putp(self.doc, self.path, c)
        return None if c is MISSING else c

    def entries(self):
        """List the current entries as tables ('aot') or (name, table) pairs ('map')."""
        c = self.container()
        if c is None:
            return []
        return list(c) if self.mode == "aot" else list(c.items())

    def entry(self, i):
        """Return the table for the entry at list position `i`."""
        e = self.entries()[i]
        return e if self.mode == "aot" else e[1]

    def label(self, i):
        """Text shown in the entry list: the output name, or the first identifying key of a rule (name, app_id, title, namespace)."""
        if self.mode == "map":
            return str(self.entries()[i][0])
        if i < len(self.custom_labels) and self.custom_labels[i].strip():
            return f"{i + 1}. {self.custom_labels[i].strip()}"
        e = self.entry(i)
        for p in (("name",), ("match", "app_id"), ("match", "title"), ("match", "namespace"), ("index",)):
            v = getp(e, p)
            if v is not MISSING:
                return f"{i + 1}. {'.'.join(p)} = {totext(v)}"
        m = getp(e, ("match",))  # other matchers, e.g. match.is_focused
        if m is not MISSING and len(m):
            k = next(iter(m))
            return f"{i + 1}. match.{k} = {totext(m[k])}"
        return f"{i + 1}. (matches everything)"

    def refresh(self, select=0):
        """Rebuild the entry list from the config and select entry number `select`."""
        if self.mode == "aot":
            count = len(self.entries())
            self.custom_labels = (self.custom_labels + [""] * count)[:count]
        self.list.blockSignals(True)
        self.list.clear()
        self.list.addItems([self.label(i) for i in range(len(self.entries()))])
        self.list.blockSignals(False)
        self.size_entry_list()
        self.cur = -1
        if self.list.count():
            self.list.setCurrentRow(min(select, self.list.count() - 1))
            self.select(self.list.currentRow())
        else:
            self.rename_button.setEnabled(False)
            self.move_up.setEnabled(False)
            self.move_down.setEnabled(False)
            self.scroll.setWidget(QWidget())

    def select(self, i):
        """Save the entry being edited, then load the form for entry `i`."""
        self.commit()
        self.cur = i
        self.rename_button.setEnabled(self.mode == "aot" and i >= 0)
        self.move_up.setEnabled(self.mode == "aot" and i > 0)
        self.move_down.setEnabled(self.mode == "aot" and 0 <= i < len(self.entries()) - 1)
        self.fws = []
        if i < 0:
            return
        e = self.entry(i)
        self.scroll.setWidget(
            form_page(
                self.groups,
                e,
                self.fws,
                self.collapsible,
                getattr(self, "category", self.title),
                self.schema_prefix,
            )
        )

    def move(self, offset):
        """Move the selected array entry up or down by one position."""
        i = self.list.currentRow()
        target = i + offset
        c = self.container()
        if self.mode != "aot" or i < 0 or not 0 <= target < len(c):
            return
        self.commit()
        self.fws, self.cur = [], -1
        entry = c.pop(i)
        c.insert(target, entry)
        label = self.custom_labels.pop(i)
        self.custom_labels.insert(target, label)
        self.save_labels()
        self.refresh(target)

    def rename(self):
        """Set or clear the selected entry's GUI-only display name."""
        i = self.list.currentRow()
        if self.mode != "aot" or i < 0:
            return
        name, ok = QInputDialog.getText(
            self, "Rename entry", "Display name (blank uses the automatic name):",
            QLineEdit.EchoMode.Normal, self.custom_labels[i],
        )
        if not ok:
            return
        self.custom_labels[i] = name.strip()
        self.save_labels()
        self.list.item(i).setText(self.label(i))
        self.size_entry_list()

    def save_labels(self):
        """Persist custom names, reporting sidecar write failures without affecting the TOML config."""
        try:
            save_entry_labels(self.config_path, self.labels_key, self.custom_labels)
        except OSError as e:
            QMessageBox.warning(self, "Could not save display name", str(e))

    def validate(self):
        """Check that all fields of the open entry parse correctly, without changing anything (raises ValueError if not)."""
        for fw in self.fws:
            fw.get()

    def commit(self):
        """Write the open entry's form values into the config and refresh its list label."""
        if 0 <= self.cur < len(self.entries()) and self.fws:
            apply_fields(self.entry(self.cur), self.fws)
            item = self.list.item(self.cur)
            if item:
                item.setText(self.label(self.cur))
                self.size_entry_list()

    def inspect_outputs(self):
        """Discover live output modes and optionally add the selected mode to the config."""
        executable = shutil.which("umbriel")
        if not executable:
            QMessageBox.warning(
                self, "Umbriel not found",
                "Install Umbriel or add its executable to PATH to inspect connected outputs.",
            )
            return
        try:
            result = subprocess.run(
                [executable, "outputs", "--json"],
                capture_output=True,
                text=True,
                timeout=5,
                check=False,
            )
        except subprocess.TimeoutExpired:
            QMessageBox.warning(
                self, "Output inspection timed out",
                "`umbriel outputs --json` did not finish within 5 seconds. "
                "Make sure Umbriel is running in the active session and try again.",
            )
            return
        except OSError as error:
            QMessageBox.warning(self, "Could not inspect outputs", str(error))
            return
        if result.returncode:
            detail = result.stderr.strip() or result.stdout.strip() or f"exit status {result.returncode}"
            QMessageBox.warning(
                self, "Could not inspect outputs",
                f"`umbriel outputs --json` failed: {detail}",
            )
            return
        try:
            outputs = json.loads(result.stdout)
        except json.JSONDecodeError as error:
            QMessageBox.warning(
                self, "Invalid output data",
                f"`umbriel outputs --json` returned invalid JSON: {error}",
            )
            return
        if not isinstance(outputs, list) or any(
            not isinstance(output, dict) or not isinstance(output.get("name"), str)
            for output in outputs
        ):
            QMessageBox.warning(
                self, "Unexpected output data",
                "`umbriel outputs --json` returned an unexpected output list.",
            )
            return
        if not outputs:
            QMessageBox.information(
                self, "No connected outputs",
                "Umbriel did not report any outputs. Make sure it is running in the session "
                "whose displays you want to configure.",
            )
            return
        self.show_output_inspector(outputs)

    def show_output_inspector(self, outputs):
        """Present discovered output identities and modes in a small setup dialog."""
        dialog = QDialog(self)
        dialog.setWindowTitle("Inspect connected outputs")
        dialog.setMinimumWidth(560)
        dialog.resize(700, 460)
        layout = QVBoxLayout(dialog)
        layout.setContentsMargins(18, 16, 18, 14)
        layout.setSpacing(10)
        layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        intro = QLabel(
            "Choose a connected output and one of its advertised modes. Adding the mode "
            "creates or updates an [output.<name>] entry; other settings in that entry are kept."
        )
        intro.setWordWrap(True)
        intro_font = QFont(intro.font())
        intro_font.setPointSize(9)
        intro.setFont(intro_font)
        layout.addWidget(intro)

        def add_selector(label, picker, minimum_length):
            """Add a compact, full-width labeled selector."""
            title = QLabel(label)
            picker.setSizeAdjustPolicy(
                QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon
            )
            picker.setMinimumContentsLength(minimum_length)
            picker.setToolTip(label)
            layout.addWidget(title)
            layout.addWidget(picker)

        output_picker = QComboBox()
        for output in outputs:
            name = output["name"]
            identity = output.get("config_name")
            label = f"{name} — {identity}" if isinstance(identity, str) and identity else name
            output_picker.addItem(label, output)
            output_picker.setItemData(output_picker.count() - 1, label, Qt.ItemDataRole.ToolTipRole)
        add_selector("Connected output", output_picker, 32)
        details = QLabel()
        details.setWordWrap(True)
        details.setMinimumHeight(details.fontMetrics().height() * 2)
        details.setForegroundRole(QPalette.ColorRole.PlaceholderText)
        details.setFont(intro_font)
        layout.addWidget(QLabel("Current state"))
        layout.addWidget(details)
        key_picker = QComboBox()
        add_selector("Config entry key", key_picker, 38)
        mode_picker = QComboBox()
        add_selector("Mode", mode_picker, 24)
        enable_output = QCheckBox("Set enabled = true")
        layout.addWidget(enable_output)
        identity_help = QLabel(
            "Monitor identity follows the same display when it moves to another port. "
            "Connector name targets a physical port."
        )
        identity_help.setWordWrap(True)
        identity_help.setForegroundRole(QPalette.ColorRole.PlaceholderText)
        identity_help.setFont(intro_font)
        layout.addWidget(identity_help)
        layout.addStretch(1)
        buttons = QDialogButtonBox()
        apply_button = buttons.addButton(
            "Add or update entry", QDialogButtonBox.ButtonRole.AcceptRole
        )
        buttons.addButton(QDialogButtonBox.StandardButton.Close)
        buttons.rejected.connect(dialog.reject)
        layout.addWidget(buttons)

        def update_output(index):
            output = output_picker.itemData(index)
            if not isinstance(output, dict):
                return
            name = output["name"]
            identity = output.get("config_name")
            identity = identity if isinstance(identity, str) and identity.strip() else None
            existing = {
                str(key).casefold(): str(key)
                for key in (entry[0] for entry in self.entries())
                if str(key).casefold() in {
                    name.casefold(),
                    identity.casefold() if identity else "",
                }
            }
            key_picker.clear()
            keys = []
            if identity:
                keys.append((identity, "monitor identity"))
            keys.append((name, "connector"))
            added = set()
            for key, kind in keys:
                folded = key.casefold()
                if folded in added:
                    continue
                added.add(folded)
                configured_key = existing.get(folded)
                suffix = " — existing entry" if configured_key else f" — {kind}"
                key_picker.addItem(f"{configured_key or key}{suffix}", configured_key or key)

            modes = output.get("modes", [])
            if not isinstance(modes, list):
                modes = []
            modes = [
                mode for mode in modes
                if isinstance(mode, dict)
                and isinstance(mode.get("width"), int)
                and isinstance(mode.get("height"), int)
                and isinstance(mode.get("refresh_mhz"), (int, float))
                and mode["width"] > 0
                and mode["height"] > 0
                and mode["refresh_mhz"] > 0
            ]
            modes.sort(
                key=lambda mode: (
                    not bool(mode.get("current")),
                    not bool(mode.get("preferred")),
                )
            )
            mode_picker.clear()
            for mode in modes:
                refresh = mode["refresh_mhz"] / 1000
                value = f'{mode["width"]}x{mode["height"]}@{refresh:g}'
                labels = []
                if mode.get("current"):
                    labels.append("current")
                if mode.get("preferred"):
                    labels.append("preferred")
                suffix = f" ({', '.join(labels)})" if labels else ""
                mode_picker.addItem(value + suffix, value)
            current_mode = next((mode for mode in modes if mode.get("current")), None)
            current_text = (
                f'{current_mode["width"]}x{current_mode["height"]}'
                f'@{current_mode["refresh_mhz"] / 1000:g}'
                if current_mode else "not reported"
            )
            position = output.get("position")
            if isinstance(position, dict) and {"x", "y"} <= position.keys():
                position_text = f'{position["x"]}, {position["y"]}'
            elif isinstance(position, list) and len(position) == 2:
                position_text = f"{position[0]}, {position[1]}"
            else:
                position_text = "not reported"
            scale = output.get("scale")
            scale_text = str(scale) if isinstance(scale, (int, float)) else "not reported"
            enabled = output.get("enabled")
            state_text = "enabled" if enabled is True else "disabled" if enabled is False else "state unknown"
            details.setText(
                f"{state_text}; current mode {current_text}; position {position_text}; scale {scale_text}."
            )
            enable_output.setChecked(enabled is False)
            enable_output.setVisible(enabled is False)
            if not modes:
                mode_picker.addItem("No supported modes reported", None)
                apply_button.setEnabled(False)
            else:
                apply_button.setEnabled(True)

        def apply_output():
            output = output_picker.currentData()
            key = key_picker.currentData()
            mode = mode_picker.currentData()
            if not isinstance(output, dict) or not isinstance(key, str) or not isinstance(mode, str):
                QMessageBox.warning(
                    dialog, "Cannot configure output",
                    "Select an output with a supported mode before adding a config entry.",
                )
                return
            try:
                self.commit()
                entries = self.container(True)
                entry = entries.get(key)
                if entry is None:
                    entry = tomlkit.table()
                    entries[key] = entry
                entry["mode"] = mode
                if enable_output.isChecked():
                    entry["enabled"] = True
                self.refresh(list(entries).index(key))
            except (KeyError, TypeError, ValueError) as error:
                QMessageBox.warning(
                    dialog, "Could not update output entry", str(error)
                )
                return
            window = self.window()
            if hasattr(window, "mark_dirty"):
                window.mark_dirty()
            dialog.accept()

        output_picker.currentIndexChanged.connect(update_output)
        apply_button.clicked.connect(apply_output)
        update_output(output_picker.currentIndex())
        dialog.exec()

    def add(self):
        """Add a new empty entry: an empty [[rule]] or a named table that you are prompted for."""
        self.commit()
        if self.mode == "aot":
            c = self.container(True)
            c.append(tomlkit.table())
            self.custom_labels.append("")
            self.save_labels()
        else:
            name, ok = QInputDialog.getText(self, "New entry", "Name (e.g. DP-1 or monitor identity):")
            if not ok or not name.strip():
                return
            self.container(True)[name.strip()] = tomlkit.table()
        self.refresh(len(self.entries()) - 1)

    def duplicate(self):
        """Create a copy of the selected rule or named table."""
        index = self.list.currentRow()
        if index < 0:
            return
        self.commit()
        source = self.entry(index)
        clone = copy.deepcopy(source)
        if self.mode == "aot":
            container = self.container(True)
            container.insert(index + 1, clone)
            self.custom_labels.insert(index + 1, "")
            self.save_labels()
        else:
            existing_names = {str(name) for name, _ in self.entries()}
            name, accepted = QInputDialog.getText(
                self, "Duplicate entry", "Name for the copy:"
            )
            name = name.strip()
            if not accepted or not name:
                return
            if name in existing_names:
                QMessageBox.warning(self, "Already exists", f'"{name}" already exists.')
                return
            self.container(True)[name] = clone
            index = len(self.entries()) - 1
        self.refresh(index + 1 if self.mode == "aot" else index)

    def remove(self):
        """Delete the selected entry from the config."""
        i = self.list.currentRow()
        if i < 0:
            return
        answer = QMessageBox.question(
            self,
            "Remove entry",
            f"Remove {self.label(i)} from {self.title}?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.Cancel,
            QMessageBox.StandardButton.Cancel,
        )
        if answer != QMessageBox.StandardButton.Yes:
            return
        self.fws, self.cur = [], -1
        c = self.container()
        if self.mode == "aot":
            del c[i]
            self.custom_labels.pop(i)
            self.save_labels()
        else:
            del c[self.entries()[i][0]]
        self.refresh(max(0, i - 1))

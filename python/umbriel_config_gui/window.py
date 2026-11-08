"""Main window, save/validation workflow, and application entry point."""

from . import state
from .qt6ct_theme import Qt6ctThemeFollower
from .common import (
    APP_NAME,
    BANNER_RE,
    ConfigLoadError,
    QApplication,
    QBrush,
    QCheckBox,
    QColor,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFileDialog,
    QFont,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMessageBox,
    QPalette,
    QPlainTextEdit,
    QProcess,
    QPushButton,
    QSpinBox,
    QTabWidget,
    QTableWidget,
    QTimer,
    QVBoxLayout,
    QWidget,
    Qt,
    add_entry_name_comments,
    PaletteReadability,
    apply_interaction_styles,
    config_gui_data_dir,
    config_fingerprint,
    create_app_icon,
    create_backup_snapshot,
    difflib,
    header_path,
    inline_window_rule_matches,
    install_desktop_icon,
    json,
    load_saved_config_path,
    migrate_gui_directory,
    migrate_gui_file,
    move_new_keybinds,
    normalize_config_path,
    os,
    parse_cli_args,
    persist_config_path,
    re,
    read_config_state,
    rebuild_config,
    shutil,
    subprocess,
    sys,
    tomlkit,
    write_text_file,
)
from .editors import EntryEditor
from .desktop import DefaultApps, UserDirs
from .keybinds import KeybindEditor, write_keybind_groups
from .sidebar import SideTabs, load_sidebar_order
from .tables import AnimationCurvesPage, EffectsPage, KVTable
from .field_defs import (
    INPUT_DEVICE,
    LAYER_RULE,
    OUTPUT_GROUPS,
    SCRATCHPAD,
    SECURITY_RULE,
    TABS,
    WINDOW_RULE_GROUPS,
    WORKSPACE_RULE_GROUPS,
)
from .schema import check_schema_coverage, load_umbriel_schema
from .settings import (
    FieldWidget,
    SIDEBAR_SECTIONS,
    apply_fields,
    form_page,
)
from .widgets import TriStateControl

def group_diff_by_section(diff, new_text):
    """Split unified-diff hunks by the TOML section containing their new lines."""
    section_by_line = {}
    section = "Top-level settings"
    for line_number, line in enumerate(new_text.splitlines(), start=1):
        if line.lstrip().startswith("["):
            try:
                path, is_array = header_path(line)
            except (tomlkit.exceptions.TOMLKitError, ValueError):
                path, is_array = (), False
            if path:
                section = ("[[" if is_array else "[") + ".".join(map(str, path)) + ("]]" if is_array else "]")
        section_by_line[line_number] = section

    groups = {}
    lines = diff.splitlines(keepends=True)
    index = 0
    while index < len(lines):
        if not lines[index].startswith("@@ "):
            index += 1
            continue
        hunk = [lines[index]]
        match = re.search(r"\+(\d+)(?:,\d+)?", lines[index])
        new_start = int(match.group(1)) if match else 1
        index += 1
        while index < len(lines) and not lines[index].startswith("@@ "):
            if not lines[index].startswith(("--- ", "+++ ")):
                hunk.append(lines[index])
            index += 1

        current_section = section_by_line.get(max(1, new_start), section)
        current_line = max(1, new_start)
        section_hunks = {}
        for diff_line in hunk[1:]:
            prefix = diff_line[:1]
            content = diff_line[1:] if prefix in (" ", "+", "-") else diff_line
            if prefix in (" ", "+"):
                current_section = section_by_line.get(current_line, current_section)
                current_line += 1
            elif prefix == "-" and content.lstrip().startswith("["):
                try:
                    old_path, old_array = header_path(content)
                except (tomlkit.exceptions.TOMLKitError, ValueError):
                    old_path, old_array = (), False
                if old_path:
                    current_section = "Removed " + (
                        ("[[" if old_array else "[") + ".".join(map(str, old_path))
                        + ("]]" if old_array else "]")
                    )
            section_hunks.setdefault(current_section, []).append(diff_line)
        for name, section_lines in section_hunks.items():
            groups.setdefault(name, []).extend([hunk[0], *section_lines, "\n"])
    return groups


# ----------------------------------------------------------------- main window
class Window(QMainWindow):
    """Main window: one tab per settings area plus the Save/Reload buttons."""
    def __init__(self, config_path=None):
        """Load the config, build every tab and editor, and add the bottom bar (status text, validate checkbox, Save)."""
        super().__init__()
        cli_explicit = state._CLI_ARGS.config is not None or state._CLI_ARGS.config_option is not None
        if config_path is not None:
            self.config_path = normalize_config_path(config_path)
        else:
            self.config_path = state.PATH if cli_explicit else load_saved_config_path(state.PATH)
        state.PATH = self.config_path
        config_data_dir = config_gui_data_dir(state.PATH)
        migrate_gui_file(
            state.PATH + ".bak", os.path.join(config_data_dir, "config.bak")
        )
        migrate_gui_directory(
            state.PATH + ".backups", os.path.join(config_data_dir, "backups")
        )
        self.setWindowIcon(create_app_icon())
        self.setWindowTitle(f"{APP_NAME} - {state.PATH}")
        self.resize(1920, 1080)
        app = QApplication.instance()
        if app is not None:
            app_font = QFont(app.font())
            app_font.setPointSize(10)
            app.setFont(app_font)
            self.setFont(app_font)
        self.doc, self._disk_fingerprint = load_config_snapshot(self.config_path)
        try:
            self.schema = load_umbriel_schema()
            state.ACTIVE_SCHEMA_OPTIONS = {
                option["path"]: option
                for option in self.schema["options"]
                if isinstance(option, dict) and isinstance(option.get("path"), str)
            }
            schema_version = str(self.schema.get("version", "unknown version"))
            schema_revision = self.schema.get("revision")
            suffix = f" ({schema_revision})" if schema_revision else ""
            self.schema_status_text = f"Loaded Umbriel schema: {schema_version}{suffix}."
        except (FileNotFoundError, RuntimeError, ValueError, subprocess.TimeoutExpired) as error:
            self.schema = None
            state.ACTIVE_SCHEMA_OPTIONS = {}
            self.schema_status_text = f"Schema metadata unavailable: {error}"
        self._external_change_detected = False
        self.fws, self.editors = [], []
        self._dirty = False

        central = QWidget()
        central.setObjectName("centralWidget")
        central.setAutoFillBackground(True)
        self.setCentralWidget(central)
        root = QVBoxLayout(central)
        root.setContentsMargins(12, 10, 12, 10)
        root.setSpacing(8)
        schema_bar = QHBoxLayout()
        self.schema_status = QLabel(self.schema_status_text)
        self.schema_status.setWordWrap(True)
        self.schema_status.setForegroundRole(QPalette.ColorRole.PlaceholderText)
        self.schema_check_button = QPushButton("Schema coverage...")
        self.schema_check_button.clicked.connect(self.show_schema_coverage)
        schema_bar.addWidget(self.schema_status, 1)
        schema_bar.addWidget(self.schema_check_button)
        root.addLayout(schema_bar)
        tabs = SideTabs()
        self.side_tabs = tabs
        root.addWidget(tabs, 1)

        def settings_page_factory(name, groups):
            def build():
                page = form_page(groups, self.doc, self.fws, category=name)
                self.track_page_changes(page)
                return page
            return build

        settings_pages = {
            name: settings_page_factory(name, groups)
            for name, groups in TABS.items()
        }
        editor_factories = {}
        built_editors = {}

        def add_editor(tab, factory):
            def build():
                widget = factory()
                if isinstance(widget, EntryEditor):
                    widget.category = tab
                built_editors[tab] = widget
                self.editors[:] = [
                    built_editors[name] for name in editor_factories if name in built_editors
                ]
                self.track_page_changes(widget)
                return widget
            editor_factories[tab] = build

        add_editor("Keybinds", lambda: KeybindEditor(self.doc))
        add_editor("Environment", lambda: KVTable(self.doc, "environment", ["Variable", "Value"], False))
        add_editor("Animation curves", lambda: AnimationCurvesPage(self.doc))
        add_editor("Effects", lambda: EffectsPage(self.doc))
        add_editor("Outputs", lambda: EntryEditor(self.doc, "output", "map", OUTPUT_GROUPS, "Outputs (connector or monitor)"))
        add_editor("Window rules", lambda: EntryEditor(self.doc, "window_rule", "aot", WINDOW_RULE_GROUPS, "[[window_rule]]"))
        add_editor("Layer rules", lambda: EntryEditor(self.doc, "layer_rule", "aot", [("Layer rule", LAYER_RULE)], "[[layer_rule]]", False))
        add_editor("Workspace rules", lambda: EntryEditor(self.doc, "workspace", "aot", WORKSPACE_RULE_GROUPS, "[[workspace]]"))
        add_editor("Security rules", lambda: EntryEditor(self.doc, "security_context_rule", "aot", [("Security context rule", SECURITY_RULE)], "[[security_context_rule]]", False))
        add_editor("Scratchpads", lambda: EntryEditor(self.doc, "scratchpad", "aot", [("Scratchpad", SCRATCHPAD)], "[[scratchpad]]", False))
        add_editor("Input devices", lambda: EntryEditor(self.doc, "input.device", "aot", [("Device override", INPUT_DEVICE)], "[[input.device]]", False))
        add_editor("User folders", UserDirs)
        add_editor("Default apps", DefaultApps)
        self._editor_page_names = tuple(editor_factories)
        self._built_editors = built_editors
        self._editor_pages = {"userdirs": "User folders", "defaultapps": "Default apps"}

        navigation_names = []
        for section_index, (_, names) in enumerate(SIDEBAR_SECTIONS):
            navigation_names.extend(names)
            if section_index == 0:
                navigation_names.append(None)
        navigation_names.extend(
            name for name in (*settings_pages, *editor_factories) if name not in navigation_names
        )
        fixed_names = navigation_names[:2]
        umbriel_names = [
            name for name in navigation_names[2:] if name is not None
        ]
        navigation_names = [
            *fixed_names,
            None,
            *load_sidebar_order(umbriel_names),
        ]
        for name in navigation_names:
            if name is None:
                tabs.addSeparator()
                continue
            tabs.addLazyTab(settings_pages.get(name) or editor_factories[name], name)

        path_bar = QHBoxLayout()
        config_label = QLabel("Config:")
        self.config_path_edit = QLineEdit(state.PATH)
        self.config_path_edit.setPlaceholderText("/path/to/config.toml")
        self.config_path_edit.returnPressed.connect(self.apply_config_path)
        choose_path_btn = QPushButton("Browse...")
        choose_path_btn.clicked.connect(self.choose_config_path)
        apply_path_btn = QPushButton("Use path")
        apply_path_btn.clicked.connect(self.apply_config_path)
        open_btn = QPushButton("Open config")
        open_btn.clicked.connect(self.open_config_file)
        reload_btn = QPushButton("Reload from disk")
        reload_btn.clicked.connect(self.reopen)
        self.backups_btn = QPushButton("Backups...")
        self.backups_btn.clicked.connect(self.restore_backup)
        path_bar.addWidget(config_label)
        path_bar.addWidget(self.config_path_edit, 1)
        path_bar.addWidget(choose_path_btn)
        path_bar.addWidget(apply_path_btn)
        path_bar.addWidget(open_btn)
        path_bar.addWidget(reload_btn)
        path_bar.addWidget(self.backups_btn)
        root.addLayout(path_bar)

        bar = QHBoxLayout()
        self.save_btn = QPushButton("Save")
        self.save_btn.clicked.connect(self.save)
        self.diff_box = QCheckBox("Review diff before saving")
        self.diff_box.setChecked(True)
        self.validate_box = QCheckBox("Validate after saving")
        self.validate_box.setChecked(not state._CLI_ARGS.no_validate)
        self.rebuild_box = QCheckBox("Rebuild file structure on save")
        self.rebuild_box.setToolTip("Regroup the whole file in canonical order (banners, every key inside its own "
                                    "table, comments kept with their section) before writing. Settings never change, but comments "
                                    "may move. On by default only for files that already use this tool's banners.")
        has_banners = any(BANNER_RE.match(line) for line in self.doc.as_string().splitlines())
        self.rebuild_box.setChecked(has_banners and not state._CLI_ARGS.no_rebuild)
        self.status = QLabel("")
        bar.addWidget(self.status, 1)
        bar.addWidget(self.rebuild_box)
        bar.addWidget(self.diff_box)
        bar.addWidget(self.validate_box)
        bar.addWidget(self.save_btn)
        root.addLayout(bar)
        self.disk_check_timer = QTimer(self)
        self.disk_check_timer.setInterval(2000)
        self.disk_check_timer.timeout.connect(self.check_external_changes)
        self.disk_check_timer.start()

    def _editor(self, attr):
        """Return a lazily built desktop editor, building its page on first use."""
        name = self._editor_pages[attr]
        self.side_tabs.materialize(name)
        return self._built_editors[name]

    @property
    def userdirs(self):
        return self._editor("userdirs")

    @property
    def defaultapps(self):
        return self._editor("defaultapps")

    def show_schema_coverage(self):
        """Show GUI/schema drift from the currently installed Umbriel CLI."""
        if self.schema is None:
            QMessageBox.warning(self, "Schema unavailable", self.schema_status_text)
            return
        missing, stale = check_schema_coverage(self.schema)
        report = [
            f"Umbriel {self.schema.get('version', 'unknown version')} "
            f"({self.schema.get('revision') or 'unknown revision'})",
            "",
        ]
        if not missing and not stale:
            report.append("All schema options are represented by a GUI field or custom editor.")
        if missing:
            report.extend(["Schema options not represented in the GUI:", *[f"  {path}" for path in missing], ""])
        if stale:
            report.extend(["GUI fields not present in this schema:", *[f"  {path}" for path in stale]])
        dialog = QDialog(self)
        dialog.setWindowTitle("Umbriel schema coverage")
        dialog.resize(720, 520)
        layout = QVBoxLayout(dialog)
        layout.addWidget(QLabel(
            "This compares the editor's supported settings with the installed Umbriel CLI schema. "
            "Restart the GUI after updating Umbriel to reload defaults and constraints."
        ))
        output = QPlainTextEdit()
        output.setReadOnly(True)
        output.setPlainText("\n".join(report))
        layout.addWidget(output, 1)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        buttons.rejected.connect(dialog.reject)
        buttons.accepted.connect(dialog.accept)
        layout.addWidget(buttons)
        dialog.exec()

    def mark_dirty(self, *_args):
        """Record a user edit in any settings page."""
        self._dirty = True

    def track_page_changes(self, page):
        """Connect the page's editable controls and editing actions to dirty tracking."""
        widgets = [page, *page.findChildren(QWidget)]
        for widget in widgets:
            if widget.property("dirtyTrackingConnected"):
                continue
            widget.setProperty("dirtyTrackingConnected", True)
            if isinstance(widget, TriStateControl):
                widget.valueChanged.connect(self.mark_dirty)
                widget.activated.connect(self.mark_dirty)
            elif isinstance(widget, QLineEdit):
                widget.textEdited.connect(self.mark_dirty)
            elif isinstance(widget, QPlainTextEdit):
                widget.textChanged.connect(self.mark_dirty)
            elif isinstance(widget, QComboBox):
                widget.currentIndexChanged.connect(self.mark_dirty)
                widget.editTextChanged.connect(self.mark_dirty)
            elif isinstance(widget, (QSpinBox, QDoubleSpinBox)):
                widget.valueChanged.connect(self.mark_dirty)
            elif isinstance(widget, QCheckBox):
                widget.toggled.connect(self.mark_dirty)
            elif isinstance(widget, QTableWidget):
                widget.itemChanged.connect(self.mark_dirty)
            elif isinstance(widget, QListWidget):
                widget.currentRowChanged.connect(
                    lambda _row, page=page: QTimer.singleShot(
                        0, lambda: self.track_page_changes(page)
                    )
                )
            elif isinstance(widget, QPushButton):
                if widget.text() != "Refresh":
                    widget.clicked.connect(self.mark_dirty)
                widget.clicked.connect(
                    lambda _clicked=False, page=page: QTimer.singleShot(
                        0, lambda: self.track_page_changes(page)
                    )
                )

    def check_external_changes(self):
        """Notice config edits made by another application while this window is open."""
        try:
            current = config_fingerprint(state.PATH)
        except OSError as e:
            if not self._external_change_detected:
                self.status.setText(f"Could not check the config for external changes: {e}")
            self._external_change_detected = True
            return
        if current != self._disk_fingerprint:
            self._external_change_detected = True
            self.status.setText("Config changed outside this window. Reload or review before saving.")
        elif self._external_change_detected:
            self._external_change_detected = False
            self.status.setText("External config change is no longer present.")

    def confirm_external_change(self):
        """Require an explicit choice before replacing a config changed on disk."""
        try:
            current = config_fingerprint(state.PATH)
        except OSError as e:
            QMessageBox.critical(self, "Cannot read config", f"Could not check {state.PATH}:\n{e}")
            return False
        if current == self._disk_fingerprint:
            self._external_change_detected = False
            return True

        message = QMessageBox(self)
        message.setIcon(QMessageBox.Icon.Warning)
        message.setWindowTitle(f"Config changed outside {APP_NAME}")
        message.setText(
            "The config file changed after it was loaded. Reload to discard your GUI edits, "
            "or explicitly overwrite the external changes."
        )
        reload_button = message.addButton(
            "Reload from disk", QMessageBox.ButtonRole.AcceptRole
        )
        overwrite_button = message.addButton(
            "Overwrite external changes", QMessageBox.ButtonRole.DestructiveRole
        )
        message.addButton(QMessageBox.StandardButton.Cancel)
        message.exec()
        if message.clickedButton() is reload_button:
            self.reopen(discard_changes=True)
            return False
        if message.clickedButton() is overwrite_button:
            self._disk_fingerprint = current
            self._external_change_detected = False
            return True
        return False

    def confirm_save_diff(self, old_text, new_text):
        """Show the exact TOML diff and ask before writing it."""
        diff = "".join(
            difflib.unified_diff(
                old_text.splitlines(keepends=True),
                new_text.splitlines(keepends=True),
                fromfile=state.PATH,
                tofile=f"{state.PATH} (proposed)",
            )
        )
        if not diff:
            return True
        additions = sum(
            line.startswith("+") and not line.startswith("+++")
            for line in diff.splitlines()
        )
        removals = sum(
            line.startswith("-") and not line.startswith("---")
            for line in diff.splitlines()
        )
        dialog = QDialog(self)
        dialog.setWindowTitle("Review config changes")
        dialog.resize(900, 600)
        layout = QVBoxLayout(dialog)
        layout.addWidget(QLabel(f"Proposed changes: {additions} added, {removals} removed lines."))
        views = QTabWidget()
        sections = group_diff_by_section(diff, new_text)
        section_page = QWidget()
        section_layout = QHBoxLayout(section_page)
        section_list = QListWidget()
        section_preview = QPlainTextEdit()
        section_preview.setReadOnly(True)
        section_preview.setLineWrapMode(QPlainTextEdit.LineWrapMode.NoWrap)
        section_font = QFont(section_preview.font())
        section_font.setFamily("monospace")
        section_preview.setFont(section_font)
        for name, changes in sections.items():
            added = sum(line.startswith("+") and not line.startswith("++") for line in changes)
            removed = sum(line.startswith("-") and not line.startswith("--") for line in changes)
            item = QListWidgetItem(f"{name}  (+{added} / -{removed})")
            item.setData(Qt.ItemDataRole.UserRole, "".join(changes))
            section_list.addItem(item)
        section_list.currentItemChanged.connect(
            lambda current, _previous: section_preview.setPlainText(
                current.data(Qt.ItemDataRole.UserRole) if current else ""
            )
        )
        if section_list.count():
            section_list.setCurrentRow(0)
        section_layout.addWidget(section_list, 0)
        section_layout.addWidget(section_preview, 1)
        views.addTab(section_page, "By section")

        preview = QPlainTextEdit()
        preview.setReadOnly(True)
        preview.setLineWrapMode(QPlainTextEdit.LineWrapMode.NoWrap)
        preview.setPlainText(diff)
        preview_font = QFont(preview.font())
        preview_font.setFamily("monospace")
        preview.setFont(preview_font)
        views.addTab(preview, "Unified diff")
        layout.addWidget(views, 1)
        buttons = QDialogButtonBox()
        buttons.addButton("Save changes", QDialogButtonBox.ButtonRole.AcceptRole)
        buttons.addButton(QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(dialog.accept)
        buttons.rejected.connect(dialog.reject)
        layout.addWidget(buttons)
        return dialog.exec() == QDialog.DialogCode.Accepted

    def restore_backup(self):
        """Restore a timestamped backup after confirming that unsaved edits may be discarded."""
        directory = os.path.join(config_gui_data_dir(state.PATH), "backups")
        migrate_gui_directory(state.PATH + ".backups", directory)
        try:
            snapshots = sorted(
                os.path.join(directory, name)
                for name in os.listdir(directory)
                if name.startswith(os.path.basename(state.PATH) + ".") and name.endswith(".bak")
            )
        except FileNotFoundError:
            snapshots = []
        except OSError as e:
            QMessageBox.warning(self, "Could not list backups", str(e))
            return
        if not snapshots:
            QMessageBox.information(self, "No backups", "No saved backup snapshots are available yet.")
            return
        labels = [os.path.basename(snapshot) for snapshot in reversed(snapshots)]
        selected, accepted = QInputDialog.getItem(
            self, "Restore backup", "Choose a saved config snapshot:", labels, 0, False
        )
        if not accepted:
            return
        snapshot = snapshots[-1 - labels.index(selected)]
        try:
            load_config_document(snapshot)
        except ConfigLoadError as e:
            QMessageBox.warning(self, "Invalid backup", str(e))
            return
        answer = QMessageBox.question(
            self,
            "Restore config backup",
            "Restore this snapshot over the current config? This discards unsaved GUI edits.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.Cancel,
            QMessageBox.StandardButton.Cancel,
        )
        if answer != QMessageBox.StandardButton.Yes:
            return
        try:
            create_backup_snapshot(state.PATH)
            rollback_path = os.path.join(config_gui_data_dir(state.PATH), "config.bak")
            migrate_gui_file(state.PATH + ".bak", rollback_path)
            with open(snapshot, encoding="utf-8") as backup:
                write_text_file(state.PATH, backup.read())
        except OSError as e:
            QMessageBox.critical(self, "Could not restore backup", str(e))
            return
        self._dirty = False
        self.reopen()

    def closeEvent(self, event):
        """Ask whether to save or discard edits before closing the window."""
        if not self._dirty:
            event.accept()
            return
        choice = QMessageBox.question(
            self,
            "Unsaved changes",
            "Save your changes before closing?",
            QMessageBox.StandardButton.Save
            | QMessageBox.StandardButton.Discard
            | QMessageBox.StandardButton.Cancel,
            QMessageBox.StandardButton.Save,
        )
        if choice == QMessageBox.StandardButton.Save:
            if self.save():
                event.accept()
            else:
                event.ignore()
        elif choice == QMessageBox.StandardButton.Discard:
            event.accept()
        else:
            event.ignore()

    def choose_config_path(self):
        """Pick a config.toml file with the system file dialog and fill the path field."""
        start = self.config_path_edit.text() or state.PATH
        chosen, _ = QFileDialog.getOpenFileName(self, "Select config.toml", start, "TOML files (*.toml);;All files (*)")
        if chosen:
            self.config_path_edit.setText(chosen)

    def apply_config_path(self):
        """Switch the active config file to the selected path and reopen the window."""
        path = os.path.expanduser(self.config_path_edit.text().strip())
        if not path:
            return
        if not os.path.exists(path):
            QMessageBox.warning(self, "Config not found", f"{path} does not exist.")
            return
        self.reopen(path)

    def open_config_file(self):
        """Ask the user which app to use to open the current config file."""
        target = os.path.expanduser(self.config_path_edit.text().strip()) or state.PATH
        if not os.path.exists(target):
            QMessageBox.warning(self, "Config not found", f"{target} does not exist.")
            return

        known = [
            ("kate", "Kate"), ("kwrite", "KWrite"), ("pluma", "Pluma"), ("gedit", "Gedit"),
            ("mousepad", "Mousepad"), ("xed", "Xed"), ("leafpad", "Leafpad"),
            ("gnome-text-editor", "GNOME Text Editor"), ("nvim", "Neovim"), ("nano", "Nano"),
            ("code", "VS Code"), ("codium", "VSCodium"), ("subl", "Sublime Text"),
            ("helix", "Helix"), ("vim", "Vim"), ("emacs", "Emacs"), ("kak", "Kakoune"),
        ]

        labels, commands = [], []
        for cmd, label in known:
            if shutil.which(cmd.split()[0]):
                labels.append(label)
                commands.append(cmd)

        if sys.platform.startswith("darwin") and shutil.which("open"):
            labels.append("System default")
            commands.append("open")
        elif os.name == "nt" and shutil.which("notepad.exe"):
            labels.append("System default")
            commands.append("notepad.exe")
        elif shutil.which("xdg-open"):
            labels.append("System default")
            commands.append("xdg-open")

        labels.append("Custom command...")
        commands.append("custom")

        preferred_index = 0
        for idx, cmd in enumerate(commands):
            if cmd in {"kate", "kwrite", "pluma", "gedit", "mousepad", "xed"}:
                preferred_index = idx
                break

        choice, ok = QInputDialog.getItem(
            self,
            "Open config with",
            "Choose an application:",
            labels,
            preferred_index,
            False,
        )
        if not ok:
            return

        idx = labels.index(choice)
        app = commands[idx]
        if app == "custom":
            cmd, ok2 = QInputDialog.getText(self, "Custom command", "Command to run (for example: kate --new-window):")
            if not ok2 or not cmd.strip():
                return
            try:
                subprocess.Popen(cmd.strip().split() + [target])
            except OSError:
                QMessageBox.warning(self, "Could not open file", f"Unable to run: {cmd}")
            return

        try:
            if app in ("xdg-open", "open"):
                if sys.platform.startswith("darwin"):
                    subprocess.Popen(["open", target])
                elif os.name == "nt":
                    os.startfile(target)
                else:
                    subprocess.Popen(["xdg-open", target])
            elif app == "notepad.exe":
                os.startfile(target)
            elif app in ("nano", "vim", "nvim", "helix", "kak", "emacs"):
                term = shutil.which("x-terminal-emulator") or shutil.which("kitty") or shutil.which("konsole") or shutil.which("gnome-terminal")
                if term:
                    subprocess.Popen([term, "-e", app, target])
                else:
                    subprocess.Popen([app, target])
            else:
                subprocess.Popen([app.split()[0], *app.split()[1:], target])
        except OSError:
            QMessageBox.warning(self, "Could not open file", f"Unable to open {target} with {choice}.")

    def reopen(self, config_path=None, discard_changes=False):
        """Validate the target, then open a fresh window after resolving unsaved edits."""
        target = normalize_config_path(config_path) if config_path else state.PATH
        try:
            load_config_document(target)
        except ConfigLoadError as e:
            QMessageBox.warning(self, "Cannot open config", str(e))
            return
        if discard_changes:
            self._dirty = False
        app = QApplication.instance()
        app.setQuitOnLastWindowClosed(False)
        try:
            if not self.close():
                return
            state.PATH = target
            if config_path:
                try:
                    persist_config_path(target)
                except OSError as e:
                    QMessageBox.warning(self, "Could not save config path", str(e))
            w = Window(target)
            w.show()
            app.win = w
        finally:
            app.setQuitOnLastWindowClosed(True)

    def save(self):
        """Check inputs, save changed config and desktop settings, then optionally validate in the background."""
        if not self.confirm_external_change():
            return False
        for name in self._editor_page_names:
            self.side_tabs.materialize(name)
        try:
            disk_text, _ = read_config_state(state.PATH)
            for fw in self.fws:
                fw.get()
            for ed in self.editors:
                ed.validate()
        except OSError as e:
            QMessageBox.critical(self, "Could not read config", f"Could not read {state.PATH}:\n{e}")
            return False
        except ValueError as e:
            QMessageBox.warning(self, "Invalid value", str(e))
            return False
        apply_fields(self.doc, self.fws)
        try:
            for ed in self.editors:
                if ed is not self.userdirs and ed is not self.defaultapps:
                    ed.commit()
        except OSError as e:
            QMessageBox.critical(self, "Could not prepare config", str(e))
            return False

        def save_desktop_settings():
            try:
                self.userdirs.commit()
                self.defaultapps.commit()
            except OSError as e:
                self._dirty = True
                QMessageBox.critical(
                    self, "Could not save desktop settings",
                    f"{e}\n\nSome desktop settings may already have been saved.",
                )
                return False
            return True

        inline_window_rule_matches(self.doc)
        new_text = add_entry_name_comments(tomlkit.dumps(self.doc), self.editors)
        rebuilt = False
        if self.rebuild_box.isChecked():
            try:
                new_text = rebuild_config(new_text)
                rebuilt = True
            except Exception as e:  # never block a save: fall back to the normal in-place layout
                QMessageBox.warning(self, "Structure rebuild skipped",
                                    f"The file was saved without restructuring ({e}).")
        keybind_editor = next((ed for ed in self.editors if isinstance(ed, KeybindEditor)), None)
        if keybind_editor and not rebuilt:
            new_text = move_new_keybinds(new_text, keybind_editor.pending_new_keys)
        if keybind_editor:
            new_text = write_keybind_groups(
                new_text,
                keybind_editor.group_names,
                keybind_editor.group_assignments,
            )

        if not self.confirm_external_change():
            return False
        try:
            latest_text, latest_fingerprint = read_config_state(state.PATH)
        except OSError as e:
            QMessageBox.critical(self, "Could not read config", f"Could not read {state.PATH}:\n{e}")
            return False
        if latest_fingerprint != self._disk_fingerprint:
            if not self.confirm_external_change():
                return False
            self.status.setText("Config changed during save preparation. Review the diff and save again.")
            return False
        disk_text = latest_text
        reviewed_fingerprint = latest_fingerprint
        if disk_text == new_text:
            if not save_desktop_settings():
                return False
            saved_items = []
            if self.userdirs.changed:
                saved_items.append("user folders")
            if self.defaultapps.changed:
                saved_items.append("default apps")
            self._disk_fingerprint = latest_fingerprint
            self._dirty = False
            self.status.setText(
                f"Saved {', '.join(saved_items)}." if saved_items else "No changes to save."
            )
            return True
        if self.diff_box.isChecked() and not self.confirm_save_diff(disk_text, new_text):
            return False
        if not self.confirm_external_change():
            return False
        try:
            latest_fingerprint = config_fingerprint(state.PATH)
        except OSError as e:
            QMessageBox.critical(self, "Could not read config", f"Could not check {state.PATH}:\n{e}")
            return False
        if latest_fingerprint != reviewed_fingerprint:
            self.status.setText("Config changed while reviewing the diff. Review it again before saving.")
            return False
        if not save_desktop_settings():
            return False
        try:
            create_backup_snapshot(state.PATH)
            rollback_path = os.path.join(config_gui_data_dir(state.PATH), "config.bak")
            migrate_gui_file(state.PATH + ".bak", rollback_path)
            shutil.copy2(state.PATH, rollback_path)
            write_text_file(state.PATH, new_text)
            self._disk_fingerprint = config_fingerprint(state.PATH)
            self._external_change_detected = False
        except OSError as e:
            self._dirty = True
            message = f"Could not safely save {state.PATH}:\n{e}"
            if self.userdirs.changed or self.defaultapps.changed:
                message += "\n\nDesktop settings were already saved."
            QMessageBox.critical(self, "Could not save config", message)
            return False
        self._dirty = False
        if not self.validate_box.isChecked():
            self.status.setText("Saved (not validated). Umbriel keeps its last working config if the reload fails.")
            return True
        # Validate in the background so the window never freezes.
        self.save_btn.setEnabled(False)
        self.status.setText("Saved. Validating...")
        self.proc = QProcess(self)
        args = ["config", "validate", "-c", state.PATH, "--json"]
        self.backups_btn.setEnabled(False)
        self.timer = QTimer(self, singleShot=True, interval=30000)
        self.timer.timeout.connect(self.proc.kill)
        self.proc.finished.connect(self.validated)
        self.proc.errorOccurred.connect(self.validate_error)
        self.timer.start()
        self.proc.start("umbriel", args)
        return True

    def validate_error(self, err):
        """Handle `umbriel` not being installed: the file stays saved and validation is skipped."""
        if err == QProcess.ProcessError.FailedToStart:
            self.timer.stop()
            self.save_btn.setEnabled(True)
            self.backups_btn.setEnabled(True)
            self.status.setText("Saved. `umbriel` not found on PATH, validation skipped.")

    def show_validation_diagnostics(self, diagnostics):
        """Show validator output and allow diagnostics with config paths to navigate to their page."""
        if not diagnostics:
            return
        errors_count = sum(
            isinstance(diagnostic, dict) and diagnostic.get("severity") == "error"
            for diagnostic in diagnostics
        )
        warning_count = len(diagnostics) - errors_count
        dialog = QDialog(self)
        dialog.setWindowTitle("Config validation")
        dialog.resize(780, 420)
        layout = QVBoxLayout(dialog)
        layout.addWidget(QLabel(
            f"{errors_count} error(s), {warning_count} warning(s). "
            "Double-click a diagnostic to open its config page when possible."
        ))
        items = QListWidget()
        for diagnostic in diagnostics:
            if not isinstance(diagnostic, dict):
                diagnostic = {"message": str(diagnostic)}
            severity = str(diagnostic.get("severity", "error")).upper()
            location = diagnostic.get("file") or ""
            if location and diagnostic.get("line"):
                location += f":{diagnostic['line']}"
                if diagnostic.get("column"):
                    location += f":{diagnostic['column']}"
            text = f"{severity}: {diagnostic.get('message', '')}"
            if location:
                text += f"  ({location})"
            item = QListWidgetItem(text)
            severity_color = (
                QColor("#c53030")
                if severity == "ERROR"
                else QColor("#b7791f")
            )
            item.setForeground(QBrush(severity_color))
            path = next(
                (diagnostic.get(key) for key in ("path", "key_path", "setting_path", "setting", "key")
                 if diagnostic.get(key)),
                "",
            )
            if not path:
                paths_in_message = re.findall(
                    r"(?<![\w-])(?:[A-Za-z_][\w-]*\.)+[A-Za-z_][\w-]*(?:\[\d+\])?",
                    str(diagnostic.get("message", "")),
                )
                path = next(
                    (
                        candidate for candidate in paths_in_message
                        if candidate.startswith((
                            "animation.", "effects.", "environment.", "keybinds.",
                            "output.", "window_rule", "layer_rule", "workspace.",
                            "scratchpad.", "input.device.",
                        ))
                    ),
                    "",
                )
            if isinstance(path, (list, tuple)):
                path = ".".join(str(part) for part in path)
            item.setData(Qt.ItemDataRole.UserRole, str(path) if path else "")
            item.setToolTip(text)
            items.addItem(item)
        items.itemDoubleClicked.connect(
            lambda item: (self.navigate_to_config_path(item.data(Qt.ItemDataRole.UserRole)), dialog.accept())
        )
        layout.addWidget(items, 1)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        buttons.rejected.connect(dialog.reject)
        buttons.accepted.connect(dialog.accept)
        layout.addWidget(buttons)
        dialog.exec()

    def navigate_to_config_path(self, path):
        """Select the page and entry most closely matching a validator's config path."""
        if not path:
            return False
        self.side_tabs.ensureAllPages()
        path = str(path).strip().lstrip("$.")
        for page_name, page in self.side_tabs.page_widgets.items():
            editors = ([page] if isinstance(page, EntryEditor) else []) + page.findChildren(EntryEditor)
            for editor in editors:
                root = ".".join(editor.path)
                match = re.match(
                    r"^" + re.escape(root) + r"(?:\[(\d+)\]|\.(\d+))?(?:\.(.*))?$",
                    path,
                )
                if not match:
                    continue
                entry_index = int(match.group(1) or match.group(2)) if (match.group(1) or match.group(2)) else None
                remainder = match.group(3) or ""
                if editor.mode == "map" and entry_index is None and remainder:
                    entry_name, _, remainder = remainder.partition(".")
                    entry_index = next(
                        (index for index, (name, _) in enumerate(editor.entries())
                         if str(name) == entry_name),
                        None,
                    )
                self.side_tabs.nav.setCurrentRow(self.side_tabs.page_rows[page_name])
                if entry_index is not None and 0 <= entry_index < editor.list.count():
                    editor.list.setCurrentRow(entry_index)
                QTimer.singleShot(0, lambda page=page, suffix=remainder: self.focus_config_field(page, suffix))
                return True

        for page_name, page in self.side_tabs.page_widgets.items():
            fields = page.findChildren(FieldWidget)
            matching_field = next(
                (
                    field_widget for field_widget in fields
                    if ".".join(field_widget.f.path) == path
                    or path.endswith("." + ".".join(field_widget.f.path))
                ),
                None,
            )
            if matching_field is not None:
                self.side_tabs.nav.setCurrentRow(self.side_tabs.page_rows[page_name])
                matching_field.search_group.setExpanded(True)
                matching_field.w.setFocus()
                return True
        route_prefixes = (
            ("Animation curves", ("animation.beziers", "animation.springs")),
            ("Effects", ("effects.",)),
            ("Environment", ("environment.",)),
            ("Keybinds", ("keybinds.",)),
            ("Outputs", ("output.",)),
            ("Window rules", ("window_rule",)),
            ("Layer rules", ("layer_rule",)),
            ("Workspace rules", ("workspace.",)),
            ("Scratchpads", ("scratchpad.",)),
            ("Input devices", ("input.device.",)),
        )
        for page_name, prefixes in route_prefixes:
            if any(path.startswith(prefix) for prefix in prefixes):
                self.side_tabs.nav.setCurrentRow(self.side_tabs.page_rows[page_name])
                return True
        for page_name, page in self.side_tabs.page_widgets.items():
            if any(
                ".".join(field_widget.f.path).startswith(path)
                for field_widget in page.findChildren(FieldWidget)
            ):
                self.side_tabs.nav.setCurrentRow(self.side_tabs.page_rows[page_name])
                return True
        return False

    @staticmethod
    def focus_config_field(page, suffix):
        """Focus a field in a dynamically selected rule when its path is known."""
        if not suffix:
            return
        for field_widget in page.findChildren(FieldWidget):
            field_path = ".".join(field_widget.f.path)
            if field_path == suffix or suffix.endswith("." + field_path):
                field_widget.search_group.setExpanded(True)
                field_widget.w.setFocus()
                return

    def validated(self, code, _status):
        """Restore only on validation errors; warnings are shown while keeping the saved config."""
        self.timer.stop()
        self.save_btn.setEnabled(True)
        self.backups_btn.setEnabled(True)
        out = bytes(self.proc.readAllStandardOutput()).decode(errors="replace").strip()
        err = bytes(self.proc.readAllStandardError()).decode(errors="replace").strip()
        if _status == QProcess.ExitStatus.CrashExit:
            self.status.setText("Saved. Validation did not finish (timed out after 30 s); file kept.")
            return
        try:
            result = json.loads(out)
            diagnostics = result.get("diagnostics") if isinstance(result, dict) else None
            if not isinstance(diagnostics, list) or not isinstance(result.get("valid"), bool):
                diagnostics = None
        except (ValueError, AttributeError):
            result = None
            diagnostics = None

        def describe(diagnostic):
            if not isinstance(diagnostic, dict):
                return str(diagnostic)
            where = diagnostic.get("file") or ""
            if where and diagnostic.get("line"):
                where += f":{diagnostic['line']}" + (
                    f":{diagnostic['column']}" if diagnostic.get("column") else ""
                )
            message = f"{diagnostic.get('severity', 'error')}: {diagnostic.get('message', '')}"
            return message + (f"  ({where})" if where else "")

        if diagnostics is None:
            if code == 0:
                self.status.setText("Saved, but validation output could not be read; the file was kept.")
                QMessageBox.warning(
                    self,
                    "Could not read validation result",
                    out or err or "Umbriel exited successfully without a JSON validation result.",
                )
                return
            errors = [out or err or f"exit status {code}"]
            warnings = []
        else:
            errors = [describe(d) for d in diagnostics
                      if isinstance(d, dict) and d.get("severity") == "error"]
            warnings = [describe(d) for d in diagnostics
                        if not isinstance(d, dict) or d.get("severity") != "error"]
            if result.get("valid") is False and not errors:
                errors.append("Umbriel reported an invalid configuration without an error diagnostic.")
            if code != 0 and not errors:
                errors.append(err or f"Validator exited with status {code}.")
        if errors:
            try:
                rollback_path = os.path.join(
                    config_gui_data_dir(state.PATH), "config.bak"
                )
                with open(rollback_path, encoding="utf-8") as backup:
                    write_text_file(state.PATH, backup.read())
                self._disk_fingerprint = config_fingerprint(state.PATH)
                self._external_change_detected = False
            except OSError as e:
                self._dirty = True
                self.status.setText("Validation failed and the backup could not be restored.")
                QMessageBox.critical(
                    self,
                    "Validation failed",
                    f"{os.linesep.join(errors + warnings)}\n\nCould not restore the saved backup:\n{e}",
                )
                return
            self._dirty = True
            self.status.setText("Validation failed - file restored from backup.")
            QMessageBox.critical(
                self, "Validation failed - file restored from backup",
                "\n".join(errors + warnings),
            )
            self.show_validation_diagnostics(diagnostics or [])
        elif warnings:
            self.status.setText(f"Saved with {len(warnings)} warning(s).")
            self.show_validation_diagnostics(diagnostics)
        else:
            self.status.setText("Saved and validated.")


def load_config_snapshot(path):
    """Load a TOML document and matching disk fingerprint from one file snapshot."""
    if not os.path.exists(path):
        raise ConfigLoadError(f"{path} does not exist.\nCopy /usr/share/umbriel/config.toml there first.")
    try:
        text, fingerprint = read_config_state(path)
    except (OSError, UnicodeDecodeError) as e:
        raise ConfigLoadError(f"Could not read {path}:\n{e}") from e
    try:
        return tomlkit.parse(text), fingerprint
    except tomlkit.exceptions.TOMLKitError as e:
        raise ConfigLoadError(
            f"{path} is not valid TOML:\n{e}\n\nFix it first (try `umbriel config validate -c {path}`)."
        ) from e


def load_config_document(path):
    """Parse the TOML file at `path`, raising a readable error if it cannot be loaded."""
    return load_config_snapshot(path)[0]


def main(argv=None):
    """Run the GUI with a consistent CLI configuration path and global state."""
    state.PATH, state._CLI_ARGS = parse_cli_args(argv)
    if state._CLI_ARGS.check_schema:
        try:
            schema = load_umbriel_schema()
        except (FileNotFoundError, RuntimeError, ValueError, subprocess.TimeoutExpired) as error:
            print(f"Schema check unavailable: {error}", file=sys.stderr)
            return 2
        missing, stale = check_schema_coverage(schema)
        print(
            f"Umbriel {schema.get('version', 'unknown version')} "
            f"({schema.get('revision') or 'unknown revision'}): "
            f"{len(missing)} unsupported option(s), {len(stale)} stale GUI field(s)."
        )
        for path in missing:
            print(f"Missing GUI field: {path}")
        for path in stale:
            print(f"Stale GUI field: {path}")
        return 1 if missing or stale else 0
    app = QApplication(sys.argv[:1])
    app.setApplicationName(APP_NAME)
    app.setApplicationDisplayName(APP_NAME)
    app.setDesktopFileName("umbriel-config-gui")
    app.theme_follower = Qt6ctThemeFollower(app)
    app.theme_follower.start()
    app.palette_readability = PaletteReadability(app)
    apply_interaction_styles(app)
    app_icon = create_app_icon()
    app.setWindowIcon(app_icon)
    try:
        install_desktop_icon(app_icon)
    except OSError as e:
        QMessageBox.warning(
            None,
            "Could not install desktop icon",
            f"The window icon is set, but the Wayland desktop entry could not be installed:\n{e}",
        )
    try:
        app.win = Window()
    except ConfigLoadError as e:
        QMessageBox.critical(None, "Cannot open config", str(e))
        return 1
    app.win.show()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())

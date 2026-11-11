"""Editors for XDG user folders and default applications."""

from .common import (
    QComboBox,
    QFileDialog,
    QFont,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPalette,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
    Qt,
    WheelSafeComboBox,
    gui_backup_file,
    mimetypes,
    migrate_gui_file,
    os,
    re,
    shutil,
    write_text_file,
)
from .settings_layout import CollapsibleGroup
from .widgets import SettingLabel, SettingRow, WrappedLabel


# ------------------------------------------------------------ user folders
USER_DIRS = os.path.join(os.environ.get("XDG_CONFIG_HOME") or os.path.expanduser("~/.config"), "user-dirs.dirs")
USER_DIR_KEYS = ["DESKTOP", "DOCUMENTS", "DOWNLOAD", "MUSIC", "PICTURES", "VIDEOS",
                 "TEMPLATES", "PUBLICSHARE", "PROJECTS"]
USER_DIR_RE = re.compile(r'^\s*XDG_([A-Z]+)_DIR\s*=\s*"(.*)"\s*$')

MIMEAPPS_PATH = os.path.join(
    os.environ.get("XDG_CONFIG_HOME") or os.path.expanduser("~/.config"),
    "mimeapps.list",
)
MIMEAPPS_SECTION_RE = re.compile(r"^\s*\[([^\]]+)\]\s*(?:[#;].*)?$")
MIMEAPPS_ENTRY_RE = re.compile(r"^\s*([^#;=\s][^=]*?)\s*=\s*(.*?)\s*$")
MIME_TYPE_RE = re.compile(
    r"^[A-Za-z0-9][A-Za-z0-9!#$&^_.+-]*/"
    r"[A-Za-z0-9][A-Za-z0-9!#$&^_.+-]*$"
)
FILE_EXTENSION_RE = re.compile(r"^\.[A-Za-z0-9][A-Za-z0-9._+-]*$")
DEFAULT_APP_ROLES = [
    ("Web browser", ["text/html", "application/xhtml+xml",
                     "x-scheme-handler/http", "x-scheme-handler/https"]),
    ("Email client", ["x-scheme-handler/mailto"]),
    ("File manager", ["inode/directory", "x-scheme-handler/file"]),
    ("Text editor", ["text/plain"]),
    ("Image viewer", ["image/jpeg", "image/png", "image/gif", "image/webp",
                      "image/svg+xml", "image/bmp", "image/tiff"]),
    ("PDF viewer", ["application/pdf"]),
    ("Audio player", ["audio/mpeg", "audio/ogg", "audio/flac", "audio/wav"]),
    ("Video player", ["video/mp4", "video/webm", "video/x-matroska", "video/ogg"]),
]
ROLE_MIME_TYPES = {mime for _, mimes in DEFAULT_APP_ROLES for mime in mimes}


def installed_desktop_apps():
    """Return installed desktop application IDs paired with their display names."""
    data_home = os.environ.get("XDG_DATA_HOME") or os.path.expanduser("~/.local/share")
    data_dirs = os.environ.get("XDG_DATA_DIRS") or "/usr/local/share:/usr/share"
    roots = [os.path.join(data_home, "applications")]
    roots.extend(
        os.path.join(directory, "applications")
        for directory in data_dirs.split(os.pathsep)
        if directory
    )
    apps = {}
    seen_ids = set()
    for root in roots:
        if not os.path.isdir(root):
            continue
        for directory, subdirs, filenames in os.walk(root):
            subdirs.sort()
            for filename in sorted(filenames):
                if not filename.endswith(".desktop"):
                    continue
                path = os.path.join(directory, filename)
                try:
                    with open(path, encoding="utf-8") as desktop_file:
                        section = None
                        values = {}
                        for line in desktop_file:
                            line = line.rstrip("\r\n")
                            if line.startswith("[") and line.endswith("]"):
                                section = line[1:-1]
                            elif section == "Desktop Entry" and "=" in line:
                                key, value = line.split("=", 1)
                                values[key] = value
                except (OSError, UnicodeError):
                    continue
                relative = os.path.relpath(path, root)
                app_id = relative.replace(os.sep, "-")
                if app_id in seen_ids:
                    continue
                seen_ids.add(app_id)
                if (section is None or values.get("Type", "Application") != "Application"
                        or values.get("Hidden", "").lower() == "true"
                        or values.get("NoDisplay", "").lower() == "true"):
                    continue
                try_exec = values.get("TryExec", "")
                if try_exec and not (os.path.isabs(try_exec) and os.access(try_exec, os.X_OK)
                                     or not os.path.isabs(try_exec) and shutil.which(try_exec)):
                    continue
                name = values.get("Name", app_id[:-8] if app_id.endswith(".desktop") else app_id)
                for escaped, unescaped in (
                    (r"\s", " "), (r"\n", "\n"), (r"\t", "\t"), (r"\r", "\r"), (r"\\", "\\")
                ):
                    name = name.replace(escaped, unescaped)
                apps.setdefault(app_id, name)
    return sorted(apps.items(), key=lambda app: (app[1].casefold(), app[0].casefold()))


def create_app_selector(apps, app_id):
    """Create an editable application dropdown, preserving IDs absent from the installed list."""
    selector = WheelSafeComboBox()
    selector.setEditable(True)
    selector.setInsertPolicy(QComboBox.InsertPolicy.NoInsert)
    selector.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon)
    selector.setMinimumContentsLength(32)
    populate_app_selector(selector, apps, app_id)
    return selector


def populate_app_selector(selector, apps, app_id):
    """Refresh a selector without replacing it or losing its current ID."""
    signals_blocked = selector.blockSignals(True)
    selector.clear()
    selector.addItem("", "")
    for desktop_id, name in apps:
        selector.addItem(f"{name} ({desktop_id})", desktop_id)
    selected_index = selector.findData(app_id)
    if selected_index < 0 and app_id:
        selector.addItem(f"{app_id} (not installed)", app_id)
        selected_index = selector.count() - 1
    if selected_index >= 0:
        selector.setCurrentIndex(selected_index)
    selector.blockSignals(signals_blocked)


def selected_app_id(selector):
    """Return the selected desktop-file ID or the manually entered value."""
    index = selector.currentIndex()
    if index >= 0 and selector.currentText() == selector.itemText(index):
        return selector.itemData(index) or ""
    return selector.currentText().strip()


def parse_mimeapps_defaults(lines):
    """Read the default application IDs from all [Default Applications] sections."""
    defaults = {}
    section = None
    for line in lines:
        header = MIMEAPPS_SECTION_RE.match(line)
        if header:
            section = header.group(1)
            continue
        if section != "Default Applications":
            continue
        entry = MIMEAPPS_ENTRY_RE.match(line)
        if entry:
            defaults[entry.group(1).strip()] = [
                app_id.strip() for app_id in entry.group(2).split(";") if app_id.strip()
            ]
    return defaults


def update_mimeapps_defaults(lines, updates):
    """Update default app IDs while preserving unrelated sections, comments, and entries."""
    if not updates:
        return lines
    output = []
    section = None
    found_section = False
    additions_written = False
    present = set(parse_mimeapps_defaults(lines))
    seen = set()

    def additions():
        return [
            f"{mime}={app_id};"
            for mime, app_id in updates.items()
            if app_id and mime not in present
        ]

    for line in lines:
        header = MIMEAPPS_SECTION_RE.match(line)
        if header:
            if section == "Default Applications" and not additions_written:
                output.extend(additions())
                additions_written = True
            section = header.group(1)
            if section == "Default Applications":
                found_section = True
            output.append(line)
            continue
        if section != "Default Applications":
            output.append(line)
            continue
        entry = MIMEAPPS_ENTRY_RE.match(line)
        if not entry:
            output.append(line)
            continue
        mime = entry.group(1).strip()
        if mime not in updates:
            output.append(line)
            continue
        present.add(mime)
        if mime in seen:
            continue
        seen.add(mime)
        app_id = updates[mime]
        if not app_id:
            continue
        fallback_ids = [
            candidate.strip()
            for candidate in entry.group(2).split(";")
            if candidate.strip() and candidate.strip() != app_id
        ]
        value = ";".join([app_id, *fallback_ids]) + ";"
        output.append(f"{mime}={value}")

    if section == "Default Applications" and not additions_written:
        output.extend(additions())
        additions_written = True
    if not found_section and any(updates.values()):
        if output and output[-1].strip():
            output.append("")
        output.append("[Default Applications]")
        output.extend(f"{mime}={app_id};" for mime, app_id in updates.items() if app_id)
    elif not additions_written:
        output.extend(additions())
    return output


class UserDirs(QWidget):
    """Edits ~/.config/user-dirs.dirs (XDG user folders: Pictures, Documents, ...)."""

    def __init__(self):
        """Read user-dirs.dirs and show one row per XDG folder with its path and a Browse button."""
        super().__init__()
        self.lines = []
        if os.path.exists(USER_DIRS):
            with open(USER_DIRS, encoding="utf-8") as f:
                self.lines = f.read().splitlines()
        self.orig = {}
        for line in self.lines:
            m = USER_DIR_RE.match(line)
            if m:
                self.orig[m.group(1)] = m.group(2)
        names = USER_DIR_KEYS + [k for k in self.orig if k not in USER_DIR_KEYS]
        lay = QVBoxLayout(self)
        user_dirs_help = QLabel(
            f"{USER_DIRS} - used by file managers, browsers and file dialogs.\n"
            "$HOME is allowed. Restart apps after changing. Folders are not created for you."
        )
        user_dirs_help.setWordWrap(True)
        user_dirs_help_font = QFont(user_dirs_help.font())
        user_dirs_help_font.setPointSize(9)
        user_dirs_help.setFont(user_dirs_help_font)
        lay.addWidget(user_dirs_help)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        content = QWidget()
        cards = QVBoxLayout(content)
        cards.setContentsMargins(0, 0, 0, 0)
        folder_card = CollapsibleGroup(
            "User folders", 1,
            description="Choose paths used by applications for your folders.",
        )
        self.path_edits = {}
        for name in names:
            title = QLabel(name.capitalize())
            font = QFont(title.font())
            font.setBold(True)
            title.setFont(font)
            path_edit = QLineEdit(self.orig.get(name, ""))
            path_edit.setAccessibleName(f"{name.capitalize()} folder path")
            path_edit.setPlaceholderText("Not set")
            browse = QPushButton("Browse...")
            browse.setAccessibleName(f"Browse {name.capitalize()} folder")
            browse.clicked.connect(lambda _checked=False, key=name: self.browse(key))
            editor = QWidget()
            editor_layout = QHBoxLayout(editor)
            editor_layout.setContentsMargins(0, 0, 0, 0)
            editor_layout.addWidget(path_edit, 1)
            editor_layout.addWidget(browse)
            folder_card.form.addRow(title, editor)
            self.path_edits[name] = path_edit
        cards.addWidget(folder_card)
        cards.addStretch(1)
        scroll.setWidget(content)
        lay.addWidget(scroll, 1)
        self.changed = False

    def browse(self, name):
        """Pick a folder with the file dialog; paths inside your home are stored as $HOME/..."""
        cur = self.path_edits[name].text().replace("$HOME", os.path.expanduser("~"))
        d = QFileDialog.getExistingDirectory(self, "Choose folder", cur if os.path.isdir(cur) else os.path.expanduser("~"))
        if d:
            home = os.path.expanduser("~")
            self.path_edits[name].setText(
                ("$HOME" + d[len(home):]) if d == home or d.startswith(home + "/") else d
            )

    def values(self):
        """Return the edited paths as {FOLDER: path}."""
        return {name: edit.text().strip() for name, edit in self.path_edits.items()}

    def validate(self):
        """Reject paths that would break the quoted user-dirs file format."""
        for n, v in self.values().items():
            if any(char in v for char in '"\r\n'):
                raise ValueError(f"{n.capitalize()}: path must not contain double quotes or line breaks")

    def commit(self):
        """Rewrite user-dirs.dirs with the changed paths (a .bak copy is made first). Comments and untouched lines are kept; no folders are created or moved."""
        vals = {n: v for n, v in self.values().items() if v != self.orig.get(n, "") and (v or n in self.orig)}
        self.changed = bool(vals)
        if not vals:
            return
        out, done = [], set()
        for line in self.lines:
            m = USER_DIR_RE.match(line)
            if m and m.group(1) in vals and vals[m.group(1)]:
                out.append(f'XDG_{m.group(1)}_DIR="{vals[m.group(1)]}"')
                done.add(m.group(1))
            elif m and m.group(1) in vals:
                done.add(m.group(1))  # emptied: drop the line
            else:
                out.append(line)
        for n, v in vals.items():
            if n not in done and v:
                out.append(f'XDG_{n}_DIR="{v}"')
        if os.path.exists(USER_DIRS):
            backup = gui_backup_file("user-dirs.dirs.bak")
            migrate_gui_file(USER_DIRS + ".bak", backup)
            os.makedirs(os.path.dirname(backup), exist_ok=True)
            shutil.copy2(USER_DIRS, backup)
        write_text_file(USER_DIRS, "\n".join(out) + "\n")
        self.lines = out
        self.orig.update({n: v for n, v in vals.items()})


class DefaultApps(QWidget):
    """Edits XDG default application associations in the user's mimeapps.list."""

    def __init__(self):
        """Show common application roles and additional MIME type defaults."""
        super().__init__()
        self.lines = []
        if os.path.exists(MIMEAPPS_PATH):
            with open(MIMEAPPS_PATH, encoding="utf-8") as f:
                self.lines = f.read().splitlines()
        self.defaults = parse_mimeapps_defaults(self.lines)
        self.apps = installed_desktop_apps()
        layout = QVBoxLayout(self)
        defaults_help = QLabel(
            f"{MIMEAPPS_PATH} - application IDs are desktop-file IDs, for example firefox.desktop.\n"
            "Choose an installed app or type an application ID. Changing a role updates its listed MIME types."
        )
        defaults_help.setWordWrap(True)
        defaults_help_font = QFont(defaults_help.font())
        defaults_help_font.setPointSize(9)
        defaults_help.setFont(defaults_help_font)
        layout.addWidget(defaults_help)
        app_controls = QHBoxLayout()
        app_controls.addWidget(QLabel("Installed applications"))
        refresh_apps_button = QPushButton("Refresh")
        refresh_apps_button.clicked.connect(self.refresh_apps)
        app_controls.addWidget(refresh_apps_button)
        app_controls.addStretch(1)
        layout.addLayout(app_controls)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        content = QWidget()
        cards = QVBoxLayout(content)
        cards.setContentsMargins(0, 0, 0, 0)
        roles_card = CollapsibleGroup(
            "Common app roles", 1, description="Choose applications for common tasks."
        )
        self.role_initial = {}
        self.role_mimes = {}
        self.role_selectors = {}
        for role, mimes in DEFAULT_APP_ROLES:
            values = [self.defaults.get(mime, [""])[0] for mime in mimes]
            value = values[0] if all(item == values[0] for item in values) else "<multiple>"
            self.role_initial[role] = value
            self.role_mimes[role] = mimes
            title = QLabel(role)
            font = QFont(title.font())
            font.setBold(True)
            title.setFont(font)
            description = WrappedLabel(", ".join(mimes))
            description.setForegroundRole(QPalette.ColorRole.PlaceholderText)
            selector = create_app_selector(self.apps, value)
            selector.setAccessibleName(f"{role} application")
            self.role_selectors[role] = selector
            roles_card.form.addRow(SettingRow(SettingLabel(title, description), selector))
        cards.addWidget(roles_card)

        self.mime_card = CollapsibleGroup(
            "Other file types", 0,
            description="Manage additional MIME type defaults.",
        )
        self.mime_search = QLineEdit()
        self.mime_search.setPlaceholderText("Search file types or applications...")
        self.mime_search.setAccessibleName("Search other file types")
        self.mime_search.setProperty("dirtyTrackingConnected", True)
        self.mime_search.textChanged.connect(self._filter_mime_rows)
        self.mime_card.form.addRow(self.mime_search)
        self.mime_rows = []
        self.mime_initial = {
            mime: apps[0] if apps else ""
            for mime, apps in self.defaults.items()
            if mime not in ROLE_MIME_TYPES
        }
        buttons_widget = QWidget()
        buttons = QHBoxLayout(buttons_widget)
        buttons.setContentsMargins(0, 0, 0, 0)
        add_button = QPushButton("Add MIME type")
        add_button.clicked.connect(self.add_mime_type)
        add_format_button = QPushButton("Add file format")
        add_format_button.clicked.connect(self.add_file_format)
        buttons.addWidget(add_button)
        buttons.addWidget(add_format_button)
        buttons.addStretch(1)
        self.mime_card.form.addRow(buttons_widget)
        for mime, app_id in sorted(self.mime_initial.items()):
            self._add_mime_row(mime, app_id)
        cards.addWidget(self.mime_card)
        cards.addStretch(1)
        scroll.setWidget(content)
        layout.addWidget(scroll, 1)
        self.changed = False

    def _add_mime_row(self, mime, app_id):
        mime_edit = QLineEdit(mime)
        mime_edit.setAccessibleName("MIME type")
        selector = create_app_selector(self.apps, app_id)
        selector.setAccessibleName("Application for MIME type")
        remove = QPushButton("Remove")
        remove.setAccessibleName(f"Remove {mime}")
        editor = QWidget()
        editor_layout = QHBoxLayout(editor)
        editor_layout.setContentsMargins(0, 0, 0, 0)
        editor_layout.addWidget(selector)
        editor_layout.addWidget(remove)
        row = SettingRow(mime_edit, editor)
        self.mime_rows.append((row, mime_edit, selector))
        self.mime_card.form.insertRow(self.mime_card.form.rowCount() - 1, row)
        remove.clicked.connect(lambda: self._remove_mime_row(row))
        self._filter_mime_rows()

    def _remove_mime_row(self, row):
        self.mime_rows = [entry for entry in self.mime_rows if entry[0] is not row]
        self.mime_card.form.removeRow(row)

    def _filter_mime_rows(self, *_args):
        terms = self.mime_search.text().casefold().split()
        for row, mime_edit, selector in self.mime_rows:
            text = f"{mime_edit.text()} {selector.currentText()} {selected_app_id(selector)}".casefold()
            row.setVisible(all(term in text for term in terms))

    def refresh_apps(self):
        """Rescan desktop entries and refresh dropdowns without changing current selections."""
        self.apps = installed_desktop_apps()
        for selector in (*self.role_selectors.values(), *(entry[2] for entry in self.mime_rows)):
            populate_app_selector(selector, self.apps, selected_app_id(selector))
        self._filter_mime_rows()

    def _mime_type_is_listed(self, mime):
        normalized_mime = mime.casefold()
        return (
            normalized_mime in {role_mime.casefold() for role_mime in ROLE_MIME_TYPES}
            or any(
                mime_edit.text().strip().casefold() == normalized_mime
                for _, mime_edit, _ in self.mime_rows
            )
        )

    def add_mime_type(self):
        """Add a row for an additional MIME type."""
        mime, accepted = QInputDialog.getText(self, "Add MIME type", "MIME type:")
        mime = mime.strip()
        if not accepted or not mime:
            return
        if self._mime_type_is_listed(mime):
            QMessageBox.warning(self, "Already listed", f"{mime} is already listed.")
            return
        self._add_mime_row(mime, "")

    def add_file_format(self):
        """Add a file extension when the system has a MIME type mapping for it."""
        extension, accepted = QInputDialog.getText(
            self, "Add file format", "File extension (for example .docx):"
        )
        extension = extension.strip().lower()
        if not accepted:
            return
        if extension and not extension.startswith("."):
            extension = "." + extension
        if not FILE_EXTENSION_RE.fullmatch(extension):
            QMessageBox.warning(
                self,
                "Invalid file extension",
                "Enter a file extension such as .docx or .tar.gz.",
            )
            return

        mime, _ = mimetypes.guess_type(f"file{extension}", strict=False)
        if not mime:
            QMessageBox.warning(
                self,
                "Unknown file format",
                f"No MIME type mapping is available for {extension}. "
                "Add its MIME type manually instead.",
            )
            return
        if self._mime_type_is_listed(mime):
            QMessageBox.warning(
                self,
                "Already listed",
                f"{extension} uses {mime}, which is already listed.",
            )
            return
        self._add_mime_row(mime, "")

    def _mime_values(self):
        return {
            mime_edit.text().strip(): selected_app_id(selector)
            for _, mime_edit, selector in self.mime_rows
        }

    def validate(self):
        """Reject invalid MIME names and application IDs before writing mimeapps.list."""
        for role, selector in self.role_selectors.items():
            value = selected_app_id(selector)
            if value == self.role_initial[role]:
                continue
            if any(char in value for char in ";\r\n"):
                raise ValueError(f"{role}: invalid application ID")
        values = self._mime_values()
        for mime, app_id in values.items():
            if not MIME_TYPE_RE.fullmatch(mime):
                raise ValueError(f"{mime or 'MIME type'}: enter a valid type/subtype")
            if app_id and any(char in app_id for char in ";\r\n"):
                raise ValueError(f"{mime}: invalid application ID")
        if len({mime.casefold() for mime in values}) != len(self.mime_rows):
            raise ValueError("MIME types must be unique")

    def commit(self):
        """Write changed default associations, keeping unrelated mimeapps.list content."""
        updates = {}
        for role, selector in self.role_selectors.items():
            app_id = selected_app_id(selector)
            if app_id == self.role_initial[role]:
                continue
            for mime in self.role_mimes[role]:
                updates[mime] = app_id

        values = self._mime_values()
        for mime in set(self.mime_initial) | set(values):
            old_value = self.mime_initial.get(mime, "")
            new_value = values.get(mime, "")
            if old_value != new_value:
                updates[mime] = new_value

        self.changed = False
        if updates:
            new_lines = update_mimeapps_defaults(self.lines, updates)
            self.changed = new_lines != self.lines
            if self.changed:
                if os.path.exists(MIMEAPPS_PATH):
                    backup = gui_backup_file("mimeapps.list.bak")
                    migrate_gui_file(MIMEAPPS_PATH + ".bak", backup)
                    os.makedirs(os.path.dirname(backup), exist_ok=True)
                    shutil.copy2(MIMEAPPS_PATH, backup)
                write_text_file(MIMEAPPS_PATH, "\n".join(new_lines) + "\n")
                self.lines = new_lines

        self.defaults = parse_mimeapps_defaults(self.lines)
        self.role_initial = {}
        for role, mimes in DEFAULT_APP_ROLES:
            values_for_role = [self.defaults.get(mime, [""])[0] for mime in mimes]
            self.role_initial[role] = (
                values_for_role[0]
                if all(value == values_for_role[0] for value in values_for_role)
                else "<multiple>"
            )
        self.mime_initial = {
            mime: apps[0] if apps else ""
            for mime, apps in self.defaults.items()
            if mime not in ROLE_MIME_TYPES
        }

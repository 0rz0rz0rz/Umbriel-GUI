# Umbriel-GUI Noctalia plugin

This Noctalia 5.5 plugin provides General, Keybinds, User Folders and Default Apps
sections. User Folders and Default Apps edit `$XDG_CONFIG_HOME/user-dirs.dirs`
and `mimeapps.list` (default `~/.config/`). It requires Python 3 on `PATH`
and plugin API 24 or newer. General and Keybinds additionally need Python 3.11
or newer and the `umbriel` CLI. It is separate from the PySide6 app.

Add this directory as a local plugin source in a running Noctalia session:

```sh
noctalia plugins lint /path/to/Umbriel-GUI/noctalia-plugin/user-folders
noctalia msg plugins source add umbriel-dev path /path/to/Umbriel-GUI/noctalia-plugin
noctalia msg plugins enable umbriel-settings/user-folders
noctalia msg panel-open umbriel-settings/user-folders:folders
```

Replace `/path/to/Umbriel-GUI` with the checkout's absolute path. Alternatively,
enable the plugin in **Settings → Plugins**. After enabling it, add the plugin's
`umbriel-settings/user-folders:settings` widget to the bar using the Add-widget
picker. Its **Umbriel-GUI** button opens and closes the panel; remove the old Custom
Button if you added one. Existing installations must run
`noctalia msg config-reload` to discover the new widget.

The main menu's **Open standalone app** button uses `gio` and
`$XDG_DATA_HOME/applications/umbriel-config-gui.desktop` (default
`~/.local/share/applications/umbriel-config-gui.desktop`). Run the standalone
app once first to create that entry; the button then uses the source or
AppImage installation recorded there. If that installation moves, run it again
to update the entry. A successful launch request does not guarantee that the
app itself started successfully.

Choose a section after opening the panel. The Back button retains
unsaved edits while the panel stays open. Manifest edits require
`noctalia msg config-reload`; script edits hot-reload. Disable the plugin or
remove the `umbriel-dev` source in Settings
or with `noctalia msg plugins disable` / `noctalia msg plugins source remove`.

Paths must be absolute or start with `$HOME/`; empty fields remove an existing
entry. Browse uses `zenity` or `kdialog` to select an existing folder; the
chooser times out after 60 seconds. The panel does not create or move folders.
It preserves unrelated
entries and comments, rejects saves if the file changed since loading, and
backs up an existing file as `user-dirs.dirs.bak` in the plugin's Noctalia
data directory. Symlinked user-folder files are read-only in this prototype.
Wait for the save confirmation before closing the panel, and restart
applications to pick up changes. The Reload button discards unsaved edits;
closing the panel also discards them.
To keep the folder chooser usable, clicking outside no longer closes the
panel; use Close, Escape, or the bar button instead.

Default Apps supports common application roles and additional MIME types or
file extensions in collapsible sections; Other file types initially starts
collapsed. The General, Keybinds and Default Apps section states are saved in
`section-expansion.json` in the plugin data directory and restored when the
panel is reopened, including after Noctalia restarts. If the file cannot be
restored, sections start collapsed and the plugin reports the error.
Choose an installed application or enter its desktop-file
ID. Changes preserve unrelated entries and existing fallback IDs; clearing a
field removes its association. A backup is saved as `mimeapps.list.bak` in the
plugin data directory, and external edits are detected before saving. Symlinked
`mimeapps.list` files are read-only.

General offers the standalone app's six collapsible groups. It initially uses
the config path last selected in Umbriel Settings, or
`~/.config/umbriel/config.toml` if no path was saved. This is not necessarily
the running compositor's config: check the displayed path, and enter another
path and press Reload if needed. The config must already exist. Included files
are validated but their values are not displayed or edited.

Only changed fields are written. The helper validates the proposed config with
`umbriel` before saving, preserves unrelated values and comments, detects
external edits, rejects symlinks, and keeps a per-config backup in the plugin
data directory. Multiline values containing comments and some inline-table or
unusual TOML layouts cannot yet be safely edited here; the helper refuses those
edits without saving. Use the standalone app for those cases. Restart Umbriel
for settings marked as requiring a restart.

Keybinds lists bindings from the selected config in collapsible groups and
supports searching, adding, editing and removing shortcuts. Enter shortcuts
as text. Simple actions are edited directly; use **Edit advanced options**
to edit a TOML table with options such as `repeat`, `submap`, `release` or
`cooldown_ms`. Existing table values retain their other options unless you
change them. Included configs are not displayed. The selected path is
independent of General: check it and press Reload after changing it.

The plugin honors the standalone app's keybind locks and group assignments.
Manage locks and groups in the standalone app; removing a binding also removes
its group assignment. Some TOML layouts are read-only in the plugin. Saves
validate with Umbriel, detect config and lock changes, and use the same
per-config backup as General.

## Plugin data and backups

Noctalia stores plugin data separately from the standalone app, normally in
`~/.local/state/noctalia/plugins/data/umbriel-settings/user-folders/`.
`NOCTALIA_STATE_HOME` or `XDG_STATE_HOME` can change the state root. This
directory holds `section-expansion.json`, the desktop-setting backups, and
`umbriel-config-<config-id>.bak` for each Umbriel config edited by General or
Keybinds. Each backup is replaced on the next save for that file; these are not
the standalone app's timestamped snapshots.

This plugin is experimental and does not yet include a custom-folder editor
or all standalone settings. Use the standalone app for unsupported sections.

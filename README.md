# Umbriel Settings

A desktop app for editing an Umbriel TOML config, keeping existing comments and formatting where possible.

![Umbriel Settings screenshot](docs/settings-0.1.0-002.png)

## Features

- General, appearance, colors, animation, input, layout and workspace settings
- Keybind list and detail editor with dynamically sized collapsible group cards, concise action descriptions, filtering, bulk locking and action help
- Animation curves, effect presets and pools; outputs, rules, scratchpads, input-device overrides and environment variables
- Drag the divider between an entry list and its settings to resize either pane;
  long entry names can be scrolled horizontally.
- XDG user folders, default applications and MIME associations
- Sliders for bounded settings, using installed Umbriel schema ranges when available
- The **Overridden** switch filters setting fields to values different from their
  schema defaults (or the GUI defaults when schema metadata is unavailable).
  Unset optional fields are hidden; non-field editors are not filtered.
  Inherited values from included configs are not resolved by this filter.
- Section shortcuts expand or collapse their cards and scroll to newly opened
  sections. Cards start expanded unless their previous expansion state was saved.
- Title-bar background opacity controls, stored in the existing color values
- Installed or custom cursor themes; **Schema coverage...** compares fields with the installed schema

Cursor themes are discovered when opening Input using `XCURSOR_PATH`, or
`~/.icons`, XDG icon directories and `/usr/share/pixmaps` if unset. Reopen the
app to pick up newly installed themes.

## Keybinds

Select a shortcut in a collapsible group to edit its action and options. Search
matches shortcuts, group names, action descriptions and raw actions; the full
action is also available in the tooltip. Locked bindings show a key icon and
cannot be edited or removed until unlocked. Deleting a group moves its bindings
to **Ungrouped** without deleting or unlocking them.

## Versions

| Item | Version |
| --- | --- |
| Python GUI (`python/umbriel_config_gui/__init__.py`) | `0.1.0-002` |
| AppImage (latest release) | `0.1.0-002` |

The version format is `<Umbriel version>-<three-digit GUI revision>`.

## Desktop settings

The GUI also edits:

- **User folders** (Desktop, Documents, Downloads, Pictures, ...): `~/.config/user-dirs.dirs`
- **Default applications** (browser, file manager, MIME types, ...): the `[Default Applications]` section of `~/.config/mimeapps.list`

`$XDG_CONFIG_HOME` is respected. Unrelated entries and comments are preserved,
unset options are not written, and desktop settings are saved separately after
you accept the config diff. **User folders** provides editable paths and folder
pickers in a settings card. **Default apps** groups common roles into cards;
expand **Other file types** to search and edit individual MIME associations.
Application selectors also accept custom desktop-file IDs.

## Saving safely

- Review a diff before saving (on by default). External edits are detected and can be reloaded.
- Umbriel CLI validation runs after saving; disable it with the checkbox or `--no-validate`. It is skipped if Umbriel is not on `PATH`. Errors restore the previous file; warnings are reported.
- Files with GUI section banners can be regrouped on save, which may move comments. Disable **Rebuild file structure on save** to keep the layout.
- **Backups...** lists timestamped TOML snapshots. Select one to restore, or check snapshots (using **Select all** / **Deselect all** if needed) and choose **Delete marked**; deletion requires confirmation and cannot be undone. Separately saved desktop settings are not rolled back.

GUI-only data (backups, labels, last config path) lives in `~/.local/share/umbriel-config-gui` (or `$XDG_DATA_HOME/umbriel-config-gui`); data from the old `umbriel_config_gui/data` location is migrated automatically. Custom keybind groups are stored as TOML comments, which Umbriel ignores.

## Requirements

Python 3, PySide6, tomlkit. The Umbriel CLI is optional (validation and schema comparison).

```sh
# Arch Linux
sudo pacman -S python pyside6 python-tomlkit

# Debian 13+
sudo apt install python3 python3-pyside6.qtwidgets python3-tomlkit

# Fedora
sudo dnf install python3 python3-pyside6 python3-tomlkit

# openSUSE Tumbleweed
sudo zypper install python3 python3-pyside6 python3-tomlkit

# Otherwise, use a virtual environment
python3 -m venv .venv && . .venv/bin/activate
python -m pip install -r python/requirements.txt
```

## Run

```sh
python python/umbriel-config-gui.py [path/to/config.toml]
# or
cd python && python -m umbriel_config_gui [path/to/config.toml]
```

Without a path, it opens `~/.config/umbriel/config.toml` unless another was used previously.

```text
--config PATH     Select a config file (alternative to the positional path)
--no-validate     Skip Umbriel CLI validation after saving
--no-rebuild      Do not reorganize the file when saving
--check-schema    Compare GUI fields with the installed Umbriel schema and exit
--version         Show the version and exit
```

### AppImage

Build a self-contained AppImage with Python, PySide6 and tomlkit:

```sh
appimage/build-appimage.sh        # writes dist/Umbriel-Settings-<version>-<arch>.AppImage
```

The build needs network access, `bash`, `python3` with `venv`, and FUSE (or `APPIMAGE_EXTRACT_AND_RUN=1`). Only QtCore, QtGui and QtWidgets are kept; the Umbriel CLI is looked up on `PATH`.

The Wayland desktop entry points to the AppImage itself, so keep it at a stable path (or use that path in the keybind below).

### Theming (qt6ct / Noctalia)

AppImage and pip/venv installs cannot load the system qt6ct plugin. Instead, the app reads `~/.config/qt6ct/qt6ct.conf` and applies its style (or Fusion if unavailable), font, icon theme and KDE color scheme (`color_scheme_path`, e.g. Noctalia's `noctalia.colors`). Config and scheme changes are applied while the app is open.

This only runs when `QT_QPA_PLATFORMTHEME` is `qt6ct`/`qt5ct` and Qt has not already applied the theme. Set `UMBRIEL_QT_THEME=none` to disable it or `UMBRIEL_QT_THEME=qt6ct` to force it.

The app also adjusts unreadable hint text, borders and selected labels, especially in light schemes.

Title-bar background opacity is saved as the alpha component of the Umbriel color
(``#RRGGBBAA``). Reloading the Qt palette only changes this app's appearance;
it does not update Umbriel's config. If another tool generates or overrides
title-bar colors, it must preserve or set their alpha when regenerating them.

On the Colors page, unset title-bar background and text fields preview the
active and inactive `[WM]` colors from the KDE scheme selected in qt6ct. These
previews follow scheme changes while the page is open; they are not necessarily
the colors Umbriel uses from its defaults or included files. For each background,
**KDE TB** imports the colorful `[WM]` color, while **KDE BG** imports the matching
active or inactive `[Colors:Header]` background for a cleaner look. **Default**
unsets the override; a custom color has no selected segment. Text fields have a
**Use KDE color** button. Importing preserves alpha. Existing overrides
are never changed automatically. Saved overrides are static, so a later theme
change requires importing again; the GUI does not rewrite files in the background.

### Launch with a keybind

Add to the `[keybinds]` section of your Umbriel config (or add it on the GUI's **Keybinds** page):

```toml
"Mod+Shift+C" = "spawn /usr/bin/python3 /path/to/Umbriel-GUI/python/umbriel-config-gui.py"
```

Adjust the paths (use `.venv/bin/python` if you installed in a virtual environment) and quote paths containing spaces.

### Custom icon

Replace `python/umbriel_config_gui/assets/icon.jpg` with your own JPEG and restart. If it is missing or invalid, the embedded default is used.

## Repository layout

```text
python/     Python application (launcher, umbriel_config_gui package, requirements.txt)
appimage/   AppImage build script and recipe (desktop entry, icon, entrypoint)
docs/       Screenshots
```

## License

This project is licensed under the GNU General Public License, version 3 only.
See [LICENSE](LICENSE).

> **Disclaimer:** This project was created entirely by AI.

## Related projects

- [Umbriel](https://github.com/noctalia-dev/umbriel) — the Wayland compositor whose configuration this app edits.
- [Noctalia](https://github.com/noctalia-dev/noctalia) — the desktop shell; this app can follow its color scheme.

---
name: add-test
description: "Use when writing or fixing a unit test for this repo: headless Qt test layout, which modules to import or patch, and how to run a single test file."
---

# Add a headless test

- One file per area in `tests/test_<area>.py`, `unittest` style (no pytest).
- Qt setup: `cls.app = QApplication.instance() or QApplication([])` in `setUpClass`; `self.addCleanup(widget.close)`; call `self.app.processEvents()` after showing.
- Import from the module that owns the symbol, not through `settings`:
  - `field_defs`: `F`, `TABS`, field specs
  - `widgets`: `SwitchCheckBox`, `SettingSlider`, ...
  - `field_widget`: `FieldWidget`, `apply_fields`, `installed_cursor_themes`
  - `setting_help`: `FIELD_HELP`, `GROUP_HELP`, `CATEGORY_HELP`, `setting_description`
  - `settings_layout`: `CollapsibleGroup`, `form_page`, group expansion state
  - `settings`: compatibility facade only
  - `desktop`: `USER_DIRS`, `MIMEAPPS_PATH`, `installed_desktop_apps`
  - `keybind_ui`: `KeybindEditor`, `KeybindItemDelegate`
  - `keybinds`: table-backed keybind logic and group metadata
  - `editors`: `EntryEditor` (list/detail splitter)
  - `tables`: `EffectsPage` (preset and pool entry editors)
  - `window`: `Window`, `load_umbriel_schema`, `list_backup_snapshots`, `delete_backup_snapshots`
  - `sidebar`: `SideTabs` (lazy pages, debounced search and overridden filter)
  - `sidebar_icons`: `sidebar_icon` (palette-aware pictograms)
- Patch where the name is looked up, e.g. `patch("umbriel_config_gui.window.load_umbriel_schema")`, and `patch.object(desktop, "USER_DIRS", ...)`.
- Never touch the real `~/.config`; use `tempfile.TemporaryDirectory()` and patch paths.
- For backup dialogs, see `tests/test_backups.py`: patch the config/data paths and confirmation dialog, and exercise marked deletion without touching real backups.
- For sidebar search, overridden filtering, section shortcut state and monochrome palette changes, see `tests/test_sidebar.py`; allow Qt's event loop to process timers and deferred page builds.
- For resizable entry editors (including effects), see `tests/test_entry_editor_layout.py`: patch the config path, schema and label storage; process deferred splitter setup, test long names and user resizing, and explicitly delete Qt widgets when needed for clean shutdown.
- For keybind UI tests, see `tests/test_keybind_ui.py`; patch `state.PATH` and `keybinds.config_gui_data_dir` to a temporary directory, process deferred list updates, and exercise selection, grouping and persistence through the visible cards and backing model.
- Run one file: `cd python && QT_QPA_PLATFORM=offscreen PYTHONPATH=. python -m unittest discover -s ../tests -p test_<area>.py`
- Run one test: append `-k <test_name>`.

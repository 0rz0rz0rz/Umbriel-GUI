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
  - `window`: `Window`, `load_umbriel_schema`
- Patch where the name is looked up, e.g. `patch("umbriel_config_gui.window.load_umbriel_schema")`, and `patch.object(desktop, "USER_DIRS", ...)`.
- Never touch the real `~/.config`; use `tempfile.TemporaryDirectory()` and patch paths.
- Run one file: `cd python && QT_QPA_PLATFORM=offscreen PYTHONPATH=. python -m unittest discover -s ../tests -p test_<area>.py`
- Run one test: append `-k <test_name>`.

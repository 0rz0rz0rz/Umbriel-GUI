---
name: edit-controls
description: "Use when changing Umbriel Settings navigation, section buttons, pictograms, splitters, controls, field rows, or form layout and styling."
---

# Edit controls and layout

- Locate shared controls in `python/umbriel_config_gui/widgets.py`; `TriStateControl` paints segmented pills, and `KdeColorControl` inherits its painting and interaction.
- `SettingRow`, `SettingLabel`, and `FlowLayout` handle form layout. `FieldWidget` in `field_widget.py` and `form_page` in `settings_layout.py` wire controls to fields; locate methods with grep and read only relevant ranges.
- `form_page` section buttons toggle their cards and reflect header, overview, saved, and temporary search expansion states. Keep them synchronized, including non-collapsible cards; test `tests/test_sidebar.py`.
- `SideTabs` combines debounced search with the overridden filter; `FieldWidget.is_overridden` and `valueChanged` provide live default comparisons. Preserve hidden rows, opacity rows, section buttons, lazy-page and entry-selection behavior. `sidebar_icons.py` draws palette-aware monochrome pictograms and `sidebar.py` refreshes them on palette changes; test `tests/test_sidebar.py`.
- `EntryEditor` in `editors.py` provides the draggable list/detail splitter for rules, outputs, scratchpads, devices, and effect presets/pools. Keep its initial roughly 1:2 split, user-adjusted width across selection and refresh, non-collapsible panes, and horizontal scrolling for long names; test `tests/test_entry_editor_layout.py`.
- The backup manager is `Window.restore_backup` in `window.py`; preserve separate restore selection and checked deletion, its confirmation, and the select/deselect-all state. Test with `tests/test_backups.py`.
- Keybind cards and list/detail layout live in `keybind_ui.py`; behavior and persistence remain in `keybinds.py`. Keep shared multi-selection mapped to table rows, and exclude collapsed or filtered rows from actions. `KeybindItemDelegate` aligns shortcut and description columns; retain key icons, raw-action search and tooltips, and the draggable splitter. Test with `tests/test_keybind_ui.py`.
- User-folder and default-app cards live in `desktop.py`; preserve editable paths, custom desktop IDs and unchanged associations. Test with `tests/test_user_dirs.py` and `tests/test_default_apps.py`.
- Reuse palette roles and shared controls. Keep mouse, keyboard, disabled-state, accessibility, and dirty-tracking behavior intact.
- Shared vertical scrollbar styling lives in `interaction_styles.py` and is applied at app startup. Keep its track borderless and thumb visible; check scroll areas, lists, trees, tables and text editors with `tests/test_scrollbar_styles.py`.
- Use `WheelSafeComboBox` for app combo-box inputs when its wheel behavior fits; apply `tidy_table` to editable table views so settings and editor pages share table styling.
- For segmented pills, round only the outer selected edge; internal selected edges are square. Test all segments and subclasses with headless Qt pixel checks in `tests/test_settings_switches.py`.
- Use `add-test` for test conventions and run touched test files first. Use `verify-changes` after Python edits; do not build the AppImage for verification.

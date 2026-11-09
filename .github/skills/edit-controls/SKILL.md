---
name: edit-controls
description: "Use when changing Umbriel Settings buttons, segmented controls, switches, sliders, field rows, or form layout and styling."
---

# Edit controls and layout

- Locate shared controls in `python/umbriel_config_gui/widgets.py`; `TriStateControl` paints segmented pills, and `KdeColorControl` inherits its painting and interaction.
- `SettingRow`, `SettingLabel`, and `FlowLayout` handle form layout. `FieldWidget` in `field_widget.py` and `form_page` in `settings_layout.py` wire controls to fields; locate methods with grep and read only relevant ranges.
- Reuse palette roles and shared controls. Keep mouse, keyboard, disabled-state, accessibility, and dirty-tracking behavior intact.
- Use `WheelSafeComboBox` for app combo-box inputs when its wheel behavior fits; apply `tidy_table` to editable table views so settings and editor pages share table styling.
- For segmented pills, round only the outer selected edge; internal selected edges are square. Test all segments and subclasses with headless Qt pixel checks in `tests/test_settings_switches.py`.
- Use `add-test` for test conventions and run touched test files first. Use `verify-changes` after Python edits; do not build the AppImage for verification.

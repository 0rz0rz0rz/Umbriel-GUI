---
name: add-setting-field
description: "Use when adding, renaming, or removing a single GUI setting (an F(...) field) such as a new toggle, number, choice, or color for an Umbriel option, without reading the large modules."
---

# Add a setting field

1. Find the sibling: `grep -n "<sibling.toml.path>" python/umbriel_config_gui/field_defs.py`, then view about 30 lines around the hit.
2. Add `F(label, "dotted.toml.path", kind, default, extra, opt)` next to it in the same group. `kind` is one of `bool`, `int`, `float`, `color`, `choice`, `combo`, `str`, `list`, `strorlist`, `command_list`, `raw`. `extra` is the `(min, max)` range for numbers or the option list for choices. Use `opt=True` for keys that are absent by default.
3. For a choice list, add or reuse a constant near the top of `field_defs.py` (e.g. `ON_OFF`, `LAYOUTS`).
4. Optional help text: add the path to `FIELD_HELP` in `settings.py` (grep for a sibling there). Skip it if the schema description is enough.
5. Get type, default, range and description from `umbriel config schema --json`; do not guess.
6. Verify with the `verify-changes` skill. `--check-schema` must still report 0 unsupported and 0 stale.

Do not edit `window.py` or `common.py` for a plain field; they need no change.

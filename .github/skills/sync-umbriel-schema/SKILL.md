---
name: sync-umbriel-schema
description: "Use when Umbriel was updated or the GUI may be out of date: compare GUI fields with the installed Umbriel schema, add missing options, remove stale ones, and update the version."
---

# Sync the GUI with the installed Umbriel schema

1. `umbriel --version` to see the installed version.
2. `cd python && QT_QPA_PLATFORM=offscreen python umbriel-config-gui.py --check-schema` lists unsupported options and stale GUI fields.
3. For each unsupported option, find a sibling field with `grep -n "<sibling path>" python/umbriel_config_gui/field_defs.py` and add a new `F(...)` entry next to it in the same group (see `F` in `field_defs.py`). Use `umbriel config schema --json` for the option's type, default, range and description.
4. Remove or rename stale fields flagged by the check. Keep keybind actions in `actions.py` in step with the schema.
5. Re-run the check until it reports `0 unsupported option(s), 0 stale GUI field(s)`, then run the tests (see `verify-changes`).
6. If the Umbriel version changed, set `__version__` in `python/umbriel_config_gui/__init__.py` to `<new Umbriel version>-001`.

Do not read `field_defs.py` or `settings.py` whole. Work from grep hits and short view ranges.

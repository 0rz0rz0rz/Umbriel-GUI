---
name: edit-noctalia-desktop-settings
description: "Use when changing Noctalia plugin user-folder paths, default applications, MIME associations, or their Python helper protocol."
---

# Edit Noctalia desktop settings

- `user-folders/user_dirs.py` owns folder parsing, validation, snapshots and shared `read_document`/`atomic_write`; `user-folders/default_apps.py` owns role mappings, app discovery, MIME edits and imports the shared IO.
- `panel.luau` communicates with each helper via `read`, `save` and, for default apps, `extension`. Keep request/response shapes and panel state in sync when changing either side.
- Preserve unrelated entries and comments, MIME fallback IDs, unchanged values, revision conflict detection, per-plugin backups, atomic replacement and symlink rejection. Surface invalid input and IO errors.
- Helpers must stay standalone with Python's standard library; do not import the Qt GUI. Compare intended behavior with `python/umbriel_config_gui/desktop.py` when parity matters.
- Add isolated temporary-XDG tests in the relevant `noctalia-plugin/tests/test_*.py`; use `test-noctalia-plugin` and `verify-noctalia-plugin`.

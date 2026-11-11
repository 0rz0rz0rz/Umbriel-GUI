---
name: split-module
description: "Use when a Python module in python/umbriel_config_gui grows past roughly 800 lines and should be split, or when moving classes/functions between modules without breaking imports, tests, or import cycles."
---

# Split or move code between modules

1. Locate blocks with `grep -n "^class \|^def " <file>`; move whole top-level blocks only, verbatim.
2. Do the move with a small throwaway Python script (cut by line ranges, write the new file with its own imports). Delete the script afterwards. This is cheaper and safer than retyping.
3. Keep the import direction acyclic:
   - `actions` and `widgets` depend on `common`; `field_defs` depends on `actions`; `schema` depends on `field_defs`.
   - `field_widget` depends on `schema` and `widgets`; `setting_help` is standalone; `settings_layout` depends on `field_widget`, `setting_help`, and `widgets`.
   - `editors` depends on `field_widget` and `settings_layout`; `tables` depends on `editors`; `desktop` and `keybinds` may depend on `tables`; `keybind_ui` depends on `keybinds` and `settings_layout`.
   - `sidebar_icons` uses Qt directly; `sidebar` depends on it, `editors` and the settings modules; `window` composes all modules. `settings.py` is a compatibility facade and implementation modules must not import it.
   Check with `grep -n "^from \.[a-z_]* import" python/umbriel_config_gui/*.py` before adding an import.
4. `common.py`, `window.py` and `qt6ct_theme.py` re-export names on purpose; do not prune their imports.
5. After the move, remove unused imports in the touched files only and make sure no name is undefined: `cd python && python -c "import umbriel_config_gui.window"` plus the tests (Pylance `source.unusedImports` only works on indexed files).
6. Update tests to import and patch names from their owning modules (see the `add-test` skill) and the module map in `.github/copilot-instructions.md`.
7. Verify with the `verify-changes` skill.

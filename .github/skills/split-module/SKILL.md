---
name: split-module
description: "Use when a Python module in python/umbriel_config_gui grows past roughly 800 lines and should be split, or when moving classes/functions between modules without breaking imports, tests, or import cycles."
---

# Split or move code between modules

1. Locate blocks with `grep -n "^class \|^def " <file>`; move whole top-level blocks only, verbatim.
2. Do the move with a small throwaway Python script (cut by line ranges, write the new file with its own imports). Delete the script afterwards. This is cheaper and safer than retyping.
3. Current import direction (a module may import only from modules to its left; avoid cycles):
   `common` -> `field_defs` -> `schema` -> `widgets`/`settings` -> `editors` -> `tables` -> `desktop`, `keybinds`; `sidebar` imports `editors` and `settings`; `window` imports all of them.
   Check with `grep -n "^from \.[a-z_]* import" python/umbriel_config_gui/*.py` before adding an import.
4. `common.py`, `window.py` and `qt6ct_theme.py` re-export names on purpose; do not prune their imports.
5. After the move, remove unused imports in the touched files only and make sure no name is undefined: `cd python && python -c "import umbriel_config_gui.window"` plus the tests (Pylance `source.unusedImports` only works on indexed files).
6. Update tests that import or patch moved names (see the `add-test` skill) and the module map in `.github/copilot-instructions.md`.
7. Verify with the `verify-changes` skill.

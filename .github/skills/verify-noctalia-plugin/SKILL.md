---
name: verify-noctalia-plugin
description: "Use after changing the Noctalia plugin to run focused isolated tests, plugin lint, and panel syntax checks without altering the live session."
---

# Verify the Noctalia plugin

From the repository root, start with the affected test file:

```sh
PYTHONDONTWRITEBYTECODE=1 python -m unittest discover -s noctalia-plugin/tests -p 'test_user_dirs.py'
noctalia plugins lint noctalia-plugin/user-folders
luac -p noctalia-plugin/user-folders/panel.luau
luac -p noctalia-plugin/user-folders/bar.luau
luac -p noctalia-plugin/user-folders/keybind_ui.luau
```

- Use `test_default_apps.py` for default-app helper changes; run both files for shared or cross-section changes.
- Use `test_general.py` for General config changes, and `test_user_dirs.py` for its panel callbacks.
- Use `test_keybinds.py` and `test_user_dirs.py` for keybind helper and panel changes.
- Use `test_user_dirs.py` for the standalone launcher; its real-`gio` test skips if `gio` is unavailable.
- The panel harness is part of `test_user_dirs.py` and skips without `lua`. `luac` checks the current Lua-compatible panel syntax, not the Noctalia runtime; `noctalia plugins lint` checks manifest/settings and entry paths, not runtime rendering.
- If a tool is unavailable, report the skipped check. Do not install dependencies unless required by the task, run the AppImage build, or change the live shell/user config merely to verify.
- For actual GUI behavior, use a safely isolated host or report that live rendering was not tested.

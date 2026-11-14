---
name: test-noctalia-plugin
description: "Use when adding or fixing tests for the Noctalia plugin, its Luau panel, or its standalone Python helpers."
---

# Test the Noctalia plugin

- Use `unittest` under `noctalia-plugin/tests/`. `test_user_dirs.py` covers folder IO, the standalone launcher, and the panel and bar harnesses; `test_default_apps.py` covers MIME and app helpers; `test_general.py` and `test_keybinds.py` cover Umbriel config edits and validation.
- Run helpers as subprocesses with `XDG_CONFIG_HOME`, `XDG_DATA_HOME` and `XDG_DATA_DIRS` set to temporary paths as needed. Never write the real user configuration or mutate the live Noctalia session.
- Extend the existing `panel_test.lua` API mock for panel behavior and `bar_test.lua` for the widget. They test Lua-compatible code, not actual Noctalia rendering, and are skipped if `lua` is missing.
- Run one test file from the repository root:

  ```sh
  PYTHONDONTWRITEBYTECODE=1 python -m unittest discover -s noctalia-plugin/tests -p 'test_default_apps.py'
  ```

  Use `test_user_dirs.py` for the folder helper, launcher and panel harness. The real-`gio` launcher test uses an isolated fake app and skips if `gio` is unavailable. Then use `verify-noctalia-plugin` for plugin checks.

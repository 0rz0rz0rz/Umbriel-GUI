---
description: "Rules for the Noctalia plugin and its standalone helpers"
applyTo: "noctalia-plugin/**/*"
---

- The plugin is separate from the PySide6 app: use Luau and Noctalia's declarative UI, and keep Python helpers runnable with the standard library.
- Keep the plugin directory name equal to the suffix of its `author/plugin` ID. Preserve the existing panel entry ID and API compatibility unless the task explicitly changes them.
- Check the exact Noctalia release API before using newer features; `plugin_api` is a minimum feature level, not the Noctalia release number. See `noctalia-plugin/Noctalia API`.
- `panel.luau` keeps unsaved per-section state when navigating Back. Inputs are uncontrolled after creation: capture changes and use a new key when programmatically replacing text. Check async launch and result errors, stale callbacks, timeouts, and truncation.
- Use direct argv for helper calls; never construct shell commands from user input. Helpers must validate inputs and surface errors.
- Preserve unrelated file content and MIME fallbacks, external-change detection, backups, atomic writes and symlink protection. Never use real user config in tests.
- Use the matching plugin skills; validate with `verify-noctalia-plugin`. Do not change the live Noctalia session or user config solely to run tests.

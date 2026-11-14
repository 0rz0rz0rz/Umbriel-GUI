---
name: edit-noctalia-panel
description: "Use when changing the Noctalia plugin's panel, menu, forms, controls, navigation, or helper callbacks."
---

# Edit the Noctalia panel

- Locate only the relevant functions in `noctalia-plugin/user-folders/panel.luau`: `render`/`openSection` for navigation, `folderRows`/`browseFolder`/`appRows`/`appEditor` for controls, and `runHelper`/`reload`/`save` for IO.
- Folder browsing uses an external `zenity` or `kdialog` chooser with a 60-second timeout. Preserve the panel's outside-click setting, close control, cancellation and stale-callback behavior.
- Keep Back navigation's per-section unsaved state, disabled controls while busy, close/reopen generation checks, and explicit launch, timeout, truncation and helper errors.
- Native `ui.input` values seed only on creation; capture `onChange` and change the key when replacing the text. `ui.select` uses zero-based indices. Preserve stable keys and rerender when state-driven controls change.
- Run helpers using argv arrays and JSON, never shell interpolation. Keep the existing `author/plugin:entry` panel ID so configured bar buttons continue to work.
- The standalone launch button uses `launch_app.py` and the per-user desktop entry; keep the GUI detached from captured helper output and report launcher errors, including after the panel closes.
- Check API availability against the target Noctalia release, not just current online docs. Update `plugin_api` only if a feature requires it.
- Test callbacks and navigation using `test-noctalia-plugin`; run `verify-noctalia-plugin`. The mock and lint do not prove live rendering.

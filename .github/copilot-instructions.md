# Umbriel Settings: working rules

PySide6 + tomlkit GUI for the Umbriel TOML config. Code lives in `python/umbriel_config_gui/`.
Keep responses and changes small; the rules below exist to save tokens and credits.

## Navigating the code

- Module map: field specs `field_defs.py`, schema `schema.py`, form widgets `widgets.py`, form/FieldWidget `settings.py`, tables `tables.py`, keybinds `keybinds.py`, user dirs/default apps `desktop.py`, sidebar `sidebar.py`, entry editor `editors.py`. Largest: `window.py`, `settings.py`, `common.py` (~1000-1200 lines). Never read them whole. Use grep for `^class |^def |    def ` to locate a symbol, then view only that range.
- Ignore `__pycache__/`, `dist/`, `.venv/`, and the binary assets.
- Prefer grep/view in the main session. Do not start subagents for lookups or for files whose location is already known.
- Do not re-read a file after editing it; run the check instead.

## Saving credits

- Start with the smallest tool that answers: grep, then a short `view_range`. Batch independent reads into one call.
- When delegation is available, use the lowest-cost suitable agent/model for straightforward, well-defined work, such as an explicitly requested commit, push, or AppImage rebuild. Keep required checks and authorization intact; escalate if the task needs more reasoning or the agent is blocked.
- For a single setting use the `add-setting-field` skill; for tests `add-test`; for moving code `split-module`; for releases `build-appimage`.
- Keep modules under about 800 lines; split with the `split-module` skill when one grows past that.
- Do not paste long command output; use `| tail -n 15` or `| head -n 30`.
- Do not re-run the full suite after each edit; run the touched test file, then the full suite once before finishing.
- Never view `LICENSE`, `docs/screenshot.png`, `appimage/` build output, or generated files.
- Ask one concise question only when a choice changes behavior; otherwise decide and state the assumption.

## Verifying changes (run the smallest thing that covers the change)

- Syntax/import check: `cd python && python -c "import umbriel_config_gui.window"`
- Tests: `cd python && QT_QPA_PLATFORM=offscreen PYTHONPATH=. python -m unittest discover -s ../tests`
- Schema drift: `cd python && QT_QPA_PLATFORM=offscreen python umbriel-config-gui.py --check-schema`
- Do not rebuild the AppImage to verify code changes. It is slow and needs the network; build only when asked to release.

## Conventions

- Version lives only in `python/umbriel_config_gui/__init__.py` as `<Umbriel version>-<NNN>`.
- The project is GPL-3.0-only; keep `LICENSE` and the AppImage license bundling intact.
- Edits must keep TOML comments and formatting (tomlkit); only write keys the user changed.
- Comment only code that needs clarification. Do not add planning or notes files.

## Git and publishing

- Do not commit, push, tag, or publish unless asked. Never force-push or rewrite history without an explicit request.
- Commit messages are short and imperative.

## Output

- Be concise: report what changed and what was verified, not a walkthrough.
- No web searches for things answerable from the repo or the installed `umbriel` CLI.

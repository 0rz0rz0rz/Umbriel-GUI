# Umbriel Settings: working rules

PySide6 + tomlkit GUI for the Umbriel TOML config. Code lives in `python/umbriel_config_gui/`.
Keep responses and changes small; the rules below exist to save tokens and credits.

## Before changing anything

1. Find every file in `.github/instructions/` whose `applyTo` matches the files you will touch, and read it.
2. Check `.github/skills/` for a skill that matches the task, and load it before editing.
3. Only then start making changes.

## Navigating the code

- Module map: field specs `field_defs.py`, schema `schema.py`, shared controls `widgets.py`, field widgets `field_widget.py`, settings help `setting_help.py`, page layout `settings_layout.py`, tables `tables.py`, keybinds `keybinds.py`, user dirs/default apps `desktop.py`, sidebar `sidebar.py`, entry editor `editors.py`. Largest: `window.py` and `common.py` (~1000-1200 lines). Never read them whole. Use grep for `^class |^def |    def ` to locate a symbol, then view only that range.
- Ignore `__pycache__/`, `dist/`, `.venv/`, and the binary assets.

### Quick lookup (what lives where and how it connects)

| Need to change | Module | Key symbols |
| --- | --- | --- |
| App start, CLI, load/save flow | `window.py` | `main`, `Window`, `load_config_document`, `group_diff_by_section` |
| Config read/write, TOML edits | `common.py` | `read_config_state`, `rebuild_config`, `getp`/`putp`/`delp`, `create_backup_snapshot`, `parse_cli_args` |
| Field definitions (what settings exist) | `field_defs.py` | `F`, `Field`, `layout_fields`, `color_group`, `anim`, `regroup` |
| Schema from installed Umbriel | `schema.py` | `load_umbriel_schema`, `schema_field_catalog`, `check_schema_coverage` |
| Field controls and config write-back | `field_widget.py` | `FieldWidget`, `apply_fields`, `installed_cursor_themes` |
| Help text for settings | `setting_help.py` | `FIELD_HELP`, `GROUP_HELP`, `CATEGORY_HELP`, `setting_description` |
| Settings pages and collapsible groups | `settings_layout.py` | `form_page`, `CollapsibleGroup`, `SIDEBAR_SECTIONS`, group expansion state |
| Compatibility imports | `settings.py` | Re-exports settings symbols from their owning modules |
| Shared controls | `widgets.py` | `SettingRow`, `SettingLabel`, `SwitchCheckBox`, `TriStateControl`, `KdeColorControl`, `SettingSlider`, `FlowLayout` |
| Title bar KDE colors | `kde_titlebar.py` | `read_title_bar_colors`, `KdeTitleBarFollower` |
| Table and map editors | `tables.py` | `KVTable`, `RawValueMapEditor`, `AnimationCurvesPage`, `EffectsPage` |
| Keybinds | `keybinds.py` | `KeybindEditor`, `parse_keybind_groups`, `write_keybind_groups` |
| Actions | `actions.py` | `parse_actions`, `build_action_model`, `migrate_action` |
| Sidebar navigation and search | `sidebar.py` | `SideTabs`, `load_sidebar_order`, search loop (`setRowVisible`) |
| Entry editor | `editors.py` | `EntryEditor` |
| User dirs and default apps | `desktop.py` | `UserDirs`, `DefaultApps`, `update_mimeapps_defaults` |
| Qt palette from qt6ct/KDE | `qt6ct_theme.py` | `apply_qt6ct_theme`, `Qt6ctThemeFollower`, `build_palette` |
| Readable palettes, icons, paths | `common.py` | `readable_palette`, `PaletteReadability`, `create_app_icon`, `normalize_config_path` |

Data flow: `field_defs.py` declares each field; `schema.py` checks it against Umbriel; `form_page` in `settings_layout.py` builds one `FieldWidget` from `field_widget.py` per field using controls from `widgets.py`; `setting_help.py` supplies consistent field, group, and page descriptions; `common.py` reads and writes TOML with `getp`/`putp`; `window.py` ties pages, save, and diff review together.

### Where specific things live

| Question | Answer |
| --- | --- |
| Which pages/tabs exist, and their groups and fields | `TABS[<page>] = [(group title, [F(...), ...]), ...]` in `field_defs.py`; `window.py` builds one lazy `form_page` per `TABS` key |
| Sidebar order and sections | `SIDEBAR_SECTIONS` in `settings_layout.py` (user reorder saved via `sidebar.py`) |
| Help text under a label or in a `?` tooltip | `FIELD_HELP` (by field label), `GROUP_HELP` (by group title), `CATEGORY_HELP` (by page) in `setting_help.py`; `setting_description` assembles it. Search matches this text |
| Field kinds (`F(..., kind, ...)`) | `bool`, `int`, `float`, `str`, `choice`, `combo`, `color`, `list`, `strorlist`, `raw`, `command_list`; handled in `FieldWidget.__init__`, `set_value`, `get` |
| `opt=True` | Row gets an on/off switch (`FieldWidget.check`); `get()` returns `None` when off, so `apply_fields` deletes the key. A `bool` with `opt` becomes a 3-state control (`self.tri`: unset/on/off) |
| What gets written on save | `apply_fields(doc, fws)` in `field_widget.py`: writes only keys whose value changed (or optional ones); then `add_entry_name_comments` and `rebuild_config` in `common.py` |
| Save pipeline | `Window.save` in `window.py`: validate editors, `apply_fields`, `tomlkit.dumps`, `rebuild_config`, diff review (`confirm_save_diff`), `create_backup_snapshot`, `write_text_file`, then `umbriel config validate` in the background (`validated`) |
| Dirty tracking | `Window.track_page_changes` and `mark_dirty` |
| Title bar background/text colors and KDE import | `TITLE_BAR_KEYS`/`BACKGROUND_KEYS` in `kde_titlebar.py`; the `kde_*`, `opacity_*` methods and `KdeColorControl` in `FieldWidget`. Background colors also get an opacity row built in `form_page` (`fw.opacity_widget`/`opacity_row`) |
| Colors are `#RRGGBB` or `#RRGGBBAA` | `qcolor`/`hexof` in `common.py`; `FieldWidget.set_color` keeps the alpha channel in sync with the opacity slider |
| Process-wide state (config path, CLI args, schema options) | `state.py`: `PATH`, `_CLI_ARGS`, `ACTIVE_SCHEMA_OPTIONS`. Read as `state.PATH`, never `from state import PATH` (tests patch it) |
| Per-field schema info | `schema_path` passed to `FieldWidget`, looked up with `field_schema_option` (`schema.py`) |
| Search across pages | `SideTabs` search loop in `sidebar.py` hides rows with `form.setRowVisible(fw.search_row / fw.opacity_row, ...)`; any extra row added to a form must be hidden there too |
| Row layout | `SettingRow(label_widget, editor)` in `widgets.py`; editor row is `FieldWidget`'s `QHBoxLayout`: switch, slider, control, `?` button |
| GUI-only files (not in the config) | Global `common.GUI_DATA_DIR` (saved config path, sidebar order, group expansion); per-config `config_gui_data_dir(path)` (backups, `gui-labels.json`, locked keybinds) |
| Entry-style pages (rules, outputs, scratchpads, devices) | `EntryEditor` in `editors.py`, registered with `add_editor(...)` in `Window.__init__` using `WINDOW_RULE_GROUPS`, `OUTPUT_GROUPS`, `SCRATCHPAD`, etc. from `field_defs.py` |

### Tests and skills

- Tests in `tests/` are one file per area (`test_settings_sliders.py`, `test_settings_switches.py`, `test_save_workflow.py`, `test_kde_titlebar.py`, ...). Patch `state.PATH` and `state.ACTIVE_SCHEMA_OPTIONS` with `patch.object`, not real config files.
- Skills in `.github/skills/`: `add-setting-field`, `add-test`, `build-appimage`, `edit-controls`, `split-module`, `sync-umbriel-schema`, `verify-changes`.
- `window.py` and `common.py` are over the 800-line guideline; do not grow them further without using `split-module`. `settings.py` is a small compatibility facade; its implementation lives in `field_widget.py`, `setting_help.py`, and `settings_layout.py`.
## Saving credits

- Start with the smallest tool that answers: grep (use `output_mode: count` or `files_with_matches` first), then a short `view_range`. Batch independent reads and independent `edit` calls on the same file into one response. Review your own changes with `git diff --stat` or `git diff <file>`, not by viewing whole files.
- When delegation is available, use the lowest-cost suitable agent/model for straightforward, well-defined work, such as an explicitly requested commit, push, or AppImage rebuild. Keep required checks and authorization intact; escalate if the task needs more reasoning or the agent is blocked.
- For a single setting use the `add-setting-field` skill; for tests `add-test`; for moving code `split-module`; for releases `build-appimage`.
- Don't grow files already over 800 lines; split them with the `split-module` skill first.
- Do not paste long command output; use `| tail -n 15` or `| head -n 30`.
- Run only the tests needed to validate the change, starting with the smallest relevant selection. If a test fails, add or run focused tests to isolate the cause before broadening the run; run the full suite only when the change or failure scope requires it.
- Never view `LICENSE`, `docs/screenshot.png`, `appimage/` build output, or generated files.
- Ask one concise question only when a choice changes behavior; otherwise decide and state the assumption.

### Avoid these credit-wasting patterns

- **Don't use subagents for lookups**: Symbol location, file searches, and code inspection belong in the main session with grep/view/glob. Reserve agents for delegated implementation, reasoning, or multi-file refactors.
- **Don't re-read after editing**: After `edit`, go straight to validation. Skips redundant token overhead.
- **Don't explore "just in case"**: Only search/view files when the task explicitly requires changes to them. Avoid speculative walks through the codebase.

## Verifying changes (run the smallest thing that covers the change)

**Pick one based on your change:**
- **UI/widget changes** → import check + the matching test file (the import check only catches syntax and import errors)
- **Config read/write changes** → import check + targeted tests for that module
- **Adding a field** → import check + schema drift check
- **Changing logic** → import check + tests for that module
- **Refactoring across files** → import check + all tests (only when necessary)

**Specific commands:**
- Syntax/import check (fastest): `cd python && python -c "import umbriel_config_gui.window"`
- Tests for one file: `cd python && QT_QPA_PLATFORM=offscreen PYTHONPATH=. python -m unittest discover -s ../tests -p "test_settings_sliders.py"`
- Schema drift: `cd python && QT_QPA_PLATFORM=offscreen python umbriel-config-gui.py --check-schema`
- All tests: `cd python && QT_QPA_PLATFORM=offscreen PYTHONPATH=. python -m unittest discover -s ../tests`
- Do not rebuild the AppImage to verify code changes. It is slow and needs the network; build only when asked to release.
- Use the import check and targeted tests instead of running the app; use `--check-schema` for schema drift.
- Run checks in the main session. Use background tasks only for long builds or parallel work, not quick checks.
- Use full suites only when the change scope requires it.

## Conventions

- Version lives only in `python/umbriel_config_gui/__init__.py` as `<Umbriel version>-<NNN>`.
- The project is GPL-3.0-only; keep `LICENSE` and the AppImage license bundling intact.
- Edits must keep TOML comments and formatting (tomlkit); only write keys the user changed.
- Comment only code that needs clarification. Do not add planning or notes files.

## Git and publishing

- Do not commit, push, tag, or publish unless asked. Never force-push or rewrite history without an explicit request.
- Commit messages are short and imperative.

## Output

- No web searches for things answerable from the repo or the installed `umbriel` CLI.

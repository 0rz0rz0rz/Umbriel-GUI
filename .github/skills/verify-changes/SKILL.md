---
name: verify-changes
description: "Use after editing Python code in this repo to cheaply confirm nothing broke: import check, headless unit tests, and schema check, without building the AppImage."
---

# Verify changes cheaply

Start with the import check and the smallest test file covering the change:

```sh
cd python
python -c "import umbriel_config_gui.window"
QT_QPA_PLATFORM=offscreen PYTHONPATH=. python -m unittest discover -s ../tests -p test_entry_editor_layout.py
```

- Choose the matching test file: `test_entry_editor_layout.py` for entry and effects splitters; `test_sidebar.py` for search, overridden filtering, section shortcuts and pictograms; `test_keybind_ui.py` for the keybind splitter.
- Run the full suite (`QT_QPA_PLATFORM=offscreen PYTHONPATH=. python -m unittest discover -s ../tests`) only when the change scope requires it. Run the schema check (`QT_QPA_PLATFORM=offscreen python umbriel-config-gui.py --check-schema`) when fields or actions changed.
- Add new tests under `tests/` for behavior changes.
- Never build the AppImage just to verify code; use the `build-appimage` skill only for releases.

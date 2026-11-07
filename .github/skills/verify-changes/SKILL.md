---
name: verify-changes
description: "Use after editing Python code in this repo to cheaply confirm nothing broke: import check, headless unit tests, and schema check, without building the AppImage."
---

# Verify changes cheaply

Run from the repo root, stop at the first failure and fix it before continuing:

```sh
cd python
python -c "import umbriel_config_gui.window"
QT_QPA_PLATFORM=offscreen PYTHONPATH=. python -m unittest discover -s ../tests
QT_QPA_PLATFORM=offscreen python umbriel-config-gui.py --check-schema
```

- The import check covers every edit. Run the unit tests when behavior changed, and the schema check only when fields or actions changed.
- Add new tests under `tests/` for behavior changes.
- Run a single module when only one area changed, for example `python -m unittest discover -s ../tests -p test_save_workflow.py` with `QT_QPA_PLATFORM=offscreen PYTHONPATH=.`.
- Never build the AppImage just to verify code; use the `build-appimage` skill only for releases.

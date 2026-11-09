---
description: "Rules for editing or adding unit tests in this repo"
applyTo: "tests/**/*.py"
---

- Use `unittest` with offscreen Qt; see the `add-test` skill for imports and patch targets.
- Import settings symbols from their owning modules (`field_widget`, `setting_help`, or `settings_layout`); `settings` is only a compatibility facade. Patch names in the module where the implementation looks them up.
- Never read or write the real user config; use temporary directories.
- Run only the tests needed to validate the change, starting with the touched test file. If a test fails, add or run focused tests to isolate the cause before broadening the run; run the full suite only when the change or failure scope requires it.

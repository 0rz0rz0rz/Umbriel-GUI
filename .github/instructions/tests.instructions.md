---
description: "Rules for editing or adding unit tests in this repo"
applyTo: "tests/**/*.py"
---

- Use `unittest` with offscreen Qt; see the `add-test` skill for imports and patch targets.
- Never read or write the real user config; use temporary directories.
- Run only the touched test file while iterating, the full suite once at the end.

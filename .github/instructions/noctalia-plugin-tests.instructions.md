---
description: "Rules for testing the Noctalia plugin"
applyTo: "noctalia-plugin/tests/**/*"
---

- Follow `test-noctalia-plugin`: use `unittest`, temporary XDG directories and the existing Lua API mock, not real user config or a live shell.
- Add focused cases for changed behavior, especially helper error handling, config preservation, backups, external changes and panel callbacks.
- The Lua harness runs through the Python test and is skipped if `lua` is unavailable; report a skip rather than claiming UI callbacks were tested.
- Run the smallest relevant test file first; use `verify-noctalia-plugin` for lint and syntax checks.

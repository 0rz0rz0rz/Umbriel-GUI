import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

if sys.version_info >= (3, 11):
    import tomllib


HELPER = Path(__file__).resolve().parents[1] / "user-folders" / "keybinds.py"


@unittest.skipIf(sys.version_info < (3, 11), "Keybind settings require Python 3.11")
class KeybindPluginTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.path = self.root / "config.toml"
        self.backup = self.root / "backup"
        self.bin = self.root / "bin"
        self.bin.mkdir()
        validator = self.bin / "umbriel"
        validator.write_text(
            f"#!{sys.executable}\nimport json, os\n"
            "if os.environ.get('MUTATE_LOCK'):\n"
            "    open(os.environ['MUTATE_LOCK'], 'w').write('[\"Mod+A\"]')\n"
            "valid = os.environ.get('VALID', 'yes') == 'yes'\n"
            "print(json.dumps({'valid': valid, 'diagnostics': []}))\n"
            "raise SystemExit(0 if valid else 1)\n"
        )
        validator.chmod(0o755)
        self.env = {**os.environ, "XDG_DATA_HOME": str(self.root / "data"),
                    "PATH": str(self.bin) + os.pathsep + os.environ.get("PATH", "")}

    def helper(self, *args, success=True, env=None):
        result = subprocess.run(
            [sys.executable, str(HELPER), *args], env=env or self.env,
            text=True, capture_output=True, check=False,
        )
        self.assertEqual(result.returncode == 0, success, result.stderr)
        return json.loads(result.stdout) if success else result.stderr

    def read(self):
        return self.helper("read", str(self.path))

    def save(self, snapshot, changes, success=True, env=None):
        return self.helper("save", str(self.path), snapshot["revision"], snapshot["lock_revision"],
                           str(self.backup), json.dumps(changes), success=success, env=env)

    def lock_path(self):
        identity = hashlib.sha256(os.fsencode(str(self.path))).hexdigest()[:20]
        return self.root / "data" / "umbriel-config-gui" / "configs" / identity / "gui-locked-keybinds.json"

    def test_edit_add_remove_and_groups_preserve_other_content(self):
        original = (
            '[general]\nxwayland = true\n[keybinds]\n'
            '# Umbriel Config GUI keybind groups: {"groups":["Work"],"assignments":{"Mod+A":"Work"}}\n'
            '"Mod+A" = { action = "spawn foo", repeat = true, custom = "keep" }   # comment\n'
            '"Mod+B" = "window-close"\n'
        )
        self.path.write_text(original)
        loaded = self.read()
        self.assertEqual(loaded["bindings"][0]["group"], "Work")
        updated = self.save(loaded, [
            {"key": "Mod+A", "remove": False, "mode": "toml", "value": '{ action = "spawn bar", repeat = true, custom = "keep" }'},
            {"key": "Mod+B", "remove": True, "value": ""},
            {"key": "Mod+C", "remove": False, "mode": "action", "value": "window-close"},
        ])
        text = self.path.read_text()
        parsed = tomllib.loads(text)
        self.assertEqual(parsed["keybinds"]["Mod+A"]["custom"], "keep")
        self.assertEqual(parsed["keybinds"]["Mod+C"], "window-close")
        self.assertNotIn("Mod+B", parsed["keybinds"])
        self.assertIn('custom = "keep" }   # comment', text)
        self.assertEqual(parsed["general"]["xwayland"], True)
        identity = hashlib.sha256(os.fsencode(str(self.path))).hexdigest()[:20]
        self.assertEqual((self.backup / f"umbriel-config-{identity}.bak").read_text(), original)
        self.save(updated, [{"key": "Mod+A", "remove": True, "value": ""}])
        self.assertIn('"assignments":{}', self.path.read_text())
        self.assertIn("# comment", self.path.read_text())

    def test_refuses_locked_and_external_changes(self):
        original = '[keybinds]\n"Mod+A" = "window-close"\n'
        self.path.write_text(original)
        lock = self.lock_path()
        lock.parent.mkdir(parents=True)
        lock.write_text('["Mod+A"]')
        loaded = self.read()
        self.assertTrue(loaded["bindings"][0]["locked"])
        change = [{"key": "Mod+A", "remove": True, "value": ""}]
        self.assertIn("locked", self.save(loaded, change, success=False))
        lock.write_text("[]")
        self.assertIn("locks changed", self.save(loaded, change, success=False))
        fresh = self.read()
        self.path.write_text(original + "# external\n")
        self.assertIn("changed externally", self.save(fresh, change, success=False))
        self.assertEqual(self.path.read_text(), original + "# external\n")

    def test_validation_failure_symlink_and_lock_race_are_safe(self):
        original = '[keybinds]\n"Mod+A" = "window-close"\n'
        self.path.write_text(original)
        change = [{"key": "Mod+A", "remove": False, "mode": "action", "value": "spawn editor"}]
        loaded = self.read()
        self.assertIn("validation failed", self.save(loaded, change, success=False, env={**self.env, "VALID": "no"}))
        self.assertEqual(self.path.read_text(), original)
        lock = self.lock_path()
        lock.parent.mkdir(parents=True)
        env = {**self.env, "MUTATE_LOCK": str(lock)}
        self.assertIn("changed during saving", self.save(loaded, change, success=False, env=env))
        self.assertEqual(self.path.read_text(), original)
        self.assertFalse(self.backup.exists())
        target = self.root / "target.toml"
        self.path.rename(target)
        self.path.symlink_to(target)
        self.assertIn("symlink", self.save(self.read(), change, success=False))
        self.assertEqual(target.read_text(), original)

    def test_invalid_and_unsupported_edits_are_not_written(self):
        for original, change in (
            ('[keybinds]\n"Mod+A" = "window-close"\n',
             {"key": "Mod+A", "remove": False, "mode": "toml", "value": '"ok"\n[general]\nxwayland = false'}),
            ('[keybinds."Mod+A"]\naction = "window-close"\n',
             {"key": "Mod+A", "remove": True, "value": ""}),
            ('[keybinds]\n"Mod+A" = "window-close"\n',
             {"key": "mod+a", "remove": False, "mode": "action", "value": "window-close"}),
        ):
            with self.subTest(original=original, change=change):
                self.path.write_text(original)
                self.save(self.read(), [change], success=False)
                self.assertEqual(self.path.read_text(), original)
                self.assertFalse(self.backup.exists())

    @unittest.skipUnless(shutil.which("umbriel"), "Umbriel CLI is required")
    def test_real_umbriel_validation(self):
        self.path.write_text('[keybinds]\n"Mod+A" = "window-close"\n')
        env = {**self.env, "PATH": os.environ.get("PATH", "")}
        loaded = self.read()
        result = self.save(loaded, [
            {"key": "Mod+A", "remove": False, "mode": "action", "value": "window-toggle-fullscreen"},
        ], env=env)
        self.assertIn("revision", result)


if __name__ == "__main__":
    unittest.main()

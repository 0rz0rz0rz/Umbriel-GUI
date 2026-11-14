import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest


HELPER = Path(__file__).resolve().parents[1] / "user-folders" / "general.py"


@unittest.skipIf(sys.version_info < (3, 11), "General requires Python 3.11")
class GeneralPluginTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.config = self.root / "config.toml"
        self.backup = self.root / "backup"
        self.bin = self.root / "bin"
        self.bin.mkdir()
        validator = self.bin / "umbriel"
        validator.write_text(
            f"#!{sys.executable}\n"
            "import json, os\n"
            "valid = os.environ.get('VALID', 'yes') == 'yes'\n"
            "print(json.dumps({'valid': valid, 'diagnostics': [] if valid else "
            "[{'severity': 'error', 'message': 'invalid config'}]}))\n"
            "raise SystemExit(0 if valid else 1)\n"
        )
        validator.chmod(0o755)
        self.env = {
            **os.environ,
            "PATH": str(self.bin) + os.pathsep + os.environ.get("PATH", ""),
            "XDG_DATA_HOME": str(self.root / "data"),
        }

    def helper(self, *args, success=True, env=None):
        result = subprocess.run(
            [sys.executable, str(HELPER), *args], env=env or self.env,
            text=True, capture_output=True, check=False,
        )
        self.assertEqual(result.returncode == 0, success, result.stderr)
        return json.loads(result.stdout) if success else result.stderr

    def read(self):
        return self.helper("read", str(self.config))

    def save(self, revision, changes, success=True, env=None):
        return self.helper(
            "save", str(self.config), revision, str(self.backup), json.dumps(changes),
            success=success, env=env,
        )

    def test_edit_preserves_content_backup_and_optional_values(self):
        original = (
            '# header\n[general]\nshow_cheatsheet   =    true   # keep me\n'
            'autostart = [\n  "one",\n  "two",\n]\n'
            '[keybinds]\n"Super+equal=key" = "value"\n'
        )
        self.config.write_text(original)
        loaded = self.read()
        changes = [
            {"key": "general.show_cheatsheet", "present": True, "value": "false"},
            {"key": "general.autostart", "present": True, "value": '["one", "three"]'},
            {"key": "include.optional.files", "present": True, "value": '["a.toml"]'},
        ]
        result = self.save(loaded["revision"], changes)
        text = self.config.read_text()
        self.assertIn("show_cheatsheet   =    false   # keep me", text)
        self.assertIn('autostart = ["one", "three"]', text)
        self.assertIn('"Super+equal=key" = "value"', text)
        self.assertIn('[include.optional]\nfiles = ["a.toml"]', text)
        self.assertTrue(result["values"]["general.show_cheatsheet"]["present"])
        self.assertEqual(result["values"]["general.show_cheatsheet"]["value"], "false")
        identity = hashlib.sha256(os.fsencode(str(self.config))).hexdigest()[:20]
        self.assertEqual((self.backup / f"umbriel-config-{identity}.bak").read_text(), original)
        self.save(result["revision"], [
            {"key": "general.show_cheatsheet", "present": False, "value": "false"},
        ])
        self.assertIn("# keep me", self.config.read_text())
        self.assertNotIn("show_cheatsheet =", self.config.read_text())

    def test_conflict_symlink_invalid_input_and_validation_failure_do_not_write(self):
        original = "[general]\nshow_cheatsheet = true\n"
        self.config.write_text(original)
        rev = self.read()["revision"]
        change = [{"key": "general.show_cheatsheet", "present": True, "value": "false"}]
        self.config.write_text(original + "# external\n")
        self.assertIn("changed externally", self.save(rev, change, success=False))
        rev = self.read()["revision"]
        invalid_env = {**self.env, "VALID": "no"}
        self.assertIn("invalid config", self.save(rev, change, success=False, env=invalid_env))
        self.assertEqual(self.config.read_text(), original + "# external\n")
        self.assertFalse(self.backup.exists())
        self.assertIn("JSON array", self.save(rev, [
            {"key": "general.autostart", "present": True, "value": '[42]'},
        ], success=False))
        target = self.root / "target.toml"
        self.config.rename(target)
        self.config.symlink_to(target)
        self.assertIn("symlink", self.save(rev, change, success=False))
        self.assertEqual(target.read_text(), original + "# external\n")

    def test_unsupported_layouts_refuse_to_drop_comments_or_other_keys(self):
        for original, change in (
            ('[general]\nautostart = [\n "one", # keep\n]\n',
             {"key": "general.autostart", "present": True, "value": '["two"]'}),
            ('general = { show_cheatsheet = true, xwayland = true }\n',
             {"key": "general.show_cheatsheet", "present": True, "value": "false"}),
        ):
            with self.subTest(original=original):
                self.config.write_text(original)
                self.save(self.read()["revision"], [change], success=False)
                self.assertEqual(self.config.read_text(), original)
                self.assertFalse(self.backup.exists())

    def test_default_path_uses_standalone_selection(self):
        self.config.write_text("[general]\n")
        selection = self.root / "data" / "umbriel-config-gui" / "gui-config-path"
        selection.parent.mkdir(parents=True)
        selection.write_text(str(self.config))
        loaded = self.helper("read")
        self.assertEqual(loaded["path"], str(self.config))
        self.assertFalse(loaded["values"]["general.mod_key"]["present"])

    def test_inserts_into_final_header_without_newline(self):
        self.config.write_bytes(b"[general]")
        self.save(self.read()["revision"], [
            {"key": "general.xwayland", "present": True, "value": "false"},
        ])
        self.assertEqual(self.config.read_bytes(), b"[general]\nxwayland = false\n")

    @unittest.skipUnless(shutil.which("umbriel"), "Umbriel CLI is required")
    def test_real_validation_resolves_relative_includes_and_blocks_invalid_values(self):
        (self.root / "included.toml").write_text("[events]\nlid_open = 'echo open'\n")
        original = '[include]\nfiles = ["included.toml"]\n[general]\nmod_key = "Super"\n'
        self.config.write_text(original)
        env = {**self.env, "PATH": os.environ.get("PATH", "")}
        loaded = self.read()
        saved = self.save(loaded["revision"], [
            {"key": "general.mod_key", "present": True, "value": "Alt"},
        ], env=env)
        saved_text = self.config.read_text()
        self.assertIn('mod_key = "Alt"', saved_text)
        error = self.save(saved["revision"], [
            {"key": "general.mod_key", "present": True, "value": "NotAModifier"},
        ], success=False, env=env)
        self.assertIn("Umbriel validation failed", error)
        self.assertEqual(self.config.read_text(), saved_text)


if __name__ == "__main__":
    unittest.main()

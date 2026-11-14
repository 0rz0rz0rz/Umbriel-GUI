import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


HELPER = Path(__file__).resolve().parents[1] / "user-folders" / "default_apps.py"


class DefaultAppsPluginTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.path = self.root / "config" / "mimeapps.list"
        self.backup = self.root / "backup"
        self.env = {
            **os.environ,
            "XDG_CONFIG_HOME": str(self.path.parent),
            "XDG_DATA_HOME": str(self.root / "data"),
            "XDG_DATA_DIRS": str(self.root / "system"),
            "PYTHONDONTWRITEBYTECODE": "1",
        }

    def helper(self, *args, success=True):
        result = subprocess.run(
            [sys.executable, str(HELPER), *args],
            env=self.env, text=True, capture_output=True, check=False,
        )
        self.assertEqual(result.returncode == 0, success, result.stderr)
        return json.loads(result.stdout) if success else result.stderr

    def save(self, revision, changes, success=True):
        return self.helper("save", revision, str(self.backup), json.dumps(changes), success=success)

    def test_role_and_mime_changes_preserve_fallbacks_and_unrelated_sections(self):
        self.path.parent.mkdir()
        original = (
            "# comment\n[Default Applications]\n"
            "text/html=old.desktop;fallback.desktop;\napplication/json=json.desktop;\n"
            "[Added Associations]\ntext/html=other.desktop;\n"
        )
        self.path.write_text(original)
        loaded = self.helper("read")
        self.assertEqual(loaded["roles"]["Web browser"], "<multiple>")
        self.assertEqual(loaded["mimes"]["application/json"], "json.desktop")
        saved = self.save(loaded["revision"], [
            {"kind": "role", "key": "Web browser", "value": "new.desktop"},
            {"kind": "mime", "key": "application/json", "value": ""},
            {"kind": "mime", "key": "application/example", "value": "example.desktop"},
        ])
        text = self.path.read_text()
        self.assertIn("text/html=new.desktop;old.desktop;fallback.desktop;", text)
        self.assertIn("application/example=example.desktop;", text)
        self.assertNotIn("application/json=", text)
        self.assertIn("[Added Associations]\ntext/html=other.desktop;", text)
        self.assertEqual((self.backup / "mimeapps.list.bak").read_text(), original)
        self.assertEqual(saved["roles"]["Web browser"], "new.desktop")

    def test_external_changes_and_invalid_updates_are_rejected(self):
        loaded = self.helper("read")
        self.path.parent.mkdir()
        self.path.write_text("# external\n")
        changes = [{"kind": "role", "key": "Web browser", "value": "test.desktop"}]
        self.assertIn("changed externally", self.save(loaded["revision"], changes, success=False))
        loaded = self.helper("read")
        for change in (
            {"kind": "mime", "key": "text/html", "value": "test.desktop"},
            {"kind": "mime", "key": "bad", "value": "test.desktop"},
            {"kind": "mime", "key": "application/json", "value": "bad;id"},
        ):
            self.save(loaded["revision"], [change], success=False)
        self.assertEqual(self.path.read_text(), "# external\n")

    def test_discovers_apps_and_resolves_extensions(self):
        appdir = self.root / "data" / "applications"
        appdir.mkdir(parents=True)
        (appdir / "example.desktop").write_text("[Desktop Entry]\nType=Application\nName=Example\n")
        (appdir / "hidden.desktop").write_text("[Desktop Entry]\nName=Hidden\nHidden=true\n")
        loaded = self.helper("read")
        self.assertEqual(loaded["apps"], [{"id": "example.desktop", "name": "Example"}])
        self.assertEqual(self.helper("extension", ".pdf")["mime"], "application/pdf")
        self.helper("extension", "bad/extension", success=False)

    def test_symlink_is_not_replaced(self):
        self.path.parent.mkdir()
        target = self.root / "target"
        target.write_text("[Default Applications]\n")
        self.path.symlink_to(target)
        loaded = self.helper("read")
        changes = [{"kind": "role", "key": "File manager", "value": "files.desktop"}]
        self.assertIn("symlink", self.save(loaded["revision"], changes, success=False))
        self.assertTrue(self.path.is_symlink())
        self.assertEqual(target.read_text(), "[Default Applications]\n")


if __name__ == "__main__":
    unittest.main()

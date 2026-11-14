import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import time
import unittest


ROOT = Path(__file__).resolve().parents[1]
PLUGIN = ROOT / "user-folders"
HELPER = PLUGIN / "user_dirs.py"


class UserFoldersPluginTests(unittest.TestCase):
    def test_plugin_directory_matches_manifest_id(self):
        manifest = (PLUGIN / "plugin.toml").read_text()
        match = re.search(r'^id\s*=\s*"([^"]+)"', manifest, re.MULTILINE)
        self.assertIsNotNone(match)
        self.assertEqual(match.group(1).split("/")[-1], PLUGIN.name)

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.path = self.root / "config" / "user-dirs.dirs"
        self.backup = self.root / "backup"
        self.env = {**os.environ, "XDG_CONFIG_HOME": str(self.path.parent)}

    def helper(self, *args, success=True):
        result = subprocess.run(
            [sys.executable, str(HELPER), *args],
            env=self.env, text=True, capture_output=True, check=False,
        )
        self.assertEqual(result.returncode == 0, success, result.stderr)
        return json.loads(result.stdout) if success else result.stderr

    def save(self, revision, values, success=True):
        return self.helper("save", revision, str(self.backup), json.dumps(values), success=success)

    def test_save_preserves_other_entries_and_makes_backup(self):
        self.path.parent.mkdir()
        original = '# User folders\nXDG_DOCUMENTS_DIR="$HOME/Documents"\nXDG_CUSTOM_DIR="/old"\n'
        self.path.write_text(original)
        loaded = self.helper("read")
        self.assertEqual(loaded["values"]["DOCUMENTS"], "$HOME/Documents")
        saved = self.save(loaded["revision"], {
            "DOCUMENTS": "$HOME/Work",
            "MUSIC": "/data/My Music",
        })
        self.assertEqual(saved["values"]["MUSIC"], "/data/My Music")
        self.assertEqual(
            self.path.read_text(),
            '# User folders\nXDG_DOCUMENTS_DIR="$HOME/Work"\nXDG_CUSTOM_DIR="/old"\n'
            'XDG_MUSIC_DIR="/data/My Music"\n',
        )
        self.assertEqual((self.backup / "user-dirs.dirs.bak").read_text(), original)
        self.save(saved["revision"], {"MUSIC": ""})
        self.assertNotIn("XDG_MUSIC_DIR", self.path.read_text())

    def test_missing_file_and_external_change_detection(self):
        loaded = self.helper("read")
        self.assertEqual(loaded["revision"], "missing")
        self.save(loaded["revision"], {"DOWNLOAD": "$HOME/Downloads"})
        self.assertEqual(self.path.read_text(), 'XDG_DOWNLOAD_DIR="$HOME/Downloads"\n')
        self.assertFalse(self.backup.exists())
        loaded = self.helper("read")
        self.path.write_text("# external edit\n")
        error = self.save(loaded["revision"], {"DOWNLOAD": "/other"}, success=False)
        self.assertIn("changed externally", error)
        self.assertEqual(self.path.read_text(), "# external edit\n")

    def test_rejects_unsafe_values_without_writing(self):
        loaded = self.helper("read")
        for value in ("relative", '/tmp/$(touch bad)', '/tmp/"bad', "/tmp/`bad`", "/tmp/bad\n"):
            with self.subTest(value=value):
                self.save(loaded["revision"], {"MUSIC": value}, success=False)
                self.assertFalse(self.path.exists())

    def test_refuses_to_replace_symlink(self):
        self.path.parent.mkdir()
        target = self.root / "linked-dirs"
        target.write_text('XDG_MUSIC_DIR="/old"\n')
        self.path.symlink_to(target)
        loaded = self.helper("read")
        error = self.save(loaded["revision"], {"MUSIC": "/new"}, success=False)
        self.assertIn("symlink", error)
        self.assertTrue(self.path.is_symlink())
        self.assertEqual(target.read_text(), 'XDG_MUSIC_DIR="/old"\n')

    def test_standalone_launcher_checks_entry_and_reports_errors(self):
        data = self.root / "data with spaces"
        desktop = data / "applications" / "umbriel-config-gui.desktop"
        bin_dir = self.root / "bin"
        bin_dir.mkdir()
        log = self.root / "launch-args"
        env = {
            **self.env, "XDG_DATA_HOME": str(data), "PATH": str(bin_dir),
            "LAUNCH_LOG": str(log),
        }

        def launch(**extra_env):
            return subprocess.run(
                [sys.executable, str(PLUGIN / "launch_app.py")],
                env={**env, **extra_env}, text=True, capture_output=True, check=False,
            )

        result = launch()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("desktop entry not found", result.stderr)
        desktop.parent.mkdir(parents=True)
        desktop.write_text("[Desktop Entry]\n")
        result = launch()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("gio is not installed", result.stderr)
        gio = bin_dir / "gio"
        gio.write_text('#!/bin/sh\nprintf "%s\\n" "$@" > "$LAUNCH_LOG"\nexit "${LAUNCH_EXIT:-0}"\n')
        gio.chmod(0o755)
        result = launch()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout), {})
        self.assertEqual(log.read_text().splitlines(), ["launch", str(desktop)])
        result = launch(LAUNCH_EXIT="9")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("exit code 9", result.stderr)

    @unittest.skipUnless(shutil.which("gio"), "gio is required for the launcher integration test")
    def test_standalone_launcher_detaches_app_output(self):
        data = self.root / "data"
        desktop = data / "applications" / "umbriel-config-gui.desktop"
        desktop.parent.mkdir(parents=True)
        marker = self.root / "app-ran"
        app = self.root / "fake-app"
        app.write_text('#!/bin/sh\nsleep 0.3\nprintf "app output\\n" >&2\nprintf ready > "$LAUNCH_LOG"\n')
        app.chmod(0o755)
        desktop.write_text(f"[Desktop Entry]\nType=Application\nName=Test\nExec={app}\n")
        runtime = self.root / "runtime"
        runtime.mkdir(mode=0o700)
        env = {
            **self.env, "HOME": str(self.root), "XDG_DATA_HOME": str(data),
            "XDG_RUNTIME_DIR": str(runtime), "DBUS_SESSION_BUS_ADDRESS": "unix:path=/nonexistent",
            "DISPLAY": "", "WAYLAND_DISPLAY": "", "LAUNCH_LOG": str(marker),
        }
        result = subprocess.run(
            [sys.executable, str(PLUGIN / "launch_app.py")],
            env=env, text=True, capture_output=True, timeout=5, check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        deadline = time.monotonic() + 3
        while not marker.exists() and time.monotonic() < deadline:
            time.sleep(0.05)
        self.assertEqual(marker.read_text(), "ready")

    @unittest.skipUnless(shutil.which("lua"), "lua is required for the panel harness")
    def test_panel_load_edit_save_and_failure(self):
        subprocess.run(
            ["lua", str(ROOT / "tests" / "panel_test.lua"), str(PLUGIN / "panel.luau"),
             str(PLUGIN / "keybind_ui.luau")],
            check=True,
        )

    @unittest.skipUnless(shutil.which("lua"), "lua is required for the bar harness")
    def test_bar_button_toggles_plugin_panel(self):
        manifest = (PLUGIN / "plugin.toml").read_text()
        self.assertRegex(manifest, r'\[\[widget\]\]\s+id\s*=\s*"settings"\s+entry\s*=\s*"bar\.luau"')
        subprocess.run(
            ["lua", str(ROOT / "tests" / "bar_test.lua"), str(PLUGIN / "bar.luau")],
            check=True,
        )


if __name__ == "__main__":
    unittest.main()

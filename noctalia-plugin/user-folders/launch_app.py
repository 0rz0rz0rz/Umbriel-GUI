"""Launch the standalone app through its per-user desktop entry."""

import json
import os
from pathlib import Path
import shutil
import subprocess
import sys


def main():
    data_home = Path(os.environ.get("XDG_DATA_HOME") or Path.home() / ".local" / "share")
    desktop = data_home / "applications" / "umbriel-config-gui.desktop"
    if not desktop.is_file():
        raise ValueError("Standalone desktop entry not found. Run Umbriel Settings once first.")
    gio = shutil.which("gio")
    if not gio:
        raise ValueError("Cannot launch the standalone app: gio is not installed.")
    try:
        result = subprocess.run(
            [gio, "launch", str(desktop)], stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            start_new_session=True, timeout=10, check=False,
        )
    except subprocess.TimeoutExpired as error:
        raise ValueError("Desktop launcher timed out; the app may still open.") from error
    if result.returncode:
        raise ValueError(f"Desktop launcher failed (exit code {result.returncode}).")
    print(json.dumps({}))


if __name__ == "__main__":
    try:
        main()
    except (OSError, ValueError) as error:
        print(str(error), file=sys.stderr)
        sys.exit(1)

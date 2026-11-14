"""Read and update XDG user folder paths for the Noctalia plugin."""

import hashlib
import json
import os
from pathlib import Path
import re
import stat
import sys
import tempfile


ENTRY = re.compile(r'^\s*XDG_([A-Z]+)_DIR\s*=\s*"(.*)"\s*$')
KEY = re.compile(r"^[A-Z]+$")


def config_path():
    return Path(os.environ.get("XDG_CONFIG_HOME") or Path.home() / ".config") / "user-dirs.dirs"


def read_document(path):
    try:
        contents = path.read_bytes()
    except FileNotFoundError:
        return "", "missing"
    return contents.decode("utf-8"), hashlib.sha256(contents).hexdigest()


def snapshot(text, revision):
    values = {}
    for line in text.splitlines():
        match = ENTRY.fullmatch(line)
        if match:
            values[match.group(1)] = match.group(2)
    return {"values": values, "revision": revision}


def validate_changes(changes):
    if not isinstance(changes, dict):
        raise ValueError("Changes must be an object.")
    for key, value in changes.items():
        if not isinstance(key, str) or not KEY.fullmatch(key) or not isinstance(value, str):
            raise ValueError("Invalid folder name or path.")
        if not value:
            continue
        if not (value.startswith("/") or value == "$HOME" or value.startswith("$HOME/")):
            raise ValueError(f"{key}: use an absolute path or $HOME/path.")
        remainder = value[5:] if value.startswith("$HOME") else value
        if any(char in remainder for char in '$`"\\\r\n') or "\0" in value:
            raise ValueError(f"{key}: path contains unsupported shell characters.")


def atomic_write(path, data, mode=0o600):
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_name = None
    try:
        with tempfile.NamedTemporaryFile(dir=path.parent, delete=False) as tmp:
            tmp_name = tmp.name
            os.fchmod(tmp.fileno(), mode)
            tmp.write(data)
        os.replace(tmp_name, path)
    finally:
        if tmp_name and os.path.exists(tmp_name):
            os.unlink(tmp_name)


def save(path, backup_dir, expected_revision, changes):
    validate_changes(changes)
    if path.is_symlink():
        raise ValueError("User folders file is a symlink; edit its target directly.")
    text, revision = read_document(path)
    if revision != expected_revision:
        raise ValueError("User folders changed externally. Reload before saving.")
    output = []
    seen = set()
    for line in text.splitlines(keepends=True):
        match = ENTRY.fullmatch(line.rstrip("\r\n"))
        if match and match.group(1) in changes:
            key = match.group(1)
            seen.add(key)
            if changes[key]:
                output.append(f'XDG_{key}_DIR="{changes[key]}"\n')
        else:
            output.append(line)
    for key, value in changes.items():
        if key not in seen and value:
            if output and not output[-1].endswith(("\n", "\r")):
                output[-1] += "\n"
            output.append(f'XDG_{key}_DIR="{value}"\n')
    updated = "".join(output).encode("utf-8")
    if revision != "missing":
        atomic_write(backup_dir / "user-dirs.dirs.bak", text.encode("utf-8"))
        mode = stat.S_IMODE(path.stat().st_mode)
    else:
        mode = 0o600
    atomic_write(path, updated, mode)
    return snapshot(updated.decode("utf-8"), hashlib.sha256(updated).hexdigest())


def main(args):
    path = config_path()
    if args == ["read"]:
        text, revision = read_document(path)
        result = snapshot(text, revision)
    elif len(args) == 4 and args[0] == "save":
        result = save(path, Path(args[2]), args[1], json.loads(args[3]))
    else:
        raise ValueError("Usage: user_dirs.py read | save REVISION BACKUP_DIR CHANGES_JSON")
    print(json.dumps(result, ensure_ascii=False))


if __name__ == "__main__":
    try:
        main(sys.argv[1:])
    except (OSError, UnicodeError, ValueError) as error:
        print(str(error), file=sys.stderr)
        sys.exit(1)

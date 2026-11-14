"""Read and safely edit General settings without importing the desktop GUI."""

import copy
import hashlib
import json
import os
from pathlib import Path
import stat
import subprocess
import sys
import tempfile

if sys.version_info < (3, 11):
    sys.exit("General settings require Python 3.11 or newer.")

import tomllib

from user_dirs import atomic_write, read_document


FIELDS = {
    "general.autostart": "array",
    "general.mod_key": "string",
    "general.show_cheatsheet": "bool",
    "general.focus_on_activate": "bool",
    "general.attach_modal_dialogs": "bool",
    "general.honor_restored_maximize": "bool",
    "general.nvidia_sync_workaround": "bool",
    "general.xwayland": "bool",
    "general.xwayland_native_resolution": "bool",
    "general.xwayland_xsettings": "bool",
    "general.xwayland_primary_output": "string",
    "events.lid_close": "string",
    "events.lid_open": "string",
    "screencast.disable_dynamic_confirmation": "bool",
    "drm.ignored_devices": "array",
    "drm.ignored_pci_addresses": "array",
    "include.files": "array",
    "include.optional.files": "array",
}


def default_path():
    data_home = Path(os.environ.get("XDG_DATA_HOME") or Path.home() / ".local/share")
    saved = data_home / "umbriel-config-gui" / "gui-config-path"
    try:
        selected = saved.read_text(encoding="utf-8").strip()
    except FileNotFoundError:
        selected = ""
    return Path(os.path.abspath(os.path.expanduser(selected or "~/.config/umbriel/config.toml")))


def get_value(document, parts):
    value = document
    for part in parts:
        if not isinstance(value, dict) or part not in value:
            return None, False
        value = value[part]
    return value, True


def valid_value(kind, value):
    return (
        (kind == "bool" and isinstance(value, bool))
        or (kind == "string" and isinstance(value, str))
        or (kind == "array" and isinstance(value, list) and all(isinstance(item, str) for item in value))
    )


def snapshot(path, text, revision):
    if revision == "missing":
        raise ValueError(f"Config file does not exist: {path}")
    document = tomllib.loads(text)
    values = {}
    for key, kind in FIELDS.items():
        value, present = get_value(document, key.split("."))
        if present and not valid_value(kind, value):
            raise ValueError(f"{key}: unsupported value type in config.")
        values[key] = {
            "present": present,
            "value": json.dumps(value, ensure_ascii=False) if kind != "string" and present
            else value if present else "[]" if kind == "array" else "",
        }
    return {"path": str(path), "revision": revision, "values": values}


def key_parts(key):
    parsed = tomllib.loads(key + " = 0")
    parts = []
    while isinstance(parsed, dict) and len(parsed) == 1:
        name, parsed = next(iter(parsed.items()))
        parts.append(name)
    if parsed != 0:
        raise ValueError("Unsupported TOML key.")
    return parts


def header_parts(header):
    parsed = tomllib.loads(header + "\n")
    parts = []
    while isinstance(parsed, dict) and len(parsed) == 1:
        name, parsed = next(iter(parsed.items()))
        parts.append(name)
    return parts if parsed == {} else None


def assignment_separator(assignment):
    for index, char in enumerate(assignment):
        if char == "=":
            try:
                parts = key_parts(assignment[:index].strip())
            except tomllib.TOMLDecodeError:
                continue
            return index, parts
    raise ValueError("Could not locate a TOML key safely.")


def statements(text):
    """Locate complete assignments, using tomllib to recognize multiline values."""
    lines = text.splitlines(keepends=True)
    result = []
    table = []
    index = 0
    while index < len(lines):
        start = index
        stripped = lines[index].strip()
        if not stripped or stripped.startswith("#"):
            index += 1
            continue
        if stripped.startswith("["):
            table = header_parts(stripped) if not stripped.startswith("[[") else None
            result.append(("header", table, start, start + 1))
            index += 1
            continue
        assignment = ""
        while index < len(lines):
            assignment += lines[index]
            index += 1
            try:
                tomllib.loads(assignment)
                break
            except tomllib.TOMLDecodeError:
                continue
        else:
            raise ValueError("Could not locate a TOML assignment safely.")
        _, key = assignment_separator(assignment)
        parts = table + key if table is not None else None
        result.append(("assignment", parts, start, index))
    return lines, result


def render_value(kind, value):
    if kind == "bool":
        if value not in ("true", "false"):
            raise ValueError("Expected true or false.")
        return value, value == "true"
    if kind == "array":
        if not isinstance(value, str):
            raise ValueError("Expected a JSON array of strings.")
        value = json.loads(value)
        if not valid_value(kind, value):
            raise ValueError("Expected a JSON array of strings.")
        return json.dumps(value, ensure_ascii=False), value
    if not isinstance(value, str):
        raise ValueError("Expected text.")
    return json.dumps(value, ensure_ascii=False), value


def edit(text, key, present, encoded):
    parts = key.split(".")
    lines, entries = statements(text)
    matches = [entry for entry in entries if entry[0] == "assignment" and entry[1] == parts]
    if len(matches) > 1:
        raise ValueError(f"{key}: multiple assignments cannot be edited safely.")
    if matches:
        _, _, start, end = matches[0]
        old = "".join(lines[start:end])
        if end - start > 1 and "#" in old:
            raise ValueError(f"{key}: multiline values with comments must be edited in the standalone app.")
        comment = ""
        comment_spacing = ""
        if end - start == 1:
            for index, char in enumerate(old):
                if char == "#":
                    try:
                        tomllib.loads(old[:index] + "\n")
                    except tomllib.TOMLDecodeError:
                        continue
                    comment = old[index:].rstrip("\r\n")
                    comment_spacing = old[:index][len(old[:index].rstrip(" \t")):]
                    break
        newline = "\r\n" if old.endswith("\r\n") else "\n" if old.endswith("\n") else ""
        separator, _ = assignment_separator(old)
        prefix = old[:separator]
        if present:
            suffix = old[separator + 1:]
            padding = suffix[:len(suffix) - len(suffix.lstrip(" \t"))]
            replacement = prefix + "=" + padding + encoded + comment_spacing + comment + newline
        else:
            indent = prefix[:len(prefix) - len(prefix.lstrip())]
            replacement = indent + comment + newline if comment else ""
        lines[start:end] = [replacement]
    elif present:
        _, exists = get_value(tomllib.loads(text), parts)
        if exists:
            raise ValueError(f"{key}: this TOML layout must be edited in the standalone app.")
        headers = [entry for entry in entries if entry[0] == "header" and entry[1] == parts[:-1]]
        newline = "\r\n" if "\r\n" in text else "\n"
        line = f"{parts[-1]} = {encoded}{newline}"
        if headers:
            if not lines[headers[0][2]].endswith(("\n", "\r")):
                lines[headers[0][2]] += newline
            lines.insert(headers[0][3], line)
        else:
            if lines and not lines[-1].endswith(("\n", "\r")):
                lines[-1] += newline
            lines.extend([newline, "[" + ".".join(parts[:-1]) + "]" + newline, line])
    return "".join(lines)


def validate(path, text):
    name = None
    try:
        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=path.parent, delete=False) as file:
            name = file.name
            file.write(text)
        try:
            result = subprocess.run(
                ["umbriel", "config", "validate", "-c", name, "--json"],
                capture_output=True, text=True, timeout=30, check=False,
            )
        except subprocess.TimeoutExpired as error:
            raise ValueError("Umbriel validation timed out; config was not saved.") from error
        try:
            report = json.loads(result.stdout)
        except json.JSONDecodeError as error:
            raise ValueError("Umbriel returned an unreadable validation result; config was not saved.") from error
        if not isinstance(report, dict) or not isinstance(report.get("valid"), bool) or not isinstance(report.get("diagnostics"), list):
            raise ValueError("Umbriel returned an invalid validation result; config was not saved.")
        diagnostics = [
            str(item.get("message", "Unknown validation diagnostic"))
            for item in report["diagnostics"] if isinstance(item, dict)
        ]
        if result.returncode != 0 or not report["valid"]:
            raise ValueError("Umbriel validation failed: " + ("; ".join(diagnostics) or result.stderr.strip() or "unknown error"))
        return "; ".join(diagnostics)
    finally:
        if name is not None:
            os.unlink(name)


def save(path, backup_dir, expected_revision, changes):
    if path.is_symlink():
        raise ValueError("Config is a symlink; edit its target directly.")
    text, revision = read_document(path)
    if revision == "missing":
        raise ValueError(f"Config file does not exist: {path}")
    if revision != expected_revision:
        raise ValueError("Config changed externally. Reload before saving.")
    if not isinstance(changes, list):
        raise ValueError("Changes must be a list.")
    expected = copy.deepcopy(tomllib.loads(text))
    updated = text
    seen = set()
    for change in changes:
        if not isinstance(change, dict):
            raise ValueError("Invalid change.")
        key, present = change.get("key"), change.get("present")
        if not isinstance(key, str) or key not in FIELDS or key in seen or not isinstance(present, bool):
            raise ValueError("Invalid or duplicate setting.")
        seen.add(key)
        encoded, value = render_value(FIELDS[key], change.get("value", "")) if present else ("", None)
        if key == "general.autostart" and not present:
            raise ValueError("Autostart cannot be unset.")
        old_value, old_present = get_value(expected, key.split("."))
        if present == old_present and (not present or old_value == value):
            continue
        parent = expected
        for part in key.split(".")[:-1]:
            if part not in parent:
                if not present:
                    break
                parent[part] = {}
            if not isinstance(parent[part], dict):
                raise ValueError(f"{key}: parent is not a table.")
            parent = parent[part]
        else:
            if present:
                parent[key.split(".")[-1]] = value
            else:
                parent.pop(key.split(".")[-1], None)
        updated = edit(updated, key, present, encoded)
    try:
        actual = tomllib.loads(updated)
    except tomllib.TOMLDecodeError as error:
        raise ValueError(f"This TOML layout cannot be edited safely: {error}") from error
    if actual != expected:
        raise ValueError("The TOML layout cannot be edited without changing other settings.")
    if updated == text:
        return snapshot(path, text, revision)
    warning = validate(path, updated)
    if path.is_symlink() or read_document(path)[1] != revision:
        raise ValueError("Config changed during saving. Reload before retrying.")
    identity = hashlib.sha256(os.fsencode(str(path))).hexdigest()[:20]
    atomic_write(backup_dir / f"umbriel-config-{identity}.bak", text.encode("utf-8"))
    if path.is_symlink() or read_document(path)[1] != revision:
        raise ValueError("Config changed during saving. Reload before retrying.")
    atomic_write(path, updated.encode("utf-8"), stat.S_IMODE(path.stat().st_mode))
    result = snapshot(path, updated, hashlib.sha256(updated.encode("utf-8")).hexdigest())
    result["warning"] = warning
    return result


def main(args):
    if args == ["read"]:
        path = default_path()
        result = snapshot(path, *read_document(path))
    elif len(args) == 2 and args[0] == "read":
        path = Path(os.path.abspath(os.path.expanduser(args[1])))
        result = snapshot(path, *read_document(path))
    elif len(args) == 5 and args[0] == "save":
        path = Path(os.path.abspath(os.path.expanduser(args[1])))
        result = save(path, Path(args[3]), args[2], json.loads(args[4]))
    else:
        raise ValueError("Usage: general.py read [PATH] | save PATH REVISION BACKUP_DIR CHANGES_JSON")
    print(json.dumps(result, ensure_ascii=False))


if __name__ == "__main__":
    try:
        main(sys.argv[1:])
    except (OSError, UnicodeError, ValueError) as error:
        print(str(error), file=sys.stderr)
        sys.exit(1)

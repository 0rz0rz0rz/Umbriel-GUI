"""Edit Umbriel keybinds without changing unrelated TOML or GUI locks."""

import copy
import hashlib
import json
import os
from pathlib import Path
import stat
import sys

if sys.version_info < (3, 11):
    sys.exit("Keybind settings require Python 3.11 or newer.")

from general import assignment_separator, default_path, statements, tomllib, validate
from user_dirs import atomic_write, read_document


GROUP_MARKER = "# Umbriel Config GUI keybind groups: "


def locked_keys(path):
    identity = hashlib.sha256(os.fsencode(str(path))).hexdigest()[:20]
    data_home = Path(os.environ.get("XDG_DATA_HOME") or Path.home() / ".local/share")
    current = data_home / "umbriel-config-gui" / "configs" / identity / "gui-locked-keybinds.json"
    legacy = path.parent / "gui-locked-keybinds.json"
    current_text, current_revision = read_document(current)
    legacy_text, legacy_revision = read_document(legacy)
    text = current_text if current_revision != "missing" else legacy_text
    revision = current_revision + ":" + legacy_revision
    if not text and current_revision == "missing" and legacy_revision == "missing":
        return set(), revision
    try:
        keys = json.loads(text)
    except json.JSONDecodeError as error:
        raise ValueError(f"Could not read keybind locks: {error}") from error
    if not isinstance(keys, list) or not all(isinstance(key, str) for key in keys):
        raise ValueError("Invalid keybind lock file; use the standalone app to repair it.")
    return set(keys), revision


def group_metadata(text):
    groups, assignments = [], {}
    for line in text.splitlines():
        if not line.startswith(GROUP_MARKER):
            continue
        try:
            data = json.loads(line[len(GROUP_MARKER):])
        except json.JSONDecodeError as error:
            raise ValueError(f"Invalid keybind group metadata: {error}") from error
        if not isinstance(data, dict) or not isinstance(data.get("groups", []), list) or not isinstance(data.get("assignments", {}), dict):
            raise ValueError("Invalid keybind group metadata.")
        groups = [name.strip() for name in data.get("groups", []) if isinstance(name, str) and name.strip()]
        assignments = {
            key: value.strip() for key, value in data.get("assignments", {}).items()
            if isinstance(key, str) and isinstance(value, str) and value.strip()
        }
    return groups, assignments


def value_and_comment(assignment):
    separator, _ = assignment_separator(assignment)
    comment = ""
    spacing = ""
    for index, character in enumerate(assignment):
        if character == "#":
            try:
                tomllib.loads(assignment[:index] + "\n")
            except tomllib.TOMLDecodeError:
                continue
            comment = assignment[index:].rstrip("\r\n")
            spacing = assignment[:index][len(assignment[:index].rstrip(" \t")):]
            assignment = assignment[:index].rstrip(" \t")
            break
    return assignment[separator + 1:].strip(), comment, spacing


def snapshot(path, text, revision):
    if revision == "missing":
        raise ValueError(f"Config file does not exist: {path}")
    document = tomllib.loads(text)
    binds = document.get("keybinds", {})
    if not isinstance(binds, dict):
        raise ValueError("Keybinds must be a TOML table.")
    locked, lock_revision = locked_keys(path)
    groups, assignments = group_metadata(text)
    lines, entries = statements(text)
    raw = {}
    for kind, parts, start, end in entries:
        if kind == "assignment" and parts is not None and len(parts) == 2 and parts[0] == "keybinds":
            raw[parts[1]], _, _ = value_and_comment("".join(lines[start:end]))
    bindings = []
    for key, value in binds.items():
        if not isinstance(value, (str, dict)):
            raise ValueError(f"{key}: unsupported keybind value.")
        group = assignments.get(key, "")
        if group and group not in groups:
            groups.append(group)
        bindings.append({
            "key": key, "value": value if isinstance(value, str) else raw.get(key, ""), "group": group,
            "mode": "action" if isinstance(value, str) else "toml",
            "locked": key in locked, "editable": key in raw,
        })
    return {
        "path": str(path), "revision": revision, "lock_revision": lock_revision,
        "bindings": bindings, "groups": groups,
    }


def parse_value(raw, key, mode):
    if not isinstance(raw, str) or not raw.strip():
        raise ValueError(f"{key}: enter an action or a TOML table.")
    if mode == "action":
        return json.dumps(raw, ensure_ascii=False), raw
    if mode != "toml":
        raise ValueError(f"{key}: invalid edit mode.")
    try:
        result = tomllib.loads("value = " + raw + "\n")
    except tomllib.TOMLDecodeError as error:
        raise ValueError(f"{key}: invalid TOML value: {error}") from error
    value = result.get("value")
    if set(result) != {"value"} or not (
        isinstance(value, str) or isinstance(value, dict) and isinstance(value.get("action"), str)
    ):
        raise ValueError(f"{key}: use a quoted action or a table with an action string.")
    return raw, value


def edit_binding(text, key, raw, remove):
    lines, entries = statements(text)
    matches = [entry for entry in entries if entry[0] == "assignment" and entry[1] == ["keybinds", key]]
    if len(matches) > 1:
        raise ValueError(f"{key}: multiple assignments cannot be edited safely.")
    if matches:
        _, _, start, end = matches[0]
        old = "".join(lines[start:end])
        _, comment, comment_spacing = value_and_comment(old)
        separator, _ = assignment_separator(old)
        newline = "\r\n" if old.endswith("\r\n") else "\n" if old.endswith("\n") else ""
        if remove:
            indent = old[:len(old) - len(old.lstrip())]
            replacement = indent + comment + newline if comment else ""
        else:
            suffix = old[separator + 1:]
            padding = suffix[:len(suffix) - len(suffix.lstrip(" \t"))]
            replacement = old[:separator + 1] + padding + raw.strip()
            replacement += (comment_spacing + comment if comment else "") + newline
        lines[start:end] = [replacement]
    elif not remove:
        _, present = document_key(text, key)
        if present:
            raise ValueError(f"{key}: this TOML layout must be edited in the standalone app.")
        headers = [entry for entry in entries if entry[0] == "header" and entry[1] == ["keybinds"]]
        newline = "\r\n" if "\r\n" in text else "\n"
        line = json.dumps(key, ensure_ascii=False) + " = " + raw.strip() + newline
        if headers:
            start = headers[0][2]
            if not lines[start].endswith(("\n", "\r")):
                lines[start] += newline
            lines.insert(headers[0][3], line)
        else:
            if lines and not lines[-1].endswith(("\n", "\r")):
                lines[-1] += newline
            lines.extend([newline, "[keybinds]" + newline, line])
    else:
        raise ValueError(f"{key}: this TOML layout must be edited in the standalone app.")
    return "".join(lines)


def document_key(text, key):
    binds = tomllib.loads(text).get("keybinds", {})
    return (binds.get(key), key in binds) if isinstance(binds, dict) else (None, False)


def remove_group_assignments(text, removed):
    lines = text.splitlines(keepends=True)
    for index, line in enumerate(lines):
        if not line.startswith(GROUP_MARKER):
            continue
        newline = "\r\n" if line.endswith("\r\n") else "\n" if line.endswith("\n") else ""
        data = json.loads(line[len(GROUP_MARKER):])
        assignments = data.get("assignments", {})
        if any(key in assignments for key in removed):
            for key in removed:
                assignments.pop(key, None)
            lines[index] = GROUP_MARKER + json.dumps(data, ensure_ascii=False, separators=(",", ":")) + newline
    return "".join(lines)


def save(path, backup_dir, expected_revision, expected_locks, changes):
    if path.is_symlink():
        raise ValueError("Config is a symlink; edit its target directly.")
    text, revision = read_document(path)
    if revision == "missing":
        raise ValueError(f"Config file does not exist: {path}")
    if revision != expected_revision:
        raise ValueError("Config changed externally. Reload before saving.")
    locked, lock_revision = locked_keys(path)
    if lock_revision != expected_locks:
        raise ValueError("Keybind locks changed externally. Reload before saving.")
    if not isinstance(changes, list):
        raise ValueError("Changes must be a list.")
    expected = copy.deepcopy(tomllib.loads(text))
    binds = expected.get("keybinds", {})
    if not isinstance(binds, dict):
        raise ValueError("Keybinds must be a TOML table.")
    group_metadata(text)
    updated = text
    removed = set()
    seen = set()
    for change in changes:
        if not isinstance(change, dict):
            raise ValueError("Invalid keybind change.")
        key, remove, raw = change.get("key"), change.get("remove"), change.get("value")
        if not isinstance(key, str) or not key.strip() or key != key.strip() or key in seen or not isinstance(remove, bool):
            raise ValueError("Invalid or duplicate keybind.")
        if key in locked:
            raise ValueError(f"{key} is locked in Umbriel Settings.")
        seen.add(key)
        if remove:
            if key not in binds:
                raise ValueError(f"{key}: keybind does not exist.")
            del binds[key]
            removed.add(key)
        else:
            raw, value = parse_value(raw, key, change.get("mode"))
            if key in binds and binds[key] == value:
                continue
            binds[key] = value
            expected["keybinds"] = binds
        updated = edit_binding(updated, key, raw, remove)
    normalized = {}
    for key in binds:
        canonical = " ".join(key.casefold().split())
        if canonical in normalized:
            raise ValueError(f'Keybind conflict: "{key}" duplicates "{normalized[canonical]}".')
        normalized[canonical] = key
    if removed:
        updated = remove_group_assignments(updated, removed)
    try:
        actual = tomllib.loads(updated)
    except tomllib.TOMLDecodeError as error:
        raise ValueError(f"This TOML layout cannot be edited safely: {error}") from error
    if actual != expected:
        raise ValueError("The TOML layout cannot be edited without changing other settings.")
    if updated == text:
        return snapshot(path, text, revision)
    warning = validate(path, updated)
    if path.is_symlink() or read_document(path)[1] != revision or locked_keys(path)[1] != lock_revision:
        raise ValueError("Config or keybind locks changed during saving. Reload before retrying.")
    identity = hashlib.sha256(os.fsencode(str(path))).hexdigest()[:20]
    atomic_write(backup_dir / f"umbriel-config-{identity}.bak", text.encode("utf-8"))
    if path.is_symlink() or read_document(path)[1] != revision or locked_keys(path)[1] != lock_revision:
        raise ValueError("Config or keybind locks changed during saving. Reload before retrying.")
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
    elif len(args) == 6 and args[0] == "save":
        path = Path(os.path.abspath(os.path.expanduser(args[1])))
        result = save(path, Path(args[4]), args[2], args[3], json.loads(args[5]))
    else:
        raise ValueError("Usage: keybinds.py read [PATH] | save PATH REVISION LOCKS BACKUP_DIR CHANGES_JSON")
    print(json.dumps(result, ensure_ascii=False))


if __name__ == "__main__":
    try:
        main(sys.argv[1:])
    except (OSError, UnicodeError, ValueError) as error:
        print(str(error), file=sys.stderr)
        sys.exit(1)

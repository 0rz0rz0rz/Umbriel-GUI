"""Read and update XDG default applications for the Noctalia plugin."""

import configparser
import hashlib
import json
import mimetypes
import os
from pathlib import Path
import re
import shutil
import stat
import sys

from user_dirs import atomic_write, read_document


ROLES = {
    "Web browser": ["text/html", "application/xhtml+xml", "x-scheme-handler/http", "x-scheme-handler/https"],
    "Email client": ["x-scheme-handler/mailto"],
    "File manager": ["inode/directory"],
    "Text editor": ["text/plain"],
    "Image viewer": ["image/jpeg", "image/png", "image/gif", "image/webp", "image/svg+xml", "image/bmp", "image/tiff"],
    "PDF viewer": ["application/pdf"],
    "Audio player": ["audio/mpeg", "audio/ogg", "audio/flac", "audio/wav"],
    "Video player": ["video/mp4", "video/webm", "video/x-matroska", "video/ogg"],
}
ROLE_MIMES = {mime for mimes in ROLES.values() for mime in mimes}
HEADER = re.compile(r"^\s*\[([^\]]+)\]\s*(?:[#;].*)?$")
ENTRY = re.compile(r"^\s*([^#;=\s][^=]*?)\s*=\s*(.*?)\s*$")
MIME = re.compile(r"^[A-Za-z0-9][A-Za-z0-9!#$&^_.+-]*/[A-Za-z0-9][A-Za-z0-9!#$&^_.+-]*$")
EXTENSION = re.compile(r"^\.[A-Za-z0-9][A-Za-z0-9._+-]*$")


def config_path():
    return Path(os.environ.get("XDG_CONFIG_HOME") or Path.home() / ".config") / "mimeapps.list"


def defaults(text):
    result = {}
    section = None
    for line in text.splitlines():
        header = HEADER.fullmatch(line)
        if header:
            section = header.group(1)
        elif section == "Default Applications":
            entry = ENTRY.fullmatch(line)
            if entry:
                result[entry.group(1).strip()] = [
                    item.strip() for item in entry.group(2).split(";") if item.strip()
                ]
    return result


def installed_apps():
    data_home = Path(os.environ.get("XDG_DATA_HOME") or Path.home() / ".local/share")
    roots = [data_home / "applications"]
    roots.extend(Path(root) / "applications" for root in
                 (os.environ.get("XDG_DATA_DIRS") or "/usr/local/share:/usr/share").split(":") if root)
    apps, seen = [], set()
    for root in roots:
        for directory, subdirs, filenames in os.walk(root):
            subdirs.sort()
            for filename in sorted(filenames):
                if not filename.endswith(".desktop"):
                    continue
                path = Path(directory) / filename
                app_id = str(path.relative_to(root)).replace(os.sep, "-")
                if app_id in seen:
                    continue
                seen.add(app_id)
                parser = configparser.ConfigParser(interpolation=None, strict=False)
                try:
                    with path.open(encoding="utf-8") as file:
                        parser.read_file(file)
                except (configparser.Error, UnicodeError) as error:
                    raise ValueError(f"Cannot read desktop entry {path}: {error}") from error
                if not parser.has_section("Desktop Entry"):
                    continue
                entry = parser["Desktop Entry"]
                if (entry.get("Type", "Application") != "Application"
                        or entry.get("Hidden", "").lower() == "true"
                        or entry.get("NoDisplay", "").lower() == "true"):
                    continue
                executable = entry.get("TryExec", "")
                if executable and not shutil.which(executable):
                    continue
                apps.append({"id": app_id, "name": entry.get("Name", app_id[:-8])})
    return sorted(apps, key=lambda app: (app["name"].casefold(), app["id"].casefold()))


def snapshot(text, revision, apps):
    current = defaults(text)
    roles = {}
    for role, mimes in ROLES.items():
        values = [current.get(mime, [""])[0] if current.get(mime) else "" for mime in mimes]
        roles[role] = values[0] if all(value == values[0] for value in values) else "<multiple>"
    others = {mime: values[0] if values else "" for mime, values in current.items() if mime not in ROLE_MIMES}
    return {"revision": revision, "roles": roles, "mimes": others, "apps": apps,
            "role_mimes": sorted(ROLE_MIMES)}


def validate_changes(changes):
    if not isinstance(changes, list) or not changes:
        raise ValueError("Invalid default application changes.")
    updates = {}
    seen = set()
    role_mimes = {mime.casefold() for mime in ROLE_MIMES}
    for change in changes:
        if not isinstance(change, dict) or set(change) != {"kind", "key", "value"}:
            raise ValueError("Invalid default application change.")
        kind, key, app = change["kind"], change["key"], change["value"]
        if not isinstance(key, str):
            raise ValueError("Invalid application role or MIME type.")
        if not isinstance(app, str) or any(char in app for char in ";\r\n\0"):
            raise ValueError(f"{key}: invalid application ID.")
        if kind == "role" and key in ROLES:
            mimes = ROLES[key]
        elif kind == "mime" and MIME.fullmatch(key) and key.casefold() not in role_mimes:
            mimes = [key]
        else:
            raise ValueError(f"Invalid application role or MIME type: {key}")
        for mime in mimes:
            if mime.casefold() in seen:
                raise ValueError(f"Duplicate MIME type: {mime}")
            seen.add(mime.casefold())
            updates[mime] = app
    return updates


def update_text(text, updates):
    present = set(defaults(text))
    additions = [f"{mime}={app};\n" for mime, app in updates.items() if app and mime not in present]
    output, seen = [], set()
    section = None
    found = False
    inserted = False

    def append_additions():
        if additions and output and not output[-1].endswith(("\n", "\r")):
            output[-1] += "\n"
        output.extend(additions)

    for line in text.splitlines(keepends=True):
        content = line.rstrip("\r\n")
        header = HEADER.fullmatch(content)
        if header:
            if section == "Default Applications" and not inserted:
                append_additions()
                inserted = True
            section = header.group(1)
            found = found or section == "Default Applications"
            output.append(line)
            continue
        entry = ENTRY.fullmatch(content) if section == "Default Applications" else None
        mime = entry.group(1).strip() if entry else None
        if mime not in updates:
            output.append(line)
        elif mime not in seen:
            seen.add(mime)
            app = updates[mime]
            if app:
                fallback = [item.strip() for item in entry.group(2).split(";")
                            if item.strip() and item.strip() != app]
                output.append(f"{mime}={';'.join([app, *fallback])};\n")
    if found and section == "Default Applications" and not inserted:
        append_additions()
    elif not found and additions:
        if output and not output[-1].endswith(("\n", "\r")):
            output[-1] += "\n"
        output.append("[Default Applications]\n")
        output.extend(additions)
    return "".join(output)


def save(path, backup_dir, expected_revision, changes):
    updates = validate_changes(changes)
    apps = installed_apps()
    if path.is_symlink():
        raise ValueError("Default applications file is a symlink; edit its target directly.")
    text, revision = read_document(path)
    if revision != expected_revision:
        raise ValueError("Default applications changed externally. Reload before saving.")
    updated = update_text(text, updates).encode("utf-8")
    if revision != "missing":
        atomic_write(backup_dir / "mimeapps.list.bak", text.encode("utf-8"))
        mode = stat.S_IMODE(path.stat().st_mode)
    else:
        mode = 0o600
    atomic_write(path, updated, mode)
    return snapshot(updated.decode("utf-8"), hashlib.sha256(updated).hexdigest(), apps)


def main(args):
    path = config_path()
    if args == ["read"]:
        text, revision = read_document(path)
        result = snapshot(text, revision, installed_apps())
    elif len(args) == 4 and args[0] == "save":
        result = save(path, Path(args[2]), args[1], json.loads(args[3]))
    elif len(args) == 2 and args[0] == "extension":
        extension = args[1].strip().lower()
        if not extension.startswith("."):
            extension = "." + extension
        if not EXTENSION.fullmatch(extension):
            raise ValueError("Enter a file extension such as .pdf.")
        mime, _ = mimetypes.guess_type("file" + extension, strict=False)
        if not mime:
            raise ValueError(f"No MIME type is known for {extension}.")
        result = {"mime": mime}
    else:
        raise ValueError("Usage: default_apps.py read | save REVISION BACKUP_DIR CHANGES_JSON | extension EXT")
    print(json.dumps(result, ensure_ascii=False))


if __name__ == "__main__":
    try:
        main(sys.argv[1:])
    except (OSError, UnicodeError, ValueError) as error:
        print(str(error), file=sys.stderr)
        sys.exit(1)

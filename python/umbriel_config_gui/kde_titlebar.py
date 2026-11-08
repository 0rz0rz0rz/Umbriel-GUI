"""Read and follow the title-bar colors selected in qt6ct's KDE scheme."""

import configparser
import os

from PySide6.QtCore import QFileSystemWatcher, QObject, QSettings, QTimer
from PySide6.QtGui import QColor

from .qt6ct_theme import qt6ct_config_path


TITLE_BAR_KEYS = {
    ("colors", "title_bar", "background"): "activeBackground",
    ("colors", "title_bar", "background_unfocused"): "inactiveBackground",
    ("colors", "title_bar", "text"): "activeForeground",
    ("colors", "title_bar", "text_unfocused"): "inactiveForeground",
}

BACKGROUND_KEYS = {
    ("colors", "title_bar", "background"): "Colors:Header",
    ("colors", "title_bar", "background_unfocused"): "Colors:Header][Inactive",
}


def read_title_bar_colors(path):
    parser = configparser.RawConfigParser(interpolation=None)
    parser.optionxform = str
    with open(path, encoding="utf-8") as handle:
        parser.read_file(handle)
    def read_color(section, key):
        if not parser.has_option(section, key):
            return None
        parts = parser.get(section, key).split(",")
        if len(parts) != 3:
            raise ValueError(f"Invalid [{section}] {key} color")
        try:
            components = [int(part.strip()) for part in parts]
        except ValueError as error:
            raise ValueError(f"Invalid [{section}] {key} color") from error
        if any(component < 0 or component > 255 for component in components):
            raise ValueError(f"Invalid [{section}] {key} color")
        return QColor(*components)

    colors, backgrounds, errors = {}, {}, {}
    for kind, entries, output in (
        ("title", ((path, "WM", key) for path, key in TITLE_BAR_KEYS.items()), colors),
        ("background", ((path, section, "BackgroundNormal")
                        for path, section in BACKGROUND_KEYS.items()), backgrounds),
    ):
        for field_path, section, key in entries:
            try:
                color = read_color(section, key)
            except ValueError as error:
                errors[(kind, field_path)] = str(error)
                continue
            if color is not None:
                output[field_path] = color
    if not colors and not backgrounds and not errors:
        raise ValueError("The color scheme has no title-bar or header background colors")
    return colors, backgrounds, errors


class KdeTitleBarFollower(QObject):
    def __init__(self, fields, parent):
        super().__init__(parent)
        self.fields = fields
        self.watcher = QFileSystemWatcher(self)
        self.timer = QTimer(self)
        self.timer.setSingleShot(True)
        self.timer.setInterval(300)
        self.timer.timeout.connect(self.refresh)
        self.watcher.fileChanged.connect(self.timer.start)
        self.watcher.directoryChanged.connect(self.timer.start)
        self.refresh()

    def refresh(self):
        config_path = qt6ct_config_path()
        paths = [config_path]
        colors = {}
        backgrounds = {}
        errors = {}
        try:
            if not os.path.isfile(config_path):
                raise ValueError("qt6ct configuration not found")
            settings = QSettings(config_path, QSettings.Format.IniFormat)
            if settings.status() != QSettings.Status.NoError:
                raise ValueError("Could not read qt6ct configuration")
            if not settings.value("Appearance/custom_palette", False, bool):
                raise ValueError("qt6ct custom palette is not enabled")
            scheme = settings.value("Appearance/color_scheme_path", "", str)
            if not scheme:
                raise ValueError("No qt6ct color scheme is selected")
            scheme = os.path.expanduser(scheme)
            if not os.path.isabs(scheme):
                scheme = os.path.join(os.path.dirname(config_path), scheme)
            paths.append(scheme)
            colors, backgrounds, errors = read_title_bar_colors(scheme)
            message = f"KDE color from {scheme}"
        except (OSError, UnicodeDecodeError, configparser.Error, ValueError) as error:
            message = f"KDE title-bar color unavailable: {error}"
        watched = [path for path in paths if os.path.isfile(path)]
        watched += sorted({os.path.dirname(path) for path in paths if os.path.isdir(os.path.dirname(path))})
        existing = self.watcher.files() + self.watcher.directories()
        stale = [path for path in existing if path not in watched]
        if stale:
            self.watcher.removePaths(stale)
        missing = [path for path in watched if path not in existing]
        if missing:
            failed = self.watcher.addPaths(missing)
            if failed:
                message += f"; could not watch {', '.join(failed)} for changes"
        for field in self.fields:
            color = colors.get(field.f.path)
            field_message = message
            if ("title", field.f.path) in errors:
                field_message = errors[("title", field.f.path)]
            elif color is None and (colors or backgrounds or errors):
                field_message = f"{message}; [WM] {TITLE_BAR_KEYS[field.f.path]} is missing"
            field.set_kde_color(color, field_message)
            if field.f.path in BACKGROUND_KEYS:
                background = backgrounds.get(field.f.path)
                background_message = message
                if ("background", field.f.path) in errors:
                    background_message = errors[("background", field.f.path)]
                elif background is None and (colors or backgrounds or errors):
                    section = BACKGROUND_KEYS[field.f.path]
                    background_message = f"{message}; [{section}] BackgroundNormal is missing"
                field.set_kde_background(background, background_message)

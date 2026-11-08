"""Configuration field metadata, schema integration, and reusable form widgets."""

import configparser
import warnings

from .common import (
    MISSING,
    GUI_DATA_DIR,
    QEvent,
    QColorDialog,
    QDoubleSpinBox,
    QFont,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPainter,
    QPalette,
    QPlainTextEdit,
    QSizePolicy,
    QPushButton,
    QScrollArea,
    QSpinBox,
    QToolButton,
    QVBoxLayout,
    QWidget,
    Qt,
    WheelSafeComboBox,
    delp,
    getp,
    hexof,
    json,
    normalize_optional_includes,
    os,
    migrate_gui_file,
    putp,
    py,
    qcolor,
    textwrap,
    tomlkit,
    totext,
    write_text_file,
)
from .schema import field_schema_option
from .kde_titlebar import KdeTitleBarFollower, TITLE_BAR_KEYS
from .widgets import (
    FlowLayout,
    KdeColorControl,
    OverviewButton,
    SettingLabel,
    SettingRow,
    SettingSlider,
    SwitchCheckBox,
    TriStateControl,
    WrappedLabel,
)


def installed_cursor_themes():
    """Find cursor themes and inheritance-only aliases in cursor search paths."""
    cursor_path = os.environ.get("XCURSOR_PATH")
    if cursor_path is not None:
        roots = cursor_path.split(os.pathsep)
    else:
        data_home = os.environ.get("XDG_DATA_HOME") or os.path.expanduser("~/.local/share")
        data_dirs = os.environ.get("XDG_DATA_DIRS") or "/usr/local/share:/usr/share"
        roots = [
            os.path.expanduser("~/.icons"),
            os.path.join(data_home, "icons"),
            *(os.path.join(directory, "icons") for directory in data_dirs.split(os.pathsep) if directory),
            "/usr/share/pixmaps",
        ]
    themes = set()
    aliases = {}
    for root in roots:
        if not root:
            continue
        root = os.path.expanduser(root)
        try:
            entries = list(os.scandir(root))
        except FileNotFoundError:
            continue
        except OSError as error:
            warnings.warn(f"Could not scan cursor theme directory {root}: {error}", RuntimeWarning)
            continue
        for entry in entries:
            if not entry.is_dir():
                continue
            if os.path.isdir(os.path.join(entry.path, "cursors")):
                themes.add(entry.name)
                continue
            index_path = os.path.join(entry.path, "index.theme")
            try:
                with os.scandir(entry.path) as children:
                    if any(child.is_dir() for child in children):
                        continue
                with open(index_path, encoding="utf-8") as index_file:
                    index = configparser.ConfigParser(interpolation=None, strict=False)
                    index.read_file(index_file)
            except FileNotFoundError:
                continue
            except (OSError, UnicodeError, configparser.Error) as error:
                warnings.warn(f"Could not read cursor theme index {index_path}: {error}", RuntimeWarning)
                continue
            inherited = index.get("Icon Theme", "Inherits", fallback="")
            aliases.setdefault(entry.name, set()).update(
                name.strip() for name in inherited.split(",") if name.strip()
            )
    while True:
        inherited_themes = {name for name, parents in aliases.items() if parents & themes}
        new_themes = inherited_themes - themes
        if not new_themes:
            break
        themes.update(new_themes)
    return sorted(themes, key=lambda name: (name.casefold(), name))


FIELD_HELP = {
    "Enabled": "Turn this feature on or off.",
    "Duration (ms)": "Set how long this animation takes, in milliseconds.",
    "Curve": "Choose the timing curve that controls the animation's acceleration and deceleration.",
    "Custom effect preset": "Use a named effect preset from the Effects page; leave unset to use the built-in effect.",
    "Action (pick or type)": "Choose an action for this hot corner, or enter a custom action.",
    "Kind": "Choose which effect type this preset or pool applies to.",
    "Shader file (relative to this config)": "Select the shader file for this effect. Relative paths start from the config file's directory.",
    "Preset names (TOML array)": "List the named presets this pool can choose from.",
    "Selection policy": "Choose whether the pool cycles, randomizes, or prefers unused presets.",
    "Autostart commands (restart)": "Commands launched when Umbriel starts; changes take effect after restart.",
    "Mod key": "Choose the modifier key used by Umbriel's built-in shortcuts.",
    "Show keybind cheatsheet at start": "Show the shortcut reference when the session starts.",
    "Let activation requests focus windows": "Allow applications to request focus when activating a window.",
    "Attach modal dialogs to parent": "Keep modal dialogs attached to and positioned with their parent window.",
    "Honor maximize while opening": "Respect an application's request to open a window maximized.",
    "NVIDIA sync workaround": "Enable a synchronization workaround for some NVIDIA setups.",
    "Enable XWayland": "Allow legacy X11 applications to run through XWayland.",
    "Native resolution (sharp on scaled outputs)": "Use native-resolution rendering for sharper XWayland output on scaled displays.",
    "Announce scale/cursor via XSETTINGS": "Publish display scale and cursor settings to X11 applications.",
    "Primary output for X11 apps": "Choose the output XWayland uses as its primary display.",
    "Ignored device paths": "List DRM device paths Umbriel should not use.",
    "Ignored PCI addresses": "List PCI addresses of DRM devices Umbriel should not use.",
    "Required include files": "Load these additional configuration files; a missing file is an error.",
    "Optional include files": "Load these additional configuration files when present; missing files are ignored.",
    "Prefer server-side decorations": "Prefer window decorations drawn by the compositor over client-side decorations.",
    "Opacity while dragging": "Set window opacity while the window is being dragged.",
    "Opaque fullscreen": "Render fullscreen windows without transparency.",
    "Passes": "Set the number of blur passes; more passes can look smoother but cost more GPU time.",
    "Radius": "Set the blur radius in pixels.",
    "Noise": "Set the amount of noise added to the blur.",
    "Brightness": "Adjust the brightness of the blurred image.",
    "Contrast": "Adjust the contrast of the blurred image.",
    "Saturation": "Adjust the color saturation of the blurred image.",
    "Softness": "Set how soft and spread out the window shadow appears.",
    "Offset X": "Move the shadow horizontally.",
    "Offset Y": "Move the shadow vertically.",
    "Buttons (comma separated)": "Choose which title-bar buttons to show and their order.",
    "Title format": "Set the title-bar text template; {title} inserts the window title.",
    "Max tabs (0 = all)": "Limit the number of visible tabs; zero shows all tabs.",
    "Middle-click paste": "Paste the primary selection when the middle mouse button is pressed.",
    "Repeat rate (Hz)": "Set how many times per second a held key repeats.",
    "Repeat delay (ms)": "Set how long a key must be held before repeating starts.",
    "Track layout": "Choose whether keyboard layout follows the whole session or the focused window.",
    "Natural scroll": "Reverse the scroll direction to match touch-style scrolling.",
    "Left handed": "Swap left- and right-button behavior.",
    "Sensitivity": "Adjust pointer sensitivity; zero uses the device's neutral setting.",
    "Disable while typing": "Temporarily ignore touchpad input while typing.",
    "Disable with external mouse": "Disable the touchpad while an external mouse is connected.",
    "Scroll method": "Choose how scrolling gestures or edges are detected.",
    "Click method": "Choose how touchpad clicks map to mouse buttons.",
    "Tap button map": "Choose which mouse button each tap gesture produces.",
    "Map to output": "Restrict this device to the named output.",
    "Map to focused output": "Map this device to whichever output currently has focus.",
    "Map to focused window": "Map this device to the currently focused window.",
    "Calibration matrix (6 numbers)": "Enter six calibration values to correct the tablet's coordinate mapping.",
    "Hardware cursor": "Use a hardware cursor plane when the display and driver support it.",
    "Hide when typing": "Hide the cursor while keyboard input is active.",
    "Hide after inactivity (ms, 0 = never)": "Set how long the cursor stays visible after movement; zero disables hiding.",
    "Focus follows mouse": "Move keyboard focus to a window when the pointer enters it.",
    "Hover raises window": "Raise a window above others when the pointer moves over it.",
    "Gap": "Set the space between tiled windows, in pixels.",
    "Extent presets (TOML array)": "List reusable column-width fractions for the scrolling layout.",
    "New window exits fullscreen (TOML)": "Choose whether opening a window exits fullscreen, using a TOML value.",
    "Client maximize button": "Choose whether an application's maximize request fills a column or the available edges.",
    "Default column width fraction": "Set the default scrolling-column width relative to the output.",
    "Center underfull strip": "Center a row of columns when it does not fill the output.",
    "Center focused": "Choose when the scrolling layout centers the focused column.",
    "Preserve split": "Keep existing split directions when windows are added to the dwindle layout.",
    "New window toward cursor": "Place new dwindle splits toward the pointer when possible.",
    "Master width fraction": "Set the master area width as a fraction of the output.",
    "New stack windows on top": "Place newly added stack windows above existing stack windows.",
    "New window becomes master": "Make each new window the master window.",
    "Back and forth": "Return to the previously active workspace when switching to the current one again.",
    "Empty workspace above": "Create or prefer an empty workspace above the current workspace.",
    "Zoom": "Set the overview zoom level.",
    "Shortcut keys": "Set the keys displayed as workspace shortcuts in the overview.",
    "Stiffness": "Higher values make the spring respond and settle faster.",
    "Damping": "Higher values reduce spring overshoot and wobble.",
    "Coupling": "Set how strongly window movement is coupled to the pointer.",
    "Pointer response": "Set how quickly the dragged window follows pointer movement.",
    "Max displacement (px)": "Limit how far the window can lag behind the pointer.",
    "Settle after pause (s)": "Set how long pointer motion must pause before the window settles.",
    "Block screen capture": "Prevent matching windows from appearing in screen captures.",
    "Border effect on unfocused windows": "Draw the selected border effect on unfocused windows as well as the focused window.",
    "Effect while screen sharing": "Choose the screen effect to use while an output or window is being shared.",
    "Confine pointer": "Keep the pointer within the bounds of the matching window.",
    "Focus on activate": "Focus the window when an activation request is received.",
    "Open in scratchpad": "Place matching windows in the named scratchpad.",
    "Open on output": "Place matching windows on the named output.",
    "Open on workspace (2 or \"NAME\")": "Choose the workspace where matching windows open.",
    "Open fullscreen": "Start matching windows in fullscreen mode.",
    "Open floating": "Open matching windows as floating windows instead of tiling them.",
    "Open maximized": "Start matching windows maximized.",
    "Open maximized to edges": "Start matching windows maximized to the available output edges.",
    "Open pinned": "Keep matching windows visible across workspaces.",
    "Takes focus": "Give matching windows keyboard focus when they open.",
    "Radius": "Set the blur radius in pixels.",
    "Floating size px ({width=,height=})": "Set a floating window's width and height in pixels using a TOML table.",
    "Floating size fraction ({width=,height=})": "Set a floating window's width and height as output fractions.",
    "Floating position ({x=,y=,anchor=})": "Set the position and anchor for matching floating windows.",
    "Scrolling extent px": "Set the scrolling-column width in pixels.",
    "Scrolling extent fraction": "Set the scrolling-column width as an output fraction.",
    "Mode (e.g. 2560x1440@144)": "Choose a resolution and refresh rate advertised by this output. Use Inspect connected outputs to see the live supported modes.",
    "Position ([x, y])": "Set the output's top-left position in compositor coordinates.",
    "Transform": "Rotate or flip the output image.",
    "Direct scanout": "Allow fullscreen surfaces to be sent directly to the display when possible.",
    "HDR": "Choose whether and when to enable high-dynamic-range output.",
    "SDR white (cd/m2)": "Set the reference brightness for SDR content on an HDR output.",
    "Bit depth": "Choose the output color bit depth.",
    "Workspaces (\"dynamic\", 5 or [\"A\",\"B\"])": "Choose dynamic, numbered, or explicitly named workspaces for this output.",
    "Min workspaces": "Set the minimum number of workspaces kept on this output.",
    "Cyclic workspaces": "Wrap workspace navigation from the last workspace back to the first.",
    "Workspace axis": "Choose whether workspaces are arranged horizontally or vertically.",
    "Device name (exact, from libinput list-devices)": "Match this device using its exact libinput name.",
    "Spawn when empty (command)": "Run this command when the named scratchpad has no window to show.",
}


def setting_description(field, category, group):
    """Return contextual help with usage notes for a setting."""
    if field.path == ("input", "cursor", "theme"):
        description = "Choose an installed cursor theme or type a custom theme name."
    elif field.label == "Radius" and group == "Cursor-only settings":
        description = "Set the size of the cursor effect in pixels; zero covers the whole output."
    else:
        description = FIELD_HELP.get(field.label)
    if description is None:
        label = field.label.rstrip(" ?")
        if field.label.startswith("Match "):
            description = f"Require this condition for the {category.lower()} rule to match."
        elif field.kind == "bool":
            description = (
                f"Choose whether {label[5:].lower()} is required for this rule to match."
                if label.startswith("Match ")
                else f"Choose whether {label[:1].lower() + label[1:]} is enabled for {group.lower()}."
            )
        elif field.kind == "color":
            description = f"Set the {label.lower()} color used by {group.lower()}."
        elif field.kind in ("int", "float"):
            description = f"Set the {label.lower()} used by {group.lower()}."
        elif field.kind == "raw":
            description = f"Set {label.lower()} for {group.lower()} using a TOML value."
        elif field.kind in ("choice", "combo"):
            description = f"Choose the {label.lower()} used by {group.lower()}."
        elif field.kind == "command_list":
            description = f"List the commands used by {group.lower()}."
        elif field.kind == "list":
            description = f"List the values used by {group.lower()}."
        else:
            description = f"Set the {label.lower()} used by {group.lower()}."
    if field.kind in ("choice", "combo") and isinstance(field.extra, (list, tuple)):
        description += " Options: " + ", ".join(str(option) for option in field.extra) + "."
        if field.kind == "combo":
            description += " You can also type a custom value."
    if field.kind == "raw":
        description += " Enter valid TOML."
    if field.opt:
        description += " Leave this setting unset to omit its key and use Umbriel's built-in default."
    else:
        description += " This value is written directly to the config."
    parts = (
        description,
        f"Applies to: {category} > {group}",
        f"Config key: {'.'.join(field.path)}",
    )
    return "\n".join(textwrap.fill(part, width=42) for part in parts)


class FieldWidget(QWidget):
    """The editor widget for one Field: a spinbox, checkbox, dropdown, text box or color button, plus an optional 'set' checkbox."""
    def __init__(self, field, current, schema_path=None):
        """Create the right widget for the field kind and fill it with the current config value (or the default if the key is missing)."""
        super().__init__()
        self.f = field
        self.schema_option = field_schema_option(schema_path or ".".join(field.path))
        self.default = (
            self.schema_option["default"]
            if self.schema_option is not None and "default" in self.schema_option
            else field.default
        )
        lay = QHBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(8)
        lay.addStretch(1)
        k, ex = field.kind, field.extra
        if self.schema_option is not None:
            if "values" in self.schema_option and k in ("choice", "combo"):
                ex = self.schema_option["values"]
            if "min" in self.schema_option and "max" in self.schema_option and k in ("int", "float"):
                ex = (self.schema_option["min"], self.schema_option["max"])
        if field.path == ("input", "cursor", "theme"):
            ex = installed_cursor_themes()
        self.tri = k == "bool" and field.opt
        if self.tri:
            self.w = TriStateControl()
        elif k == "bool":
            self.w = SwitchCheckBox()
        elif k == "int":
            self.w = QSpinBox()
            self.w.setRange(*(ex or (-100000, 100000)))
        elif k == "float":
            self.w = QDoubleSpinBox()
            lo, hi = ex or (-100000.0, 100000.0)
            self.w.setDecimals(3)
            self.w.setRange(lo, hi)
            self.w.setSingleStep(10.0 if hi - lo > 100 else 0.05)
        elif k in ("choice", "combo"):
            self.w = WheelSafeComboBox()
            self.w.addItems(ex or [])
            self.w.setEditable(k == "combo")
        elif k == "raw":
            self.w = QPlainTextEdit()
            self.w.setMinimumHeight(72)
            self.w.setMaximumHeight(120)
            raw_font = QFont(self.w.font())
            raw_font.setFamily("monospace")
            self.w.setFont(raw_font)
            try:
                example = totext(self.default)
            except (TypeError, ValueError):
                example = ""
            self.w.setPlaceholderText(
                f"TOML value, for example: {example}" if example else "Enter a TOML value"
            )
        elif k == "command_list":
            self.w = QWidget()
            self.command_rows = QVBoxLayout(self.w)
            self.command_rows.setContentsMargins(0, 0, 0, 0)
            self.command_rows.setSpacing(6)
            self.add_command_button = QPushButton("Add command")
            self.add_command_button.clicked.connect(self.add_command)
            self.command_rows.addWidget(self.add_command_button)
        elif k == "color":
            self.w = QPushButton()
            self.w.clicked.connect(self.pick_color)
        else:  # str, strorlist, list, raw
            self.w = QLineEdit()
        self.opacity_slider = None
        self.opacity_spin = None
        self.opacity_widget = None
        self.opacity_check = None
        self.opacity_row = None
        self.kde_color = None
        self.kde_background = None
        self.kde_button = None
        self.kde_source = None
        self.kde_messages = ["", ""]
        if field.path in TITLE_BAR_KEYS and field.path not in (
            ("colors", "title_bar", "background"),
            ("colors", "title_bar", "background_unfocused"),
        ):
            self.kde_button = QPushButton("Use KDE color")
            self.kde_button.setEnabled(False)
            self.kde_button.clicked.connect(self.use_kde_color)
        if field.path in (
            ("colors", "title_bar", "background"),
            ("colors", "title_bar", "background_unfocused"),
        ):
            self.kde_source = KdeColorControl()
            self.kde_source.setAccessibleName(f"{field.label} color source")
            self.kde_source.activated.connect(self.select_kde_source)
            self.opacity_slider = SettingSlider()
            self.opacity_slider.setRange(0, 255)
            self.opacity_slider.setPageStep(26)
            self.opacity_slider.setAccessibleName(f"{field.label} opacity")
            self.opacity_spin = QDoubleSpinBox()
            self.opacity_spin.setRange(0.0, 1.0)
            self.opacity_spin.setDecimals(3)
            self.opacity_spin.setSingleStep(0.01)
            self.opacity_spin.setFixedWidth(80)
            self.opacity_spin.setAccessibleName(f"{field.label} opacity")
            self.opacity_slider.valueChanged.connect(self.set_opacity_from_slider)
            self.opacity_spin.valueChanged.connect(self.set_opacity)
        if not self.tri:
            self.w.setMinimumWidth(0)
        self.slider = None
        if k in ("int", "float"):
            self.w.setFixedWidth(105)
            if ex is not None:
                scale = 1 if k == "int" else 1000
                slider_min = round(self.w.minimum() * scale)
                slider_max = round(self.w.maximum() * scale)
                if (-2147483648 <= slider_min <= slider_max <= 2147483647
                        and slider_max - slider_min <= 2147483647):
                    self.slider = SettingSlider()
                    self.slider.setRange(slider_min, slider_max)
                    self.slider.setPageStep(max(1, (slider_max - slider_min) // 10))
                    self.slider.setAccessibleName(field.label)
                    self.slider.valueChanged.connect(
                        lambda value: self.w.setValue(value / scale if k == "float" else value)
                    )

                    def sync_slider(value):
                        self.slider.blockSignals(True)
                        self.slider.setValue(round(value * scale))
                        self.slider.blockSignals(False)

                    self.w.valueChanged.connect(sync_slider)
        elif k in ("choice", "combo"):
            self.w.setMinimumWidth(120)
            self.w.setMaximumWidth(360)
            self.w.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
            self.w.view().setMinimumWidth(240)
        elif k == "color":
            self.w.setFixedWidth(110)
        elif k not in ("bool", "command_list"):
            self.w.setMaximumWidth(460)
            self.w.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.check = None
        if field.opt and not self.tri:
            self.check = SwitchCheckBox()
            self.check.setToolTip("Tick to write this setting to your config. Unticked = Umbriel's built-in default.")
            if self.kde_button is not None or self.kde_source is not None:
                self.check.setToolTip(
                    "Tick to write this color. When unticked, the KDE color is a preview only; "
                    "Umbriel uses its default or an included config."
                )
                self.check.toggled.connect(self.update_kde_preview)
            if self.kde_source is not None:
                self.check.toggled.connect(self.sync_kde_source)
            self.check.toggled.connect(self.w.setEnabled)
            if self.slider is not None:
                self.check.toggled.connect(self.slider.setEnabled)
            if self.opacity_slider is not None:
                self.check.toggled.connect(self.opacity_slider.setEnabled)
                self.check.toggled.connect(self.opacity_spin.setEnabled)
            lay.addWidget(self.check)
        if self.slider is not None:
            lay.addWidget(self.slider)
        if self.opacity_slider is not None:
            lay.addWidget(self.kde_source)
            lay.addWidget(self.w)
            self.opacity_widget = QWidget()
            opacity_layout = QHBoxLayout(self.opacity_widget)
            opacity_layout.setContentsMargins(0, 0, 0, 0)
            if self.check is not None:
                self.opacity_check = SwitchCheckBox()
                self.opacity_check.setToolTip("Tick to write this color's opacity. Same switch as the color above.")
                self.check.toggled.connect(self.opacity_check.setChecked)
                self.opacity_check.toggled.connect(self.check.setChecked)
                opacity_layout.addWidget(self.opacity_check)
            self.opacity_slider.setMaximumWidth(16777215)
            self.opacity_slider.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
            opacity_layout.addWidget(self.opacity_slider, 1)
            opacity_layout.addWidget(self.opacity_spin)
            self.opacity_help = QToolButton()
            self.opacity_help.setText("?")
            self.opacity_help.setAutoRaise(True)
            self.opacity_help.setFixedSize(20, 20)
            self.opacity_help.setAccessibleName(f"Help for {field.label} opacity")
            opacity_layout.addWidget(self.opacity_help)
        else:
            if self.kde_button is not None:
                lay.addWidget(self.kde_button)
            lay.addWidget(self.w)
        self.help_button = QToolButton()
        self.help_button.setText("?")
        self.help_button.setAutoRaise(True)
        self.help_button.setFixedSize(20, 20)
        self.help_button.setAccessibleName(f"Help for {field.label}")
        self.help_button.setToolTip("Setting description")
        lay.addWidget(self.help_button)
        if self.tri:
            self.w.setAccessibleName(field.label)
            self.w.setCurrentIndex(0 if current is MISSING else (1 if py(current) else 2))
            return
        if current is MISSING:
            self.set_value(self.default)
            if self.check:
                self.check.setChecked(False)
                self.w.setEnabled(False)
                if self.slider is not None:
                    self.slider.setEnabled(False)
                if self.opacity_slider is not None:
                    self.opacity_slider.setEnabled(False)
                    self.opacity_spin.setEnabled(False)
        else:
            self.set_value(py(current) if k not in ("raw", "strorlist") else current)
            if self.check:
                self.check.setChecked(True)
        if self.slider is not None:
            self.slider.blockSignals(True)
            self.slider.setValue(round(self.w.value() * scale))
            self.slider.blockSignals(False)
        if k == "raw":
            self.w.textChanged.connect(self.update_raw_feedback)
            self.update_raw_feedback()

    def pick_color(self):
        """Open the color dialog (with alpha) and apply the chosen color."""
        c = QColorDialog.getColor(qcolor(self.w.text()), self, "Pick color",
                                  QColorDialog.ColorDialogOption.ShowAlphaChannel)
        if c.isValid():
            self.set_color(hexof(c))
            if self.kde_source is not None:
                self.kde_source.setCurrentIndex(-1)

    def set_color(self, h):
        """Show a color on the button: background in the chosen color, text black or white for readability."""
        self.w.setText(h)
        self.w.setStyleSheet(f"background:{h[:7]};color:{'#000' if qcolor(h).lightness() > 128 else '#fff'}")
        if self.opacity_slider is not None:
            alpha = qcolor(h).alpha()
            self.opacity_slider.blockSignals(True)
            self.opacity_slider.setValue(alpha)
            self.opacity_slider.blockSignals(False)
            self.opacity_spin.blockSignals(True)
            self.opacity_spin.setValue(alpha / 255)
            self.opacity_spin.blockSignals(False)

    def set_opacity(self, value):
        color = qcolor(self.w.text())
        color.setAlpha(round(value * 255))
        self.set_color(hexof(color))

    def set_opacity_from_slider(self, value):
        self.opacity_spin.setValue(value / 255)

    def set_kde_color(self, color, message):
        self.kde_color = color
        if self.kde_source is not None:
            self.kde_source.setSegmentAvailable(1, color is not None)
            self.kde_messages[0] = f"KDE TB: {message}"
            self.update_kde_source_tooltip()
        else:
            self.kde_button.setEnabled(color is not None)
            self.kde_button.setToolTip(
                message if color is not None else message + "; this field was not changed."
            )
        if color is not None and self.check and not self.check.isChecked():
            self.preview_kde_color()

    def preview_kde_color(self):
        color = qcolor(hexof(self.kde_color))
        color.setAlpha(qcolor(self.w.text()).alpha())
        self.set_color(hexof(color))

    def use_kde_color(self):
        if self.kde_color is not None:
            self.preview_kde_color()
            if self.check:
                self.check.setChecked(True)

    def set_kde_background(self, color, message):
        self.kde_background = color
        self.kde_source.setSegmentAvailable(2, color is not None)
        self.kde_messages[1] = f"KDE BG: {message}"
        self.update_kde_source_tooltip()

    def use_kde_background(self):
        if self.kde_background is not None:
            color = qcolor(hexof(self.kde_background))
            color.setAlpha(qcolor(self.w.text()).alpha())
            self.set_color(hexof(color))
            if self.check:
                self.check.setChecked(True)

    def update_kde_preview(self, checked):
        if not checked and self.kde_color is not None:
            self.preview_kde_color()

    def update_kde_source_tooltip(self):
        self.kde_source.setToolTip(
            "Default unsets the override. KDE TB and KDE BG import colors; "
            "no selected segment means a custom override.\n" + "\n".join(self.kde_messages)
        )

    def sync_kde_source(self, checked):
        if not checked:
            self.kde_source.setCurrentIndex(0)
        elif self.kde_source.currentIndex() == 0:
            self.kde_source.setCurrentIndex(-1)

    def select_kde_source(self, index):
        if index == 0:
            if self.check:
                self.check.setChecked(False)
        elif index == 1:
            self.use_kde_color()
        elif index == 2:
            self.use_kde_background()

    def set_value(self, v):
        """Put a value into the widget, converting it to whatever the widget type needs."""
        k = self.f.kind
        if self.tri:
            self.w.setCurrentIndex(0 if v is None else (1 if bool(v) else 2))
            return
        if v is None:
            v = {"bool": False, "int": 0, "float": 0.0, "color": "#000000FF"}.get(k, "")
        if k == "bool":
            self.w.setChecked(bool(v))
        elif k == "int":
            self.w.setValue(int(v))
        elif k == "float":
            self.w.setValue(float(v))
        elif k in ("choice", "combo"):
            if self.w.findText(str(v)) < 0:
                self.w.addItem(str(v))
            self.w.setCurrentText(str(v))
        elif k == "color":
            self.set_color(str(v))
        elif k == "list":
            self.w.setText(", ".join(str(x) for x in v))
        elif k == "command_list":
            while self.command_rows.count() > 1:
                item = self.command_rows.takeAt(0)
                if item.widget():
                    item.widget().setParent(None)
                    item.widget().deleteLater()
            for command in v:
                self.add_command_row(str(command))
        elif k == "raw":
            self.w.setPlainText(totext(v) if v != "" else "")
        elif k == "strorlist":
            self.w.setText(totext(v) if not isinstance(py(v), str) else str(py(v)))
        else:
            self.w.setText(str(v))

    def get(self):
        """Read the widget back as a TOML-ready value. Returns None when the field is optional and 'set' is unchecked, and raises ValueError on invalid raw TOML."""
        if self.tri:
            i = self.w.currentIndex()
            return None if i == 0 else i == 1
        if self.check and not self.check.isChecked():
            return None
        k = self.f.kind
        if k == "bool":
            return self.w.isChecked()
        if k in ("int", "float"):
            return self.w.value()
        if k in ("choice", "combo"):
            return self.w.currentText()
        if k == "color":
            return self.w.text()
        if k == "list":
            return [s.strip() for s in self.w.text().split(",") if s.strip()]
        if k == "command_list":
            return [
                command.text()
                for command in self.w.findChildren(QLineEdit)
                if command.text().strip()
            ]
        t = self.w.toPlainText().strip() if k == "raw" else self.w.text().strip()
        if k == "raw" or (k == "strorlist" and t.startswith("[")):
            try:
                # The trailing newline matters: without it the parsed value carries no line break and is
                # written glued to the next "[[...]]" header when it is the last key of a rule.
                return tomlkit.parse("v = " + t + "\n")["v"]
            except Exception as e:
                raise ValueError(f"{self.f.label}: invalid TOML value ({e})")
        return t if k == "strorlist" else self.w.text()

    def update_raw_feedback(self):
        """Mark malformed TOML values as the user edits them."""
        text = self.w.toPlainText().strip()
        if not text:
            self.w.setStyleSheet("")
            self.w.setToolTip("Enter a TOML value, for example: [0.333, 0.5, 0.667]")
            return
        try:
            tomlkit.parse("value = " + text + "\n")
        except tomlkit.exceptions.TOMLKitError as error:
            self.w.setStyleSheet("border: 1px solid #d55;")
            self.w.setToolTip(f"Invalid TOML value: {error}")
        else:
            self.w.setStyleSheet("")
            self.w.setToolTip("Valid TOML value.")

    def add_command_row(self, command=""):
        """Add a case-preserving command entry to the autostart list."""
        row = QWidget()
        layout = QHBoxLayout(row)
        layout.setContentsMargins(0, 0, 0, 0)
        entry = QLineEdit(command)
        entry.setMinimumWidth(420)
        layout.addWidget(entry, 1)
        remove_button = QPushButton("Remove")
        remove_button.clicked.connect(lambda: self.remove_command_row(row))
        layout.addWidget(remove_button)
        self.command_rows.insertWidget(self.command_rows.count() - 1, row)

    def add_command(self):
        """Add a blank command entry to the autostart list."""
        self.add_command_row()

    def remove_command_row(self, row):
        """Remove a command entry from the autostart list."""
        self.command_rows.removeWidget(row)
        row.setParent(None)
        row.deleteLater()


def apply_fields(c, fws):
    """Write the widget values into `c` (the config or one rule entry). Only changed keys are written; unchecked optional fields are removed."""
    for fw in fws:
        v, p = fw.get(), fw.f.path
        cur = getp(c, p)
        if v is None:
            if cur is not MISSING:
                delp(c, p)
        elif cur is MISSING:
            if fw.f.opt or py(v) != py(fw.default):
                putp(c, p, v)
        elif py(cur) != py(v):
            putp(c, p, v)


GROUP_HELP = {
    "Session": "Control session startup, focus behavior, and application interaction.",
    "XWayland (restart)": "Configure support for legacy X11 applications; changes require a restart.",
    "Lid events": "Choose commands to run when the laptop lid opens or closes.",
    "Screencast": "Control confirmation behavior when screencast targets change.",
    "DRM devices (restart)": "Exclude display devices Umbriel should not initialize; changes require a restart.",
    "Includes": "Load additional TOML configuration files.",
    "Windows": "Set default window borders, corners, opacity, and fullscreen appearance.",
    "Blur": "Tune background blur appearance and its rendering cost.",
    "Shadow": "Control window shadow visibility, softness, and position.",
    "Title bar": "Customize title-bar layout, text, buttons, and appearance.",
    "Tab bar": "Customize tab-bar placement, labels, spacing, and overflow.",
    "General": "Set colors used by the interface and its components.",
    "Borders": "Choose colors for focused, unfocused, and outer window borders.",
    "Overview": "Choose colors or behavior used by the workspace overview.",
    "Keyboard": "Set keyboard layout, repeat behavior, and layout tracking.",
    "Touchpad": "Configure tapping, scrolling, clicking, and touchpad sensitivity.",
    "Mouse": "Configure mouse buttons, scrolling, and pointer sensitivity.",
    "Tablet": "Map and calibrate drawing-tablet input.",
    "Touch": "Enable touch input and optionally map it to an output.",
    "Cursor": "Set cursor theme, hardware behavior, and hiding rules.",
    "Drag edge scroll": "Control scrolling when dragging near an output edge.",
    "Focus": "Set pointer-driven focus and window raising behavior.",
    "Shared": "Set layout defaults and reserved space at output edges.",
    "Scrolling": "Control column width and centering in the scrolling layout.",
    "Dwindle": "Set split direction and placement behavior for the dwindle layout.",
    "Master": "Set master placement, width, and new-window behavior.",
    "Stacking": "Control pointer snapping into stacking drop zones.",
    "Tab groups": "Set tab display, ordering, focus, and close behavior.",
    "Global": "Set workspace navigation behavior across the session.",
    "Defaults": "Set animation defaults inherited by individual animation events.",
    "Windows opening": "Control the animation shown when windows appear.",
    "Windows closing": "Control the animation shown when windows close.",
    "Windows moving": "Control animations for window movement.",
    "Windows resizing": "Control animations for window resizing.",
    "Window opacity and blur": "Animate window opacity and blur changes.",
    "Workspace switching": "Control the transition shown when switching workspaces.",
    "Scratchpad": "Animate scratchpad windows and configure their backdrop.",
    "Modal dialogs": "Control dialog transitions and parent-window dimming.",
    "Focus border": "Animate the border shown around the focused window.",
    "Dim unfocused windows": "Configure dimming for windows without focus.",
    "Layer-shell surfaces": "Control transitions for layer-shell surfaces such as panels.",
    "Drag physics": "Add spring-like motion when dragging windows.",
    "Selected effects ([effects] table)": "Choose named effect presets and configure when border and screen effects are drawn.",
    "Match (which windows)": "Define the window properties a rule must match.",
    "Open placement": "Choose where and how matching windows open.",
    "Look (opacity, blur, borders, title bar)": "Override appearance settings for matching windows.",
    "Behavior (pointer, VRR, HDR, ...)": "Override interaction and display behavior for matching windows.",
    "Identity": "Name a workspace rule and choose its index and output.",
    "Struts": "Reserve space along output edges for this workspace.",
    "Scrolling layout": "Override scrolling-layout behavior for this workspace.",
    "Master layout": "Override master-layout behavior for this workspace.",
    "Dwindle layout": "Override dwindle-layout behavior for this workspace.",
    "Stacking layout": "Override stacking-layout behavior for this workspace.",
    "Layout": "Set layout mode and general window placement behavior.",
    "Basics": "Enable the output and set its mode, position, and scale.",
    "Display features (VRR, HDR, ...)": "Configure variable refresh, tearing, HDR, and color depth.",
    "Workspaces and layout": "Set workspace count and layout behavior for this output.",
    "Preset": "Name an effect, choose its type, and select its shader.",
    "Border-only settings": "Tune extra appearance settings for border effects.",
    "Cursor-only settings": "Limit the area affected by a cursor effect.",
    "Pool": "Choose a set of effect presets and how Umbriel selects among them.",
}


class CollapsibleGroup(QGroupBox):
    """A settings group whose fields only show while its header checkbox is ticked.

    The header says "(using defaults)" when none of the group's keys are in the
    config file, or "(N set)" when some are. Groups with keys already in the file
    open automatically; everything else starts collapsed to save space.
    Collapsing never changes the file: hidden fields keep their values.
    """

    def __init__(self, title, n_set, collapsible=True, description=""):
        """Create the header checkbox (when collapsible) and the hidden/visible body that holds the form rows."""
        super().__init__()
        self.header = None
        self.search_original_expanded = None
        self.body = QWidget()
        self.setObjectName("settingsCard")
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        self.setStyleSheet(
            "QGroupBox#settingsCard {"
            " background: palette(window);"
            " border: 2px solid palette(midlight);"
            " border-radius: 18px;"
            " margin: 0px;"
            "}"
            "QGroupBox#settingsCard[cardCollapsed=\"true\"] {"
            " border-radius: 14px;"
            "}"
        )
        self.setProperty("cardHovered", False)
        self._hover_targets = []
        if description:
            self.setAccessibleDescription(description)
        self.form = QFormLayout(self.body)
        self.form.setHorizontalSpacing(16)
        self.form.setVerticalSpacing(10)
        self.form.setContentsMargins(16, 4, 16, 12)
        self.form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.ExpandingFieldsGrow)
        self.form.setLabelAlignment(Qt.AlignmentFlag.AlignLeft)
        self.form.setFormAlignment(Qt.AlignmentFlag.AlignTop)
        self.form.setRowWrapPolicy(QFormLayout.RowWrapPolicy.WrapLongRows)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)
        self.header_background = QWidget()
        self.header_background.setObjectName("settingsCardHeader")
        header_row = QHBoxLayout(self.header_background)
        header_row.setContentsMargins(10, 0, 10, 0)
        if collapsible:
            header = QPushButton()
            self.header = header
            header.setText(title)
            header.setCheckable(True)
            header.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
            header.setFixedHeight(SETTING_SECTION_BUTTON_HEIGHT)
            header.setFlat(True)
            header_font = QFont(header.font())
            header_font.setPointSize(SETTING_SECTION_BUTTON_FONT_SIZE)
            header.setFont(header_font)
            header.setStyleSheet(
                "QPushButton { text-align: left; background: transparent; border: 2px solid transparent; }"
                "QPushButton:hover { border-color: transparent; border-radius: 8px; }"
                "QPushButton:checked { background: transparent; }"
            )
            header.setAccessibleDescription(description)
            header.setToolTip(description)
            arrow = QToolButton()
            arrow.setAutoRaise(True)
            arrow.setFixedSize(24, 24)
            arrow.setStyleSheet(
                "QToolButton { background: transparent; border: 2px solid transparent; }"
                "QToolButton:hover { border-color: transparent; border-radius: 8px; }"
            )
            arrow.setAccessibleName(f"Toggle {title}")
            arrow.setToolTip("Expand or collapse this section")
            self.header_background.installEventFilter(self)
            self._hover_targets.append(self.header_background)

            def update_arrow(expanded):
                arrow.setArrowType(
                    Qt.ArrowType.DownArrow if expanded else Qt.ArrowType.RightArrow
                )

            header.toggled.connect(update_arrow)
            arrow.clicked.connect(lambda _checked=False: header.toggle())
            update_arrow(n_set > 0)
            header_row.addWidget(header, 1)
            header_row.addWidget(arrow)
        else:
            heading = QLabel(title)
            heading_font = QFont(heading.font())
            heading_font.setBold(True)
            heading_font.setPointSize(13)
            heading.setFont(heading_font)
            header_row.addWidget(heading)
            header_row.addStretch(1)
            self.help_button = QToolButton()
            self.help_button.setText("?")
            self.help_button.setAutoRaise(True)
            self.help_button.setFixedSize(20, 20)
            self.help_button.setAccessibleName(f"Help for {title}")
            self.help_button.setToolTip("\n".join(textwrap.fill(line, width=42) for line in description.splitlines()))
            header_row.addWidget(self.help_button)
        lay.addWidget(self.header_background)
        lay.addWidget(self.body)
        if collapsible:
            # Set visibility only after the body has its parent: reparenting resets it.
            header.toggled.connect(self.body.setVisible)
            header.toggled.connect(self._update_collapsed_style)
            header.setChecked(n_set > 0)
            self.body.setVisible(n_set > 0)
            self._update_collapsed_style(n_set > 0)

    def _update_collapsed_style(self, expanded):
        self.setProperty("cardCollapsed", not expanded)
        self.style().unpolish(self)
        self.style().polish(self)
        self.update()

    def paintEvent(self, event):
        super().paintEvent(event)
        if self.property("cardHovered"):
            painter = QPainter(self)
            painter.setRenderHint(QPainter.RenderHint.Antialiasing)
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(self.palette().color(QPalette.ColorRole.Midlight))
            radius = 12 if self.property("cardCollapsed") else 16
            painter.drawRoundedRect(self.rect().adjusted(2, 2, -2, -2), radius, radius)

    def eventFilter(self, watched, event):
        if watched in self._hover_targets:
            if event.type() == QEvent.Type.Enter:
                self._set_card_hovered(True)
            elif event.type() == QEvent.Type.Leave:
                self._set_card_hovered(False)
        return super().eventFilter(watched, event)

    def _set_card_hovered(self, hovered):
        if self.property("cardHovered") == hovered:
            return
        self.setProperty("cardHovered", hovered)
        self.update()

    def setExpanded(self, expanded):
        """Expand or collapse the group while keeping its header checkbox in sync."""
        if self.header is not None:
            self.header.setChecked(expanded)

    def rememberSearchState(self):
        """Remember whether the group was expanded before a search temporarily opens it."""
        if self.search_original_expanded is None:
            self.search_original_expanded = (
                self.header.isChecked() if self.header is not None else True
            )

    def restoreSearchState(self):
        """Restore the group's visibility and expansion state after search is cleared."""
        self.setVisible(True)
        if self.search_original_expanded is not None:
            self.setExpanded(self.search_original_expanded)
            self.search_original_expanded = None


_GROUP_EXPANSION_PATH = os.path.join(
    GUI_DATA_DIR, "gui-state.json"
)
_group_expansion_states = None


def load_group_expansion_states():
    """Load saved section expansion states, falling back to defaults if unavailable."""
    global _group_expansion_states
    if _group_expansion_states is not None:
        return _group_expansion_states
    try:
        migrate_gui_file(
            os.path.join(
                os.environ.get("XDG_CONFIG_HOME") or os.path.expanduser("~/.config"),
                "umbriel",
                "gui-state.json",
            ),
            _GROUP_EXPANSION_PATH,
        )
        with open(_GROUP_EXPANSION_PATH, encoding="utf-8") as file:
            data = json.load(file)
        if not isinstance(data, dict):
            raise ValueError("the saved GUI state must be a JSON object")
        _group_expansion_states = {}
        for page, groups in data.items():
            if isinstance(page, str) and isinstance(groups, dict):
                _group_expansion_states[page] = {
                    title: expanded
                    for title, expanded in groups.items()
                    if isinstance(title, str) and isinstance(expanded, bool)
                }
    except FileNotFoundError:
        _group_expansion_states = {}
    except (OSError, ValueError) as error:
        QMessageBox.warning(
            None,
            "Could not load GUI state",
            f"Section expansion states could not be loaded: {error}",
        )
        _group_expansion_states = {}
    return _group_expansion_states


def save_group_expansion_state(page, title, expanded):
    """Persist the user's expanded/collapsed state for a settings section."""
    states = load_group_expansion_states()
    states.setdefault(page, {})[title] = bool(expanded)
    try:
        write_text_file(_GROUP_EXPANSION_PATH, json.dumps(states, indent=2))
    except OSError as error:
        QMessageBox.warning(
            None,
            "Could not save GUI state",
            f"Section expansion state could not be saved: {error}",
        )


CATEGORY_HELP = {
    "Basics": "Core session preferences, user folders, and default applications.",
    "Look": "Window appearance, colors, animation timing, and visual effects.",
    "Behavior": "Input devices, window layouts, workspaces, and overview behavior.",
    "Bindings": "Configure keyboard shortcuts and their actions.",
    "Rules and devices": "Create window, workspace, output, security, and input-device overrides.",
    "General": "Session startup, XWayland, screencast, device exclusions, and included config files.",
    "User folders": "Set the standard XDG folders used by applications.",
    "Default apps": "Choose applications associated with common file types and MIME types.",
    "Appearance": "Set window decorations, blur, shadows, and tab-bar styling.",
    "Colors": "Customize interface, window, overview, tab-bar, and title-bar colors.",
    "Animation": "Set default timing and per-event animations, including drag physics.",
    "Animation curves": "Define reusable Bézier and spring curves for animation events.",
    "Effects": "Define reusable shader presets and pools for window, border, screen, and cursor effects.",
    "Input": "Configure keyboard, pointer, touchpad, tablet, and touch behavior.",
    "Layout": "Choose the tiling layout and configure its sizing, spacing, and tab behavior.",
    "Workspaces": "Configure workspace navigation, overview, and hot-corner actions.",
    "Keybinds": "Add, edit, and organize keyboard shortcuts.",
    "Environment": "Set environment variables passed to the session and applications.",
    "Outputs": "Configure each display's mode, position, scale, workspaces, and display features. Use Inspect connected outputs to read live modes from `umbriel outputs --json`. A monitor identity follows the same display between ports; a connector name targets a physical port. This command needs Umbriel running in the session you want to configure.",
    "Window rules": "Match windows by their properties and override placement, appearance, or behavior.",
    "Layer rules": "Match layer-shell surfaces and configure their blur behavior.",
    "Workspace rules": "Set names, outputs, and layout overrides for selected workspaces.",
    "Security rules": "Allow selected applications or sandboxes to access protocol globals.",
    "Scratchpads": "Configure named temporary window groups and their launch commands.",
    "Input devices": "Override keyboard, pointer, and touchpad settings for a specific device.",
}

SIDEBAR_SECTIONS = [
    ("Desktop", ["User folders", "Default apps"]),
    ("Basics", ["General"]),
    ("Look", ["Appearance", "Colors", "Animation", "Animation curves", "Effects"]),
    ("Behavior", ["Input", "Layout", "Workspaces"]),
    ("Bindings", ["Keybinds"]),
    ("Rules and devices", ["Window rules", "Layer rules", "Workspace rules", "Outputs",
                           "Scratchpads", "Input devices", "Security rules", "Environment"]),
]

SETTING_SECTION_BUTTON_FONT_SIZE = 10
SETTING_SECTION_BUTTON_HEIGHT = 32


def form_page(groups, doc, store, collapsible=True, category="", schema_prefix=""):
    """Build a scrollable page from [(title, [Field, ...]), ...].

    Every field gets a FieldWidget (also appended to `store` so saving can read
    them). `doc` is the table the field paths are looked up in: the whole config
    for normal tabs, or one rule/output entry for the rule editors.
    """
    page = QWidget()
    page.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
    page_layout = QHBoxLayout(page)
    page_layout.setContentsMargins(18, 12, 18, 12)
    page_layout.setSpacing(0)
    content = QWidget()
    content.setMinimumWidth(0)
    content.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
    page_layout.addWidget(content, 1)
    v = QVBoxLayout(content)
    v.setContentsMargins(0, 0, 0, 0)
    v.setSpacing(10)

    overview = OverviewButton()
    overview.setObjectName("settingsOverview")
    overview.setCursor(Qt.CursorShape.PointingHandCursor)
    overview.setAccessibleName(category or "Settings overview")
    overview.setAccessibleDescription(
        "Click to expand or collapse all settings sections."
    )
    overview.setToolTip(
        "Click to expand or collapse all settings sections.\n"
        "Only settings you choose to override are written; unset values keep Umbriel's defaults."
        + ("\n" + CATEGORY_HELP[category] if category in CATEGORY_HELP else "")
    )
    overview.setStyleSheet(
        "QPushButton#settingsOverview {"
        " background: transparent;"
        " border: 0px;"
        " border-radius: 8px;"
        " text-align: left;"
        "}"
        "QPushButton#settingsOverview:hover {"
        " background: palette(alternate-base);"
        "}"
    )
    overview_layout = QVBoxLayout(overview)
    overview_layout.setContentsMargins(6, 4, 6, 4)
    page_title = QLabel(category or "Settings")
    page_title.setObjectName("pageTitle")
    title_font = QFont(page_title.font())
    title_font.setBold(True)
    title_font.setPointSize(13)
    page_title.setFont(title_font)
    page_title.setForegroundRole(QPalette.ColorRole.Highlight)
    page_title.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
    overview_layout.addWidget(page_title)
    v.addWidget(overview)

    section_navigation = QWidget()
    section_navigation.setObjectName("sectionNavigation")
    section_navigation.setMinimumWidth(0)
    section_navigation.setSizePolicy(
        QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum
    )
    section_navigation_policy = section_navigation.sizePolicy()
    section_navigation_policy.setHeightForWidth(True)
    section_navigation.setSizePolicy(section_navigation_policy)
    section_layout = FlowLayout(section_navigation)

    section_buttons = []
    section_groups = []
    kde_fields = []
    saved_expansion_states = load_group_expansion_states().get(category, {})
    group_page = QWidget()
    group_page.setMinimumWidth(0)
    group_page.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
    group_layout = QVBoxLayout(group_page)
    group_layout.setContentsMargins(0, 0, 0, 0)
    group_layout.setSpacing(8)
    for title, fields in groups:
        n_set = sum(1 for f in fields if getp(doc, f.path) is not MISSING)
        group_description = GROUP_HELP.get(title)
        if group_description is None and title.startswith("Hot corner:"):
            corner = title.partition(":")[2].strip()
            group_description = f"Set the trigger delay and action for the {corner} screen corner."
        if group_description is None:
            group_description = f"Settings for {title.lower()}."
        box = CollapsibleGroup(title, n_set, collapsible, group_description)
        section_groups.append(box)
        if box.header is not None:
            if title in saved_expansion_states:
                box.setExpanded(saved_expansion_states[title])

            def save_expansion(expanded, group=box, group_title=title):
                if group.search_original_expanded is None:
                    save_group_expansion_state(category, group_title, expanded)

            box.header.toggled.connect(save_expansion)
        for f in fields:
            current = getp(doc, f.path)
            if f.path == ("include", "optional", "files") and current is not MISSING:
                current = normalize_optional_includes(py(current))
            schema_path = ".".join(part for part in (schema_prefix, ".".join(f.path)) if part)
            fw = FieldWidget(f, current, schema_path)
            if category == "Colors" and f.path in TITLE_BAR_KEYS:
                kde_fields.append(fw)
            if f.kind == "str" and fw.schema_option and fw.schema_option.get("format") == "effect":
                fw.w.setPlaceholderText("Effect preset name")
            elif f.kind in ("list", "strorlist"):
                fw.w.setPlaceholderText("Comma-separated values" if f.kind == "list" else "Text or TOML array")
            help_description = setting_description(f, category or title, title)
            fw.help_button.setToolTip(help_description)
            field_title = QLabel(f.label)
            title_font = QFont(field_title.font())
            title_font.setBold(True)
            title_font.setPointSize(10)
            field_title.setFont(title_font)
            description_text = (
                help_description
                if category
                else setting_description(f, "Settings", title)
            ).partition(
                "\nApplies to:"
            )[0]
            description_text = " ".join(description_text.splitlines())
            description_text = description_text.partition(
                " Leave this setting unset to omit its key"
            )[0]
            description_text = description_text.partition(
                " This value is written directly to the config."
            )[0]
            description_text = description_text.partition(" Options:")[0]
            if f.kind == "combo":
                description_text += " Choose or type a custom value."
            description = WrappedLabel(description_text)
            description.setForegroundRole(QPalette.ColorRole.PlaceholderText)
            label_widget = SettingLabel(field_title, description)
            row_widget = SettingRow(label_widget, fw)
            fw.field_label = field_title
            fw.search_group = box
            fw.search_group_title = title
            fw.search_form = box.form
            fw.search_row = row_widget
            store.append(fw)
            box.form.addRow(row_widget)
            if fw.opacity_widget is not None:
                opacity_title = QLabel(f"{f.label} opacity")
                opacity_title.setFont(title_font)
                opacity_description = WrappedLabel("Color opacity: 0.0 is transparent, 1.0 is opaque.")
                opacity_description.setForegroundRole(QPalette.ColorRole.PlaceholderText)
                opacity_row = SettingRow(SettingLabel(opacity_title, opacity_description), fw.opacity_widget)
                fw.opacity_row = opacity_row
                fw.opacity_help.setToolTip("Color opacity: 0.0 is transparent, 1.0 is opaque.")
                fw.opacity_widget.setFixedWidth(fw.sizeHint().width())
                box.form.addRow(opacity_row)
        group_layout.addWidget(box, 0, Qt.AlignmentFlag.AlignTop)

        section_button = QToolButton()
        section_button.setText(title)
        section_button.setCheckable(True)
        section_button.setAutoRaise(True)
        section_button.setFixedHeight(SETTING_SECTION_BUTTON_HEIGHT)
        section_font = QFont(section_button.font())
        section_font.setPointSize(SETTING_SECTION_BUTTON_FONT_SIZE)
        section_button.setFont(section_font)
        section_button.setToolTip(f"Toggle {title}")
        section_button.setStyleSheet(
            "QToolButton {"
            " border: 1px solid palette(midlight);"
            " border-radius: 9px;"
            " padding: 4px 10px;"
            " background: palette(window);"
            "}"
            "QToolButton:hover { background: palette(midlight); }"
            "QToolButton:checked {"
            " background: palette(highlight);"
            " color: palette(highlighted-text);"
            " border-color: palette(highlight);"
            " font-weight: 600;"
            "}"
            "QToolButton:!checked {"
            " color: palette(text);"
            "}"
        )
        section_button.setChecked(
            box.header.isChecked() if box.header is not None else True
        )
        section_buttons.append(section_button)
        section_layout.addWidget(section_button)

    group_layout.addStretch(1)
    v.insertWidget(1, section_navigation)

    sections_scroll = QScrollArea()
    sections_scroll.setObjectName("settingsSectionsScroll")
    sections_scroll.setWidgetResizable(True)
    sections_scroll.setFrameShape(QScrollArea.Shape.NoFrame)
    sections_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
    sections_scroll.setWidget(group_page)
    v.addWidget(sections_scroll, 1)

    def navigate_to_group(index, toggle=False):
        group = section_groups[index]
        if group.header is not None and toggle:
            group.setExpanded(not group.header.isChecked())
        elif group.header is None:
            section_buttons[index].setChecked(True)
        sections_scroll.ensureWidgetVisible(group, 0, 12)

    for index, (group, button) in enumerate(zip(section_groups, section_buttons)):
        button.clicked.connect(
            lambda _checked=False, group_index=index: navigate_to_group(
                group_index, toggle=True
            )
        )
        if group.header is not None:
            group.header.toggled.connect(button.setChecked)

    def toggle_all_groups():
        expand = not all(
            group.header.isChecked()
            for group in section_groups
            if group.header is not None
        )
        for group in section_groups:
            group.setExpanded(expand)

    overview.clicked.connect(toggle_all_groups)

    if kde_fields:
        page.kde_titlebar_follower = KdeTitleBarFollower(kde_fields, page)

    return page

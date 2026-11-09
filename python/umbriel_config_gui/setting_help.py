"""Help text and contextual descriptions for settings pages."""

import textwrap


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


"""Installed Umbriel schema loading and GUI coverage comparison."""


from . import state
from .common import (
    fnmatch,
    json,
    shutil,
    subprocess,
)
from .field_defs import (
    EFFECT_POOL_GROUPS,
    EFFECT_PRESET_GROUPS,
    INPUT_DEVICE,
    LAYER_RULE,
    OUTPUT_GROUPS,
    SCRATCHPAD,
    SECURITY_RULE,
    TABS,
    WINDOW_RULE_GROUPS,
    WORKSPACE_RULE_GROUPS,
)


def load_umbriel_schema(timeout=5):
    """Load option metadata from the installed Umbriel CLI."""
    executable = shutil.which("umbriel")
    if not executable:
        raise FileNotFoundError("Umbriel CLI was not found on PATH.")
    result = subprocess.run(
        [executable, "config", "schema", "--json"],
        capture_output=True,
        text=True,
        timeout=timeout,
        check=False,
    )
    if result.returncode:
        detail = result.stderr.strip() or result.stdout.strip() or f"exit status {result.returncode}"
        raise RuntimeError(f"`umbriel config schema --json` failed: {detail}")
    try:
        schema = json.loads(result.stdout)
    except json.JSONDecodeError as error:
        raise ValueError(f"`umbriel config schema --json` returned invalid JSON: {error}") from error
    if not isinstance(schema, dict) or not isinstance(schema.get("options"), list):
        raise ValueError("`umbriel config schema --json` returned an unexpected schema document.")
    return schema


def field_schema_option(path):
    """Find an installed-schema entry for a field's fully qualified TOML path."""
    path = str(path)
    return state.ACTIVE_SCHEMA_OPTIONS.get(path) or state.ACTIVE_SCHEMA_OPTIONS.get(path.replace("<name>", "*"))


def schema_field_catalog():
    """Return canonical config paths represented by Field widgets and custom editors."""
    catalog = []

    def add_fields(groups, prefix=""):
        for _, fields in groups:
            for field in fields:
                path = ".".join(part for part in (prefix, ".".join(field.path)) if part)
                catalog.append((path, field.kind))

    for groups in TABS.values():
        add_fields(groups)
    for prefix, groups in (
        ("output.<name>", OUTPUT_GROUPS),
        ("window_rule[]", WINDOW_RULE_GROUPS),
        ("layer_rule[]", [("Layer rule", LAYER_RULE)]),
        ("workspace[]", WORKSPACE_RULE_GROUPS),
        ("security_context_rule[]", [("Security rule", SECURITY_RULE)]),
        ("scratchpad[]", [("Scratchpad", SCRATCHPAD)]),
        ("input.device[]", [("Device override", INPUT_DEVICE)]),
        ("effects.preset.<name>", EFFECT_PRESET_GROUPS),
        ("effects.pool.<name>", EFFECT_POOL_GROUPS),
    ):
        add_fields(groups, prefix)

    catalog.extend([
        ("keybinds.<name>", "custom"),
        ("environment.<name>", "custom"),
        ("animation.beziers.<name>", "custom"),
        ("animation.springs.<name>.stiffness", "custom"),
        ("animation.springs.<name>.damping", "custom"),
    ])
    return catalog


def check_schema_coverage(schema):
    """Compare supported schema options with the GUI's field and custom-editor catalog."""
    options = schema.get("options", [])
    catalog = schema_field_catalog()
    schema_paths = {option.get("path") for option in options if isinstance(option, dict)}

    def normalize(part):
        return part.replace("[]", "__array__").replace("<name>", "*")

    def pattern_matches(pattern, value):
        return fnmatch.fnmatchcase(normalize(value), normalize(pattern))

    missing = []
    for option in options:
        if not isinstance(option, dict) or option.get("type") in ("table", "map", "array_of_tables"):
            continue
        path = str(option.get("path", ""))
        path_parts = path.split(".")
        covered = False
        for field_path, kind in catalog:
            field_parts = field_path.split(".")
            for length in range(1, min(len(field_parts), len(path_parts)) + 1):
                if all(
                    pattern_matches(field_parts[index], path_parts[index])
                    for index in range(length)
                ):
                    if length == len(field_parts) and (
                        kind in ("raw", "custom") or len(field_parts) == len(path_parts)
                    ):
                        covered = True
                        break
            if covered:
                break
        if not covered:
            missing.append(path)

    stale = []
    for field_path, _ in catalog:
        if not any(
            len(path.split(".")) >= len(field_path.split("."))
            and all(pattern_matches(field_part, schema_part) for field_part, schema_part
                    in zip(field_path.split("."), path.split(".")))
            for path in schema_paths
        ):
            stale.append(field_path)
    return sorted(set(missing)), sorted(set(stale))


# ------------------------------------------------------------ rule list editor

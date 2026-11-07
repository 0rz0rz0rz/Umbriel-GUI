"""Mutable process state shared by GUI modules."""
import argparse
import os

DEFAULT_CONFIG_PATH = os.path.expanduser("~/.config/umbriel/config.toml")
PATH = DEFAULT_CONFIG_PATH
_CLI_ARGS = argparse.Namespace(
    config=None, config_option=None, no_validate=False, no_rebuild=False, check_schema=False
)
ACTIVE_SCHEMA_OPTIONS = {}

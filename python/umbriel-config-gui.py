#!/usr/bin/env python3
"""Compatibility launcher for Umbriel Settings."""
import sys

from umbriel_config_gui import __version__
from umbriel_config_gui.window import main

if __name__ == "__main__":
    sys.exit(main())

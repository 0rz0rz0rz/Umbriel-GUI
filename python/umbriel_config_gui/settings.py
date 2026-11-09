"""Compatibility exports for settings fields and page construction."""

from .field_widget import FieldWidget, apply_fields, installed_cursor_themes
from .setting_help import CATEGORY_HELP, FIELD_HELP, GROUP_HELP, setting_description
from .settings_layout import (
    CollapsibleGroup, SIDEBAR_SECTIONS, SETTING_SECTION_BUTTON_FONT_SIZE,
    SETTING_SECTION_BUTTON_HEIGHT, form_page, load_group_expansion_states,
    save_group_expansion_state,
)

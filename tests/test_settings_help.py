import unittest

from umbriel_config_gui import settings
from umbriel_config_gui.field_defs import F
from umbriel_config_gui.field_widget import FieldWidget
from umbriel_config_gui.setting_help import FIELD_HELP, setting_description
from umbriel_config_gui.settings_layout import form_page


class SettingsHelpTests(unittest.TestCase):
    def test_description_includes_field_help_and_context(self):
        field = F("Enabled", "general.enabled", "bool", False, None, True)

        description = setting_description(field, "General", "Session")

        self.assertIn(FIELD_HELP["Enabled"], description)
        self.assertIn("Applies to: General > Session", description)
        self.assertIn("Config key: general.enabled", description)

    def test_settings_facade_reexports_moved_components(self):
        self.assertIs(settings.FieldWidget, FieldWidget)
        self.assertIs(settings.form_page, form_page)


if __name__ == "__main__":
    unittest.main()

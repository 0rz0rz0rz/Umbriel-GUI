import base64
import hashlib
import os
import tempfile
import unittest
from unittest.mock import patch

from PySide6.QtGui import QColor, QImage
from PySide6.QtWidgets import QApplication

from umbriel_config_gui import common, state, window


class AppIconTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.tempdir = tempfile.TemporaryDirectory()
        self.addCleanup(self.tempdir.cleanup)
        self.icon_path = os.path.join(self.tempdir.name, "icon.jpg")
        icon_patch = patch.object(common, "APP_ICON_PATH", self.icon_path)
        icon_patch.start()
        self.addCleanup(icon_patch.stop)

    def write_icon(self, color):
        image = QImage(256, 256, QImage.Format.Format_RGB32)
        image.fill(QColor(color))
        self.assertTrue(image.save(self.icon_path, "JPEG"))

    def test_custom_jpeg_is_used_for_window_and_desktop_icon(self):
        self.write_icon("red")
        icon = common.create_app_icon()
        pixel = icon.pixmap(32, 32).toImage().pixelColor(16, 16)
        self.assertGreater(pixel.red(), 240)
        self.assertLess(pixel.green(), 15)
        self.assertLess(pixel.blue(), 15)

        with patch.object(common.sys, "platform", "linux"), patch.dict(
            os.environ, {"XDG_DATA_HOME": self.tempdir.name}
        ):
            common.install_desktop_icon(icon)
        desktop_icon = QImage(os.path.join(
            self.tempdir.name, "icons", "hicolor", "128x128", "apps", "umbriel-config-gui.png"
        ))
        self.assertFalse(desktop_icon.isNull())
        self.assertEqual((desktop_icon.width(), desktop_icon.height()), (128, 128))
        self.assertGreater(desktop_icon.pixelColor(64, 64).red(), 240)
        desktop_path = os.path.join(
            self.tempdir.name, "applications", "umbriel-config-gui.desktop"
        )
        with open(desktop_path, encoding="utf-8") as desktop_file:
            self.assertIn("Name=Umbriel Settings\n", desktop_file.read())

    def test_missing_custom_icon_uses_embedded_icon(self):
        icon = common.create_app_icon()
        self.assertFalse(icon.isNull())
        self.assertEqual(
            hashlib.sha256(base64.b64decode(common._APP_ICON_DATA)).hexdigest(),
            "52b5fea94dfc8ee8e39709aefc7353527a4a2ed7f5b88ea64646b7b1287778ae",
        )

    def test_invalid_custom_icon_warns_and_uses_embedded_icon(self):
        with open(self.icon_path, "wb") as icon:
            icon.write(b"not an image")
        with self.assertWarnsRegex(RuntimeWarning, "Could not load.*icon.jpg"):
            self.assertFalse(common.create_app_icon().isNull())

    def test_application_uses_new_display_name_and_existing_desktop_id(self):
        with (
            patch.object(state, "PATH", state.PATH),
            patch.object(state, "_CLI_ARGS", state._CLI_ARGS),
            patch.object(window, "QApplication") as app_class,
            patch.object(window, "Window"),
            patch.object(window, "create_app_icon"),
            patch.object(window, "apply_interaction_styles"),
            patch.object(window, "install_desktop_icon"),
        ):
            window.main([])
            app = app_class.return_value
            app.setApplicationName.assert_called_once_with("Umbriel Settings")
            app.setApplicationDisplayName.assert_called_once_with("Umbriel Settings")
            app.setDesktopFileName.assert_called_once_with("umbriel-config-gui")


if __name__ == "__main__":
    unittest.main()

"""
Unit tests for Volkswagen Sniffer mascot assets, metadata, and UI integration.
"""

import os
import json
import unittest

from tools.sniffer_mascot import (
    MASCOT_NAME,
    MASCOT_DESCRIPTION,
    get_mascot_assets,
    get_mascot_greeting,
)


class TestSnifferMascot(unittest.TestCase):
    def test_mascot_metadata(self):
        """Verify mascot constants are defined properly."""
        self.assertEqual(MASCOT_NAME, "Volkswagen Sniffer")
        self.assertIn("VW California", MASCOT_DESCRIPTION)

    def test_mascot_assets_exist(self):
        """Verify that all transparent PNG mascot assets exist and are non-empty."""
        assets = get_mascot_assets()
        self.assertIn("avatar", assets)
        self.assertIn("sitting", assets)
        self.assertIn("standing", assets)

        for key, info in assets.items():
            self.assertTrue(info["exists"], f"Mascot asset {key} missing: {info['path']}")
            self.assertGreater(info["size_bytes"], 1000, f"Mascot asset {key} is too small or empty")

    def test_mascot_greetings(self):
        """Verify localized greetings in PL, DE, and EN."""
        # Polish
        pl_greeting = get_mascot_greeting("Mateusz", "pl")
        self.assertIn("Volkswagen Sniffer", pl_greeting)
        self.assertIn("Mateusz", pl_greeting)

        # German
        de_greeting = get_mascot_greeting("Mateusz", "de")
        self.assertIn("Volkswagen Sniffer", de_greeting)
        self.assertIn("Hallo", de_greeting)

        # English
        en_greeting = get_mascot_greeting("Mateusz", "en")
        self.assertIn("Volkswagen Sniffer", en_greeting)
        self.assertIn("Hello", en_greeting)

    def test_manifest_sniffer_branding(self):
        """Verify that manifest.json contains Volkswagen Sniffer."""
        manifest_path = os.path.join(
            os.path.dirname(os.path.dirname(__file__)), "frontend", "manifest.json"
        )
        with open(manifest_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        self.assertIn("Volkswagen Sniffer", data["name"])
        self.assertEqual(data["short_name"], "VW Sniffer")

    def test_chat_bubbles_styling_and_classes(self):
        """Verify that app.js sets proper message classes and styles.css styles chat bubbles."""
        app_js_path = os.path.join(
            os.path.dirname(os.path.dirname(__file__)), "frontend", "app.js"
        )
        with open(app_js_path, "r", encoding="utf-8") as f:
            app_js = f.read()

        self.assertIn("msgDiv.className = `message ${role}`;", app_js)
        self.assertIn("formatChatMessage", app_js)
        self.assertIn("message-header-row", app_js)
        self.assertIn("sniffer-badge-pill", app_js)

        styles_css_path = os.path.join(
            os.path.dirname(os.path.dirname(__file__)), "frontend", "styles.css"
        )
        with open(styles_css_path, "r", encoding="utf-8") as f:
            styles_css = f.read()

        self.assertIn(".message.user", styles_css)
        self.assertIn(".message.assistant", styles_css)
        self.assertIn(".message.assistant .message-content-wrap", styles_css)
        self.assertIn(".message.user .message-content-wrap", styles_css)
        self.assertIn(".chat-bullet-item", styles_css)


if __name__ == "__main__":
    unittest.main()

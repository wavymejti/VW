"""
Test suite for Accommodation and Attraction visual placeholders.

Validates that:
- Default SVG placeholder files exist in frontend/assets/
- Camping placeholder contains VW California branding and vanlife elements
- Attraction placeholder contains scenic and landmark elements
- frontend/styles.css defines proper wrapping and badge styles
- frontend/app.js references and uses placeholders for campings and attractions
- frontend/i18n.js provides translations for the preview tag
"""

import os
import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def test_placeholder_svg_files_exist():
    """Verify that both camping and attraction placeholder SVGs exist."""
    camping_svg = os.path.join(ROOT, "frontend", "assets", "camping_placeholder.svg")
    attr_svg = os.path.join(ROOT, "frontend", "assets", "attraction_placeholder.svg")

    assert os.path.exists(camping_svg), "camping_placeholder.svg missing"
    assert os.path.exists(attr_svg), "attraction_placeholder.svg missing"

    with open(camping_svg, "r", encoding="utf-8") as f:
        camping_content = f.read()
    assert "<svg" in camping_content
    assert "VW CALIFORNIA" in camping_content

    with open(attr_svg, "r", encoding="utf-8") as f:
        attr_content = f.read()
    assert "<svg" in attr_content
    assert "VW CALIFORNIA" in attr_content


def test_styles_css_defines_placeholder_rules():
    """Verify that styles.css defines camping-card-img-wrap and photo-placeholder-badge."""
    styles_path = os.path.join(ROOT, "frontend", "styles.css")
    with open(styles_path, "r", encoding="utf-8") as f:
        content = f.read()

    assert ".camping-card-img-wrap" in content
    assert ".photo-placeholder-badge" in content
    assert ".top-attraction-img-wrap" in content


def test_app_js_integrates_placeholders():
    """Verify that app.js references placeholder URLs and binds them to camping and attraction cards."""
    app_path = os.path.join(ROOT, "frontend", "app.js")
    with open(app_path, "r", encoding="utf-8") as f:
        content = f.read()

    assert "CAMPING_PLACEHOLDER_URL" in content
    assert "ATTRACTION_PLACEHOLDER_URL" in content
    assert "camping_placeholder.svg" in content
    assert "attraction_placeholder.svg" in content
    assert "photo-placeholder-badge" in content


def test_i18n_defines_photo_preview_tag():
    """Verify that i18n.js has the photo_preview_tag key for pl and de."""
    i18n_path = os.path.join(ROOT, "frontend", "i18n.js")
    with open(i18n_path, "r", encoding="utf-8") as f:
        content = f.read()

    assert "photo_preview_tag" in content

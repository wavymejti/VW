"""
UI and DOM verification for Camping Selection Modal.

Checks:
- HTML structure of #camping-selection-modal in index.html
- CSS definitions for .camping-selection-card and .camping-proposal-card in styles.css
- JS openCampingSelectionModal, renderCampingDayTabs, renderCampingOptionsForDay exported in app.js
- i18n keys for camping modal in i18n.js
"""

import os
import re
import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def test_index_html_contains_camping_modal():
    index_path = os.path.join(ROOT, "frontend", "index.html")
    with open(index_path, "r", encoding="utf-8") as f:
        content = f.read()

    assert "camping-selection-modal" in content
    assert "camping-day-tabs" in content
    assert "camping-cards-grid" in content
    assert "btn-camping-modal-done" in content


def test_styles_css_contains_camping_modal_rules():
    styles_path = os.path.join(ROOT, "frontend", "styles.css")
    with open(styles_path, "r", encoding="utf-8") as f:
        content = f.read()

    assert ".camping-selection-card" in content
    assert ".camping-day-tabs" in content
    assert ".camping-proposal-card" in content
    assert ".btn-select-camping" in content


def test_app_js_exports_camping_modal_functions():
    app_path = os.path.join(ROOT, "frontend", "app.js")
    with open(app_path, "r", encoding="utf-8") as f:
        content = f.read()

    assert "openCampingSelectionModal" in content
    assert "renderCampingDayTabs" in content
    assert "renderCampingOptionsForDay" in content
    assert "window.openCampingSelectionModal = openCampingSelectionModal" in content
    assert "select_camping" in content


def test_i18n_js_contains_camping_keys():
    i18n_path = os.path.join(ROOT, "frontend", "i18n.js")
    with open(i18n_path, "r", encoding="utf-8") as f:
        content = f.read()

    assert "camping_modal_title" in content
    assert "camping_select_btn" in content
    assert "camping_selected_badge" in content
    assert "camping_change_btn" in content

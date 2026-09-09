"""
Unit tests for contextual view tutorials (Mapa, Pamięć, Wyjazdy) and i18n keys.
"""

import os
import re

def test_view_tutorials_i18n_keys():
    """Verify that all tutorial translation keys for Map, Memory, and Trips exist for PL and DE."""
    i18n_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "frontend", "i18n.js")
    assert os.path.exists(i18n_path), "frontend/i18n.js does not exist"
    
    with open(i18n_path, "r", encoding="utf-8") as f:
        content = f.read()

    expected_keys = [
        "tut_map_step1_title",
        "tut_map_step1_desc",
        "tut_map_step2_title",
        "tut_map_step2_desc",
        "tut_map_step3_title",
        "tut_map_step3_desc",
        "tut_mem_step1_title",
        "tut_mem_step1_desc",
        "tut_mem_step2_title",
        "tut_mem_step2_desc",
        "tut_mem_step3_title",
        "tut_mem_step3_desc",
        "tut_trips_step1_title",
        "tut_trips_step1_desc",
        "tut_trips_step2_title",
        "tut_trips_step2_desc",
    ]

    for key in expected_keys:
        assert key in content, f"Missing key {key} in i18n.js"


def test_app_js_contains_tutorial_suites():
    """Verify that frontend/app.js contains updated MAP, MEMORY, and TRIPS tutorial step definitions."""
    app_js_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "frontend", "app.js")
    assert os.path.exists(app_js_path), "frontend/app.js does not exist"

    with open(app_js_path, "r", encoding="utf-8") as f:
        content = f.read()

    assert "MAP_TUTORIAL_STEPS" in content
    assert "MEMORY_TUTORIAL_STEPS" in content
    assert "TRIPS_TUTORIAL_STEPS" in content
    assert "startTutorialSuite" in content
    assert "Inspiracje Podróżnicze AI" in content
    assert "btn-open-suggestions" in content
    assert "Dlaczego to polecamy" in content
    assert "Interaktywna Mapa & Warstwy na Żywo" in content


def test_tutorial_backdrop_cutout_architecture():
    """Verify that tutorial uses backdrop cutout so highlighted elements remain sharp and unblurred."""
    index_html_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "frontend", "index.html")
    styles_css_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "frontend", "styles.css")
    app_js_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "frontend", "app.js")

    with open(index_html_path, "r", encoding="utf-8") as f:
        html_content = f.read()
    with open(styles_css_path, "r", encoding="utf-8") as f:
        css_content = f.read()
    with open(app_js_path, "r", encoding="utf-8") as f:
        js_content = f.read()

    # Verify backdrop element exists in index.html
    assert 'id="tutorial-backdrop"' in html_content
    assert 'class="tutorial-backdrop"' in html_content

    # Verify CSS applies blur on backdrop rather than the whole overlay container
    assert ".tutorial-backdrop {" in css_content
    assert "backdrop-filter: blur(" in css_content
    assert "clip-path" in css_content

    # Verify app.js dynamically updates clipPath polygon cutout around highlighted target
    assert "clipPolygon" in js_content
    assert "polygon(evenodd" in js_content
    assert "backdrop.style.clipPath" in js_content

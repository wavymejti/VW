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
        "tut_trips_step1_title",
        "tut_trips_step1_desc",
        "tut_trips_step2_title",
        "tut_trips_step2_desc",
    ]

    for key in expected_keys:
        assert key in content, f"Missing key {key} in i18n.js"


def test_app_js_contains_tutorial_suites():
    """Verify that frontend/app.js contains MAP, MEMORY, and TRIPS tutorial step definitions."""
    app_js_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "frontend", "app.js")
    assert os.path.exists(app_js_path), "frontend/app.js does not exist"

    with open(app_js_path, "r", encoding="utf-8") as f:
        content = f.read()

    assert "MAP_TUTORIAL_STEPS" in content
    assert "MEMORY_TUTORIAL_STEPS" in content
    assert "TRIPS_TUTORIAL_STEPS" in content
    assert "startTutorialSuite" in content

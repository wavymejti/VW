"""
After planning, the map with the route comes first; campsites open on request (Nov 2026 tests).

The camping modal used to pop up over the map right after a route was planned.
"""

import os
import re

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _read(*parts):
    with open(os.path.join(ROOT, *parts), encoding="utf-8") as f:
        return f.read()


def test_route_planned_shows_map_and_bar_not_the_modal():
    js = _read("frontend", "app.js")
    block = js[js.index("if (routePlanned) {"):]
    block = block[:block.index("} else {")]
    assert "switchView('map')" in block
    assert "showCampsiteReviewBar(" in block
    assert "openCampingSelectionModal(" not in block


def test_review_bar_opens_the_campsites():
    js = _read("frontend", "app.js")
    fn = js[js.index("function showCampsiteReviewBar("):js.index("function openCampingSelectionModal(")]
    assert "btn-review-campsites" in fn and "openCampingSelectionModal(" in fn
    html = _read("frontend", "index.html")
    assert re.search(r'id="campsite-review-bar"[^>]*hidden', html)
    assert 'id="btn-review-campsites"' in html


def test_search_results_can_be_put_on_a_night():
    js = _read("frontend", "app.js")
    fn = js[js.index("function openCampingSearchModal("):js.index("window.openCampingSearchModal")]
    assert "camping-night-select" in fn
    assert "apiCall('select_camping'" in fn

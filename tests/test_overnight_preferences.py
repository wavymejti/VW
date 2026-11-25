"""
Overnight surroundings ("on day 2 I want to sleep by a lake") — Nov 2026.

Regression: modify_route got preferred_overnight="Day 2 overnight near a lake",
which the planner never read, so the change was refused.
"""

from unittest.mock import MagicMock

import pytest

import tools.maps_client as mc
import tools.plan_route as pr

POZNAN = {"label": "Poznań", "lat": 52.4064, "lng": 16.9252}
PARIS = {"label": "Paris", "lat": 48.8566, "lng": 2.3522}


def test_setting_for_day_prefers_day_specific_entry():
    prefs = [{"setting": "in a forest"}, {"setting": "by a lake", "day_number": 2}]
    assert pr._overnight_setting_for_day(prefs, 2) == "by a lake"
    assert pr._overnight_setting_for_day(prefs, 1) == "in a forest"
    assert pr._overnight_setting_for_day(None, 1) is None
    assert pr._overnight_setting_for_day(["by the sea"], 3) == "by the sea"


@pytest.fixture
def planner(monkeypatch):
    client = MagicMock()

    def directions(origin, destination, **kwargs):
        if kwargs.get("departure_time") == "now":
            steps = []
            for i in range(1, 9):
                f = i / 8
                steps.append({"duration": {"value": 6000}, "distance": {"value": 165000},
                              "end_location": {"lat": POZNAN["lat"] + (PARIS["lat"] - POZNAN["lat"]) * f,
                                               "lng": POZNAN["lng"] + (PARIS["lng"] - POZNAN["lng"]) * f}})
            return [{"legs": [{"distance": {"value": 1320000}, "duration": {"value": 48000},
                               "steps": steps}], "overview_polyline": {"points": ""}}]
        return [{"legs": [{"distance": {"value": 300000}, "duration": {"value": 12000}}],
                 "overview_polyline": {"points": ""}, "waypoint_order": []}]

    client.directions.side_effect = directions
    monkeypatch.setattr(pr, "get_maps_client", lambda: client)
    monkeypatch.setattr(pr, "get_weather_forecast", lambda *a, **k: {"status": "error"})
    monkeypatch.setattr(pr, "search_campings", lambda lat, lng, **k: {
        "status": "success", "results": [{"name": "Regular Camp", "lat": lat, "lng": lng}]})
    monkeypatch.setattr(mc, "maps_allows", lambda feature: feature != "places_rich")
    return client


def _lake_search(found=True):
    queries = []

    def text_search(query, lat=None, lng=None, radius_m=None, max_results=5):
        queries.append(query)
        if not found:
            return {"results": []}
        return {"results": [
            {"name": "Lake Viewpoint", "types": ["tourist_attraction"],  # not a campsite
             "geometry": {"location": {"lat": lat + 0.01, "lng": lng}}},
            {"name": "Seecamping Blauer See", "types": ["campground"], "place_id": "lake1",
             "geometry": {"location": {"lat": lat + 0.1, "lng": lng}}},
            {"name": "Far Lake Camping", "types": ["campground"],
             "geometry": {"location": {"lat": lat + 2, "lng": lng}}},  # > 50 km
        ]}

    return text_search, queries


def test_day_two_lake_campsite(planner, monkeypatch):
    search, queries = _lake_search()
    monkeypatch.setattr(mc, "places_text_basic", search)
    result = pr.plan_route(POZNAN, PARIS, num_days=4, start_date="2026-11-19",
                           overnight_preferences=[{"day_number": 2, "setting": "by a lake"}])
    days = result["daily_schedules"]
    assert days[1]["overnight_camping"]["name"] == "Seecamping Blauer See"
    assert days[0]["overnight_camping"]["name"] == "Regular Camp"
    assert days[2]["overnight_camping"]["name"] == "Regular Camp"
    assert queries == ["campsite by a lake"]
    assert result["warnings"] == []


def test_no_lake_campsite_falls_back_with_warning(planner, monkeypatch):
    search, _ = _lake_search(found=False)
    monkeypatch.setattr(mc, "places_text_basic", search)
    result = pr.plan_route(POZNAN, PARIS, num_days=4, start_date="2026-11-19",
                           overnight_preferences=[{"day_number": 2, "setting": "by a lake"}])
    assert result["daily_schedules"][1]["overnight_camping"]["name"] == "Regular Camp"
    assert any("by a lake" in w for w in result["warnings"])


def test_modify_route_accepts_lake_preference(monkeypatch):
    from navigation import dispatcher
    captured = {}
    monkeypatch.setattr(dispatcher, "plan_route", lambda **k: captured.update(k) or {"status": "success"})
    dispatcher.dispatch("modify_route", {
        "origin": POZNAN, "destination": PARIS, "num_days": 4, "start_date": "2099-01-01",
        "overnight_preferences": [{"day_number": 2, "setting": "by a lake"}]})
    assert captured["overnight_preferences"] == [{"day_number": 2, "setting": "by a lake"}]


def test_legacy_preferred_overnight_is_no_longer_refused(monkeypatch):
    from navigation import dispatcher
    captured = {}
    monkeypatch.setattr(dispatcher, "plan_route", lambda **k: captured.update(k) or {"status": "success"})
    result = dispatcher.dispatch("modify_route", {
        "origin": POZNAN, "destination": PARIS, "num_days": 4, "start_date": "2099-01-01",
        "preferred_overnight": "near a lake"})
    assert result["status"] == "success"
    assert captured["overnight_preferences"] == [{"setting": "near a lake"}]


def test_schema_has_overnight_preferences():
    from navigation.dispatcher import OPENAI_TOOL_DEFINITIONS
    tools = {t["function"]["name"]: t["function"] for t in OPENAI_TOOL_DEFINITIONS}
    for name in ("plan_route", "modify_route"):
        assert "overnight_preferences" in tools[name]["parameters"]["properties"]

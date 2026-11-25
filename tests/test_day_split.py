"""
Even day split and daily km limit (Nov 2026 fix).

Regression: Poznań → Paris in 4 days came out as 734 / 131 / 211 / 287 km, because
day ends could only fall at the end of a Directions step and one motorway step
lasted hours. "Max 500 km a day" went into free-text notes the planner never read.
"""

from unittest.mock import MagicMock

import pytest
from googlemaps.convert import encode_polyline

import tools.plan_route as pr
from tools.plan_route import _interpolate_stops_along_route, _haversine_distance

POZNAN = {"label": "Poznań", "lat": 52.4064, "lng": 16.9252}
PARIS = {"label": "Paris", "lat": 48.8566, "lng": 2.3522}


def _line(a, b, n=50):
    return [{"lat": a["lat"] + (b["lat"] - a["lat"]) * i / n,
             "lng": a["lng"] + (b["lng"] - a["lng"]) * i / n} for i in range(n + 1)]


def _route_with_one_huge_step():
    """A short city step, then a single 12 h / 1300 km motorway step to Paris."""
    near = {"lat": 52.40, "lng": 16.80}
    steps = [
        {"duration": {"value": 600}, "distance": {"value": 10000},
         "start_location": POZNAN, "end_location": near,
         "polyline": {"points": encode_polyline(_line(POZNAN, near, 2))}},
        {"duration": {"value": 12 * 3600}, "distance": {"value": 1_300_000},
         "start_location": near, "end_location": PARIS,
         "polyline": {"points": encode_polyline(_line(near, PARIS))}},
    ]
    return [{"distance": {"value": 1_310_000}, "duration": {"value": 12 * 3600 + 600},
             "steps": steps}]


def _km_from(a, p):
    return _haversine_distance(a["lat"], a["lng"], p["lat"], p["lng"])


def test_cuts_fall_inside_a_long_step_and_days_are_even():
    legs = _route_with_one_huge_step()
    pts = _interpolate_stops_along_route(legs, 12 * 3600 + 600, 4, POZNAN, PARIS)
    assert len(pts) == 3
    chain = [POZNAN, *pts, PARIS]
    day_km = [_km_from(a, b) for a, b in zip(chain, chain[1:])]
    assert max(day_km) - min(day_km) < 0.15 * max(day_km), day_km


def test_distance_metric_splits_by_km():
    legs = _route_with_one_huge_step()
    pts = _interpolate_stops_along_route(legs, 0, 3, POZNAN, PARIS, metric="distance")
    assert len(pts) == 3 - 1
    chain = [POZNAN, *pts, PARIS]
    day_km = [_km_from(a, b) for a, b in zip(chain, chain[1:])]
    assert max(day_km) - min(day_km) < 0.15 * max(day_km), day_km


@pytest.fixture
def planner(monkeypatch):
    client = MagicMock()

    def directions(origin, destination, **kwargs):
        if kwargs.get("departure_time") == "now":  # total route
            return [{"legs": _route_with_one_huge_step(), "overview_polyline": {"points": ""}}]
        o = [float(x) for x in origin.split(",")]
        d = [float(x) for x in destination.split(",")]
        km = _haversine_distance(o[0], o[1], d[0], d[1]) * 1.2
        return [{"legs": [{"distance": {"value": km * 1000}, "duration": {"value": km * 36}}],
                 "overview_polyline": {"points": ""}, "waypoint_order": []}]

    client.directions.side_effect = directions
    monkeypatch.setattr(pr, "get_maps_client", lambda: client)
    monkeypatch.setattr(pr, "get_weather_forecast", lambda *a, **k: {"status": "error"})
    monkeypatch.setattr(pr, "search_campings", lambda lat, lng, **k: {
        "status": "success", "results": [{"name": "Camp", "lat": lat, "lng": lng}]})


def test_max_daily_km_adds_days_and_warns(planner):
    result = pr.plan_route(POZNAN, PARIS, num_days=2, start_date="2026-11-19",
                           max_daily_km=400, max_daily_drive_hours=10)
    assert result["status"] == "success"
    assert result["num_days"] == 4  # 1310 km / 400 km
    assert any("num_days raised" in w for w in result["warnings"])
    assert all(d["driving_km"] <= 400 * 1.1 for d in result["daily_schedules"])


def test_four_days_poznan_paris_are_balanced(planner):
    result = pr.plan_route(POZNAN, PARIS, num_days=4, start_date="2026-11-19")
    kms = [d["driving_km"] for d in result["daily_schedules"]]
    assert max(kms) < 1.3 * min(kms), kms


def test_modify_route_with_only_notes_does_not_replan(monkeypatch):
    from navigation import dispatcher
    called = []
    monkeypatch.setattr(dispatcher, "plan_route", lambda **k: called.append(k) or {"status": "success"})
    result = dispatcher.dispatch("modify_route", {
        "trip_id": "t1", "notes": "max 500 km per day", "user_id": "u1"})
    assert result["status"] == "error"
    assert "max_daily_km" in result["message"]
    assert called == []


def test_modify_route_passes_max_daily_km(monkeypatch):
    from navigation import dispatcher
    captured = {}
    monkeypatch.setattr(dispatcher, "plan_route", lambda **k: captured.update(k) or {"status": "success"})
    dispatcher.dispatch("modify_route", {
        "origin": POZNAN, "destination": PARIS, "num_days": 4,
        "start_date": "2099-01-01", "max_daily_km": 400})
    assert captured["max_daily_km"] == 400


def test_schema_has_max_daily_km():
    from navigation.dispatcher import OPENAI_TOOL_DEFINITIONS
    tools = {t["function"]["name"]: t["function"] for t in OPENAI_TOOL_DEFINITIONS}
    for name in ("plan_route", "modify_route"):
        assert "max_daily_km" in tools[name]["parameters"]["properties"]

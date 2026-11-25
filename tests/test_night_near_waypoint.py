"""
A place to visit near where a day would end becomes that night's place (Nov 2026).

Regression: "visit a lake in Austria" added Wolfgangsee as a waypoint, the day was split
by driving time and the night landed in Teisendorf, ~50 km further on, while the reply said
"overnight near Wolfgangsee". Google Maps, campsites and weather are mocked.
"""

from unittest.mock import MagicMock

import pytest

import tools.plan_route as pr

POZNAN = {"label": "Poznań", "lat": 52.4084, "lng": 16.9342}
BERLIN = {"label": "Berlin", "lat": 52.52, "lng": 13.405}
MID = {"lat": (POZNAN["lat"] + BERLIN["lat"]) / 2, "lng": (POZNAN["lng"] + BERLIN["lng"]) / 2}


def _directions(*args, **kwargs):
    steps = []
    for i in range(1, 5):
        f = i / 4
        steps.append({
            "duration": {"value": 1800},
            "distance": {"value": 70000},
            "end_location": {
                "lat": POZNAN["lat"] + (BERLIN["lat"] - POZNAN["lat"]) * f,
                "lng": POZNAN["lng"] + (BERLIN["lng"] - POZNAN["lng"]) * f,
            },
        })
    return [{
        "legs": [{"distance": {"value": 280000}, "duration": {"value": 7200}, "steps": steps}],
        "overview_polyline": {"points": "abc"},
        "waypoint_order": list(range(len(kwargs.get("waypoints") or []))),
    }]


@pytest.fixture
def planner(monkeypatch):
    client = MagicMock()
    client.directions.side_effect = _directions
    client.geocode.return_value = []
    monkeypatch.setattr(pr, "get_maps_client", lambda: client)
    monkeypatch.setattr(pr, "get_weather_forecast", lambda *a, **k: {"status": "error"})
    searched = []

    def search(lat, lng, radius_km=30, **kwargs):
        searched.append((lat, lng))
        return {"status": "success", "results": [
            {"name": f"Camp {lat:.3f},{lng:.3f}", "lat": lat + 0.01, "lng": lng, "place_id": "c"}]}

    monkeypatch.setattr(pr, "search_campings", search)
    return searched


def test_night_moves_to_a_nearby_waypoint(planner):
    lake = {"label": "Lake near the day end", "lat": MID["lat"] + 0.05, "lng": MID["lng"] + 0.35}
    assert 15 < pr._haversine_distance(MID["lat"], MID["lng"], lake["lat"], lake["lng"]) < 35
    result = pr.plan_route(POZNAN, BERLIN, num_days=2, start_date="2027-05-10", waypoints=[lake])
    assert result["status"] == "success"
    day1 = result["daily_schedules"][0]
    assert day1["night_near"] == "Lake near the day end"
    assert planner[0] == (lake["lat"], lake["lng"])            # campsites searched at the lake
    assert [w["type"] for w in day1["waypoints"]] == ["start", "attraction", "camping"]
    assert day1["campsite_km_from_stops"][0]["km"] < 5


def test_far_waypoint_keeps_the_normal_split(planner):
    far = {"label": "Far place", "lat": MID["lat"], "lng": MID["lng"] + 1.2}   # ~80 km
    result = pr.plan_route(POZNAN, BERLIN, num_days=2, start_date="2027-05-10", waypoints=[far])
    day1 = result["daily_schedules"][0]
    assert "night_near" not in day1
    assert abs(planner[0][1] - MID["lng"]) < 0.2


def test_requested_overnight_is_never_moved():
    pts = [{"label": "Frankfurt", "lat": 52.35, "lng": 14.55, "requested_overnight": True}]
    wp = [{"label": "Słubice", "lat": 52.35, "lng": 14.56}]
    assert pr._snap_day_ends_to_waypoints(pts, wp, 300)[0]["label"] == "Frankfurt"


def test_each_waypoint_takes_one_night():
    pts = [{"label": "a", "lat": 50.0, "lng": 10.0}, {"label": "b", "lat": 50.0, "lng": 10.1}]
    wp = [{"label": "W", "lat": 50.0, "lng": 10.05}]
    out = pr._snap_day_ends_to_waypoints(pts, wp, 400)
    assert [p["label"] for p in out] == ["W", "b"]

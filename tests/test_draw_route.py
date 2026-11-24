"""
A route drawn with a finger on the map (touch screens, Nov 2026 tests).

The drawn line becomes pass-through points ("via:"), not stops: they shape the route and
each day's directions, are kept on the day for recalculations, and never get a marker.
"""

import os
from datetime import date
from unittest.mock import MagicMock

import pytest

import tools.plan_route as pr
from navigation.plan_form import form_to_plan_args, FormError

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
POZNAN = {"label": "Poznań", "lat": 52.4084, "lng": 16.9342}
SALZBURG = {"label": "Salzburg", "lat": 47.8095, "lng": 13.0550}
VIA = [{"lat": 50.0755, "lng": 14.4378}, {"lat": 48.3069, "lng": 14.2858}]   # Prague, Linz
TODAY = date(2026, 11, 24)


def _pt(v):
    if isinstance(v, str):
        lat, lng = v.replace("via:", "").split(",")
        return float(lat), float(lng)
    return v["lat"], v["lng"]


def _directions(*args, **kwargs):
    pts = [_pt(kwargs["origin"]), *[_pt(w) for w in kwargs.get("waypoints") or []],
           _pt(kwargs["destination"])]
    steps, total = [], 0
    for (a_lat, a_lng), (b_lat, b_lng) in zip(pts, pts[1:]):
        d = pr._haversine_distance(a_lat, a_lng, b_lat, b_lng)
        n = max(1, int(d // 25))
        for i in range(1, n + 1):
            f = i / n
            steps.append({"duration": {"value": int(d / n * 36)}, "distance": {"value": int(d / n * 1000)},
                          "end_location": {"lat": a_lat + (b_lat - a_lat) * f, "lng": a_lng + (b_lng - a_lng) * f}})
        total += d
    stopovers = [w for w in kwargs.get("waypoints") or [] if not str(w).startswith("via:")]
    return [{"legs": [{"distance": {"value": int(total * 1000)}, "duration": {"value": int(total * 36)},
                       "steps": steps}],
             "overview_polyline": {"points": "abc"},
             "waypoint_order": list(range(len(stopovers)))}]


@pytest.fixture
def maps(monkeypatch):
    client = MagicMock()
    client.directions.side_effect = _directions
    client.geocode.return_value = []
    monkeypatch.setattr(pr, "get_maps_client", lambda: client)
    monkeypatch.setattr(pr, "get_weather_forecast", lambda *a, **k: {"status": "error"})
    monkeypatch.setattr(pr, "search_campings", lambda lat, lng, **k: {"status": "success", "results": [
        {"name": "Camp", "lat": lat, "lng": lng, "place_id": "c"}]})
    return client


def test_form_for_a_drawn_route():
    args, summary = form_to_plan_args({"mode": "drawn", "origin": POZNAN, "destination": SALZBURG,
                                       "via_points": VIA + [{"lat": "x"}]}, today=TODAY)
    assert args["via_points"] == VIA
    assert "along the route drawn on the map" in summary
    with pytest.raises(FormError):
        form_to_plan_args({"mode": "drawn", "origin": {"label": "Poznań"}, "destination": SALZBURG},
                          today=TODAY)


def test_drawn_points_shape_the_route_without_stops(maps):
    result = pr.plan_route(POZNAN, SALZBURG, num_days=2, start_date="2027-05-10", via_points=VIA)
    assert result["status"] == "success", result
    total = maps.directions.call_args_list[0].kwargs
    assert total["waypoints"] == [f"via:{p['lat']},{p['lng']}" for p in VIA]
    assert total["optimize_waypoints"] is False

    day_calls = [c.kwargs for c in maps.directions.call_args_list[1:]]
    sent = [w for c in day_calls for w in c.get("waypoints") or []]
    assert all(w.startswith("via:") for w in sent) and sent      # passed through, in order
    assert not any(c.get("optimize_waypoints") for c in day_calls if c.get("waypoints"))

    types = [w["type"] for d in result["daily_schedules"] for w in d["waypoints"]]
    assert "attraction" not in types and "via" in types
    for d in result["daily_schedules"]:
        assert d["waypoints"][0]["type"] == "start"
        assert d["waypoints"][-1]["type"] in ("camping", "end")


def test_recalculating_a_day_keeps_the_drawing(monkeypatch):
    from navigation import dispatcher
    client = MagicMock()
    client.directions.side_effect = _directions
    monkeypatch.setattr("tools.maps_client.get_client", lambda: client)
    conn = MagicMock()
    wps = [{"type": "start", "lat": 52.4, "lng": 16.9}, {"type": "via", "lat": 50.07, "lng": 14.43},
           {"type": "camping", "lat": 48.3, "lng": 14.28}]
    assert dispatcher._recalculate_day_route(conn, "sid", wps)
    kwargs = client.directions.call_args.kwargs
    assert kwargs["waypoints"] == ["via:50.07,14.43"] and "optimize_waypoints" not in kwargs


def test_drawing_ui_is_touch_only():
    with open(os.path.join(ROOT, "frontend", "app.js"), encoding="utf-8") as f:
        js = f.read()
    assert "pointerType" in js and "any-pointer: coarse" in js
    assert "if (wp.type === 'via') return;" in js

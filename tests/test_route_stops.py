"""
Fuel, EV charging and lunch stops along the route (Nov 2026).

Places come from Google Places (basic fields only); here it is mocked.
"""

import math

import pytest
from googlemaps.convert import encode_polyline

import tools.route_stops as rs
from tools import google_stops
from navigation.route_stop_add import insert_in_order, stop_waypoint


def _line_km(start, km, bearing_lng=True, n=200):
    """Polyline of `km` going east from `start` (lat, lng)."""
    lat, lng = start
    dlng = km / (111.32 * math.cos(math.radians(lat)))
    return encode_polyline([{"lat": lat, "lng": lng + dlng * i / n} for i in range(n + 1)])


@pytest.fixture(autouse=True)
def _google_on(monkeypatch):
    """Google counts as configured; every test mocks find_places or requests.post itself."""
    monkeypatch.setattr(google_stops, "available", lambda: True)
    google_stops._cache.clear()


def _trip():
    return [
        {"day_number": 1, "date": "2027-05-10", "driving_hours": 6.0, "route_polyline": _line_km((50.0, 5.0), 500),
         "waypoints": [{"type": "start"}, {"type": "camping"}]},
        {"day_number": 2, "date": "2027-05-11", "driving_hours": 5.5, "route_polyline": _line_km((50.0, 12.0), 450),
         "waypoints": [{"type": "start"}, {"type": "camping"}]},
        {"day_number": 3, "date": "2027-05-12", "route_polyline": None, "waypoints": [{"type": "stay"}]},
    ]


def test_fuel_when_a_quarter_of_the_tank_is_left_carrying_over_days():
    t = rs.find_targets(_trip(), "fuel", "diesel")
    assert [x["day_number"] for x in t] == [2]
    assert abs(t[0]["km"] - 100) < 3            # 500 km on day 1 + 100 km = 600 of 800
    assert t[0]["reason"].startswith("about 25%")


def test_ev_charging_every_morning_full_then_to_80_percent():
    t = rs.find_targets(_trip(), "ev_charging", "ev")
    assert [x["day_number"] for x in t] == [1, 2]
    assert all(abs(x["km"] - 304) < 1 for x in t)


def test_lunch_where_the_clock_says_quarter_to_one():
    t = rs.find_targets(_trip(), "restaurant", departure="09:00")
    assert [x["day_number"] for x in t] == [1, 2]
    assert t[0]["eta"] == "12:45"
    assert t[0]["after_driving"] == "3 h 30 min"        # 3 h 30 min driving + one 15 min break


def test_no_lunch_on_a_short_morning_day():
    short = [{"day_number": 1, "driving_hours": 2.0, "route_polyline": _line_km((50.0, 5.0), 150),
              "waypoints": [{"type": "start"}, {"type": "camping"}]}]
    res = rs.plan_route_stops(short, "restaurant")
    assert res["targets"] == [] and "before lunchtime" in res["message"]


def test_candidates_nearest_to_the_route_first(monkeypatch):
    calls = []

    def fake_find(kind, points, radius_m=5000):
        calls.append((kind, len(points), radius_m))
        p = points[0]
        return [
            {"place_id": "p1", "name": "Far Diner", "lat": p["lat"] + 0.04, "lng": p["lng"], "kind": kind},
            {"place_id": "p2", "name": "Roadside Grill", "lat": p["lat"] + 0.005, "lng": p["lng"], "kind": kind},
        ]

    monkeypatch.setattr(google_stops, "find_places", fake_find)
    res = rs.plan_route_stops(_trip(), "restaurant", day_number=1)
    assert res["status"] == "success"
    assert calls == [("restaurant", 1, 5000)]                     # one query for all targets
    names = [c["name"] for c in res["targets"][0]["candidates"]]
    assert names == ["Roadside Grill", "Far Diner"]
    assert res["targets"][0]["candidates"][0]["off_route_km"] <= 1.0


def test_google_down_is_an_error_message(monkeypatch):
    def down(*a, **k):
        raise google_stops.GooglePlacesError("Google Places 503: unavailable")
    monkeypatch.setattr(google_stops, "find_places", down)
    res = rs.plan_route_stops(_trip(), "fuel")
    assert res["status"] == "error" and "not available right now" in res["message"]


def test_no_google_key_is_an_error_message(monkeypatch):
    monkeypatch.setattr(google_stops, "available", lambda: False)
    res = rs.plan_route_stops(_trip(), "fuel")
    assert res["status"] == "error" and "GOOGLE_MAPS_API_KEY" in res["message"]


def test_stop_goes_in_route_order():
    poly = _line_km((50.0, 5.0), 300)
    start = {"type": "start", "lat": 50.0, "lng": 5.0}
    end = {"type": "camping", "lat": 50.0, "lng": 9.2}
    castle = {"type": "attraction", "label": "Castle", "lat": 50.0, "lng": 8.0}
    fuel = stop_waypoint({"name": "Aral", "lat": 50.0, "lng": 6.0, "place_id": "p3"}, "fuel", "10:30")
    wps = insert_in_order([start, castle, end], fuel, poly)
    assert [w.get("label") or w["type"] for w in wps] == ["start", "Aral", "Castle", "camping"]
    assert fuel["emoji"] == "⛽" and fuel["category_label"] == "Fuel stop · ~10:30"


def test_chat_tool_uses_the_route_planned_in_the_chat(monkeypatch):
    """Unsaved trip: find_route_stops falls back to the rows kept in the chat session."""
    from navigation import chat_handler as ch, dispatcher
    from types import SimpleNamespace
    import json as _json

    monkeypatch.setattr(google_stops, "find_places", lambda kind, points, radius_m=5000: [
        {"place_id": "p9", "name": "Aral", "lat": points[0]["lat"], "lng": points[0]["lng"], "kind": kind}])
    monkeypatch.setattr("tools.trip_store.get_trip_data", lambda tid: None)
    rows = [(d["day_number"], d["waypoints"], d["route_polyline"]) for d in _trip()]
    session = {"history": [], "active_trip_id": "anon-trip", "last_trip_rows": rows, "lang": "en"}
    call = SimpleNamespace(id="c1", function=SimpleNamespace(name="find_route_stops",
                                                             arguments=_json.dumps({"kind": "fuel"})))
    out = []
    ch._run_tool(session, call, out)
    res = out[0]["result"]
    assert res["status"] == "success" and res["saved_trip"] is False
    assert res["targets"][0]["candidates"][0]["name"] == "Aral"
    assert "find_route_stops" in [t["function"]["name"] for t in dispatcher.OPENAI_TOOL_DEFINITIONS]


def test_google_places_basic_fields_only_and_closed_dropped(monkeypatch):
    sent = {}

    class Resp:
        status_code = 200
        content = b"x"

        def json(self):
            return {"places": [
                {"id": "a", "displayName": {"text": "Orlen"}, "location": {"latitude": 52.0, "longitude": 16.0},
                 "types": ["gas_station"], "businessStatus": "OPERATIONAL", "shortFormattedAddress": "A2"},
                {"id": "c", "displayName": {"text": "Reifen Luftdruck"}, "primaryType": "car_repair",
                 "location": {"latitude": 52.0, "longitude": 16.0}, "types": ["car_repair", "gas_station"]},
                {"id": "b", "displayName": {"text": "Old BP"}, "location": {"latitude": 52.0, "longitude": 16.01},
                 "types": ["gas_station"], "businessStatus": "CLOSED_PERMANENTLY"},
            ]}

    def fake_post(url, json=None, headers=None, timeout=None):
        sent["mask"] = headers["X-Goog-FieldMask"]
        sent["body"] = json
        return Resp()

    monkeypatch.setattr(google_stops.requests, "post", fake_post)
    places = google_stops.find_places("fuel", [{"lat": 52.0, "lng": 16.0}])
    assert [p["name"] for p in places] == ["Orlen"]
    assert places[0]["place_id"] == "a" and places[0]["address"] == "A2"
    for expensive in ("rating", "OpeningHours", "priceLevel", "evChargeOptions", "fuelOptions", "photos", "reviews"):
        assert expensive not in sent["mask"]
    assert sent["body"]["includedTypes"] == ["gas_station"] and sent["body"]["rankPreference"] == "DISTANCE"


def test_no_lunch_when_the_day_ends_right_at_lunchtime():
    day = [{"day_number": 1, "driving_hours": 3.5, "route_polyline": _line_km((50.0, 5.0), 280),
            "waypoints": [{"type": "start"}, {"type": "camping"}]}]
    assert rs.find_targets(day, "restaurant", departure="09:00") == []


def test_restaurant_main_types_are_kept():
    fits = google_stops._main_type_fits
    assert fits("restaurant", "german_restaurant") and fits("restaurant", "pub") and fits("restaurant", None)
    assert not fits("restaurant", "gas_station")
    assert fits("fuel", "gas_station") and not fits("fuel", "car_repair")


def test_one_place_per_station_keeps_the_station():
    pump = {"name": "Reifen Luftdruck & Staubsauger", "address": "Brockhagener Str. 123", "lat": 52.0, "lng": 8.3}
    avia = {"name": "Avia Fuel Station", "address": "Brockhagener Str. 123", "lat": 52.0, "lng": 8.3}
    other = {"name": "Westfalen", "address": "Hauptstr. 1", "lat": 52.01, "lng": 8.3}
    kept = google_stops._one_per_address([pump, avia, other], "fuel")
    assert [p["name"] for p in kept] == ["Avia Fuel Station", "Westfalen"]
    assert google_stops._one_per_address([pump, avia], "restaurant") == [pump, avia]

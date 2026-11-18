"""
Stay days and rest days (Nov 2026).

Before: every day was a driving day, so "14 days to Dubrovnik and back with a week
there" became 14 short driving days. Now stays / rest days are carved out of num_days.
"""

from unittest.mock import MagicMock

import pytest

import tools.plan_route as pr

POZNAN = {"label": "Poznań", "lat": 52.4064, "lng": 16.9252}
PARIS = {"label": "Paris", "lat": 48.8566, "lng": 2.3522}
DUBROVNIK = {"label": "Dubrovnik", "lat": 42.6507, "lng": 18.0944}
VIENNA = {"label": "Vienna", "lat": 48.2082, "lng": 16.3738}


def _steps(a, b, n=12, secs=3600):
    out = []
    for i in range(1, n + 1):
        f = i / n
        out.append({"duration": {"value": secs}, "distance": {"value": 100000},
                    "end_location": {"lat": a["lat"] + (b["lat"] - a["lat"]) * f,
                                     "lng": a["lng"] + (b["lng"] - a["lng"]) * f}})
    return out


@pytest.fixture
def planner(monkeypatch):
    client = MagicMock()

    def directions(origin, destination, **kwargs):
        if kwargs.get("departure_time") == "now":
            o = dict(zip(("lat", "lng"), map(float, origin.split(","))))
            d = dict(zip(("lat", "lng"), map(float, destination.split(","))))
            wps = kwargs.get("waypoints") or []
            if wps:  # round trip via the turnaround point
                t = dict(zip(("lat", "lng"), map(float, wps[-1].split(","))))
                legs = [{"distance": {"value": 1200000}, "duration": {"value": 43200}, "steps": _steps(o, t)},
                        {"distance": {"value": 1200000}, "duration": {"value": 43200}, "steps": _steps(t, d)}]
            else:
                legs = [{"distance": {"value": 1200000}, "duration": {"value": 43200}, "steps": _steps(o, d)}]
            return [{"legs": legs, "overview_polyline": {"points": ""}}]
        return [{"legs": [{"distance": {"value": 300000}, "duration": {"value": 10800}}],
                 "overview_polyline": {"points": "x"}, "waypoint_order": []}]

    def geocode(label):
        known = {"Vienna": VIENNA, "Paris": PARIS, "Dubrovnik": DUBROVNIK}
        p = known.get(label)
        return [{"geometry": {"location": {"lat": p["lat"], "lng": p["lng"]}}}] if p else []

    client.directions.side_effect = directions
    client.geocode.side_effect = geocode
    monkeypatch.setattr(pr, "get_maps_client", lambda: client)
    monkeypatch.setattr(pr, "get_weather_forecast", lambda *a, **k: {"status": "error"})
    monkeypatch.setattr(pr, "search_campings", lambda lat, lng, **k: {
        "status": "success",
        "results": [{"name": f"Camp {lat:.2f},{lng:.2f}", "lat": lat, "lng": lng, "place_id": "c"}]})


def _kinds(result):
    return ["drive" if not d.get("stay") else d["stay_kind"] for d in result["daily_schedules"]]


def test_one_way_with_two_days_at_destination(planner):
    r = pr.plan_route(POZNAN, PARIS, num_days=4, start_date="2026-11-19",
                      stays=[{"label": "Paris", "days": 2}])
    assert r["status"] == "success"
    assert _kinds(r) == ["drive", "drive", "stay", "stay"]
    days = r["daily_schedules"]
    assert [d["day_number"] for d in days] == [1, 2, 3, 4]
    assert [d["date"] for d in days] == ["2026-11-19", "2026-11-20", "2026-11-21", "2026-11-22"]
    arrival_camp = days[1]["overnight_camping"]
    assert arrival_camp is not None
    assert pr._haversine_distance(arrival_camp["lat"], arrival_camp["lng"], PARIS["lat"], PARIS["lng"]) < 1
    assert days[2]["driving_km"] == 0 and days[2]["route_polyline"] is None
    assert days[2]["waypoints"][0]["type"] == "stay"
    assert days[3]["overnight_camping"]["name"] == arrival_camp["name"]
    assert r["driving_days"] == 2 and r["stay_days"] == 2 and r["num_days"] == 4


def test_round_trip_two_weeks_with_a_week_at_the_turnaround(planner):
    r = pr.plan_route(POZNAN, DUBROVNIK, num_days=14, start_date="2026-07-01",
                      round_trip=True, stays=[{"days": 7}], max_daily_drive_hours=10)
    assert r["status"] == "success", r.get("message")
    kinds = _kinds(r)
    assert len(kinds) == 14 and kinds.count("stay") == 7
    first, last = kinds.index("stay"), len(kinds) - 1 - kinds[::-1].index("stay")
    assert last - first == 6  # one block of 7 stay days
    days = r["daily_schedules"]
    stay_place = days[first]["waypoints"][0]
    assert pr._haversine_distance(stay_place["lat"], stay_place["lng"],
                                  DUBROVNIK["lat"], DUBROVNIK["lng"]) < 30
    assert all(not d["is_return"] for d in days[: last + 1])
    assert all(d["is_return"] for d in days[last + 1:])
    assert days[-1]["waypoints"][-1]["type"] == "end"  # back home


def test_rest_day_every_three_driving_days(planner):
    r = pr.plan_route(POZNAN, DUBROVNIK, num_days=8, start_date="2026-07-01",
                      rest_day_every=3, max_daily_drive_hours=12)
    kinds = _kinds(r)
    assert kinds.count("rest") >= 1
    assert kinds[:4] == ["drive", "drive", "drive", "rest"]
    assert len(kinds) <= 8


def test_stay_on_the_way(planner):
    r = pr.plan_route(POZNAN, DUBROVNIK, num_days=5, start_date="2026-07-01",
                      stays=[{"label": "Vienna", "days": 1}], max_daily_drive_hours=12)
    kinds = _kinds(r)
    assert kinds.count("stay") == 1 and len(kinds) == 5
    stay = r["daily_schedules"][kinds.index("stay")]["waypoints"][0]
    assert pr._haversine_distance(stay["lat"], stay["lng"], VIENNA["lat"], VIENNA["lng"]) < 1


def test_too_few_days_get_a_warning(planner):
    r = pr.plan_route(POZNAN, PARIS, num_days=2, start_date="2026-11-19",
                      stays=[{"label": "Paris", "days": 2}], max_daily_drive_hours=12)
    assert _kinds(r) == ["drive", "stay", "stay"]
    assert any("instead of 2" in w for w in r["warnings"])


def test_existing_stays_are_rebuilt_for_modify_route():
    from navigation.dispatcher import _existing_stays
    drive = [{"type": "start"}, {"type": "camping"}]
    stay = lambda kind, lat: [{"type": "stay", "stay_kind": kind, "label": "C", "lat": lat, "lng": 18.09}]
    rows = [(1, drive), (2, drive), (3, drive), (4, stay("rest", 45.0)), (5, drive),
            (6, stay("stay", 42.65)), (7, stay("stay", 42.65)), (8, drive)]
    stays, rest_every = _existing_stays(rows, DUBROVNIK)
    assert stays == [{"days": 2}]          # at the destination -> no label
    assert rest_every == 3


def test_modify_route_passes_stays(monkeypatch):
    from navigation import dispatcher
    captured = {}
    monkeypatch.setattr(dispatcher, "plan_route", lambda **k: captured.update(k) or {"status": "success"})
    dispatcher.dispatch("modify_route", {
        "origin": POZNAN, "destination": PARIS, "num_days": 6, "start_date": "2099-01-01",
        "stays": [{"label": "Paris", "days": 2}], "rest_day_every": 2})
    assert captured["stays"] == [{"label": "Paris", "days": 2}]
    assert captured["rest_day_every"] == 2


def test_schema_documents_stays():
    from navigation.dispatcher import OPENAI_TOOL_DEFINITIONS
    tools = {t["function"]["name"]: t["function"] for t in OPENAI_TOOL_DEFINITIONS}
    for name in ("plan_route", "modify_route"):
        props = tools[name]["parameters"]["properties"]
        assert "stays" in props and "rest_day_every" in props
        assert "INTO num_days" in props["stays"]["description"]


def test_rest_days_never_shorten_the_requested_trip(planner):
    """Dubrovnik live case: 14 days, a week there, model adds rest_day_every=3 -> still 14."""
    r = pr.plan_route(POZNAN, DUBROVNIK, num_days=14, start_date="2027-07-01",
                      round_trip=True, stays=[{"days": 7}], rest_day_every=3,
                      max_daily_drive_hours=10)
    assert r["num_days"] == 14, r["warnings"]
    assert _kinds(r).count("stay") == 7
    assert not any("instead of" in w for w in r["warnings"])


def test_rest_days_fit_into_the_requested_days(planner):
    r = pr.plan_route(POZNAN, DUBROVNIK, num_days=8, start_date="2027-07-01",
                      rest_day_every=3, max_daily_drive_hours=12)
    assert _kinds(r) == ["drive", "drive", "drive", "rest", "drive", "drive", "drive", "drive"]


def test_pick_campsite_skips_offices_and_prefers_campsites_for_stays():
    office = {"name": "Vacances André Trigano - siège social", "source": "google_maps"}
    street = {"name": "Dubrovnik, 21 Vukovarska ulica", "source": "park4night", "spot_code": "P"}
    camp = {"name": "Camping Solitudo", "source": "park4night", "spot_code": "C"}
    google_camp = {"name": "Camping Kate", "source": "google_maps"}
    assert pr._pick_campsite([office, google_camp])[0] is google_camp
    assert pr._pick_campsite([street, camp], long_stay=True) == (camp, False)
    assert pr._pick_campsite([street, camp], long_stay=False)[0] is street
    assert pr._pick_campsite([street], long_stay=True) == (street, True)


def test_past_dates_move_to_their_next_occurrence(monkeypatch):
    import datetime as real_dt
    from navigation import dispatcher

    class FakeDT(real_dt.datetime):
        @classmethod
        def now(cls, tz=None):
            return cls(2026, 11, 18, 10, 0)

    monkeypatch.setattr(dispatcher, "datetime", FakeDT)
    f = dispatcher._sanitize_trip_start_date
    assert f("2026-07-01") == "2027-07-01"      # "1 July" asked in November
    assert f("2026-11-16") == "2026-11-18"      # a slip for "today"
    assert f("2023-12-24") == "2026-12-24"      # old model prior
    assert f("2027-03-10") == "2027-03-10"
    assert f(None) == "2026-11-18"

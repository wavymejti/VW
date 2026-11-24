"""
Start form: Direct / Point-to-point / Turnaround (Nov 2026 tests).

Free text wasn't reliably understood for a first route, so the first plan comes from a
form. Google Maps, campsites, weather and the model are mocked.
"""

import json
import math
from datetime import date
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

import tools.plan_route as pr
import navigation.chat_handler as ch
from navigation.plan_form import form_to_plan_args, estimate_days, FormError

POZNAN = {"label": "Poznań", "lat": 52.4084, "lng": 16.9342}
PRAGUE = {"label": "Prague", "lat": 50.0755, "lng": 14.4378}
SALZBURG = {"label": "Salzburg", "lat": 47.8095, "lng": 13.0550}
DRESDEN = {"label": "Dresden", "lat": 51.0504, "lng": 13.7373}
TODAY = date(2026, 11, 24)


# ── form -> plan_route arguments ─────────────────────────────

def test_direct_ignores_stops_and_defaults_to_tomorrow():
    args, summary = form_to_plan_args(
        {"mode": "direct", "origin": POZNAN, "destination": SALZBURG, "num_days": 3,
         "stops": [PRAGUE]}, today=TODAY)
    assert args["start_date"] == "2026-11-25"
    assert args["round_trip"] is False and "route_stops" not in args
    assert summary == "Plan a trip: Poznań → Salzburg (direct), starting 2026-11-25, 3 days."


def test_point_to_point_keeps_order_and_nights():
    args, summary = form_to_plan_args(
        {"mode": "p2p", "origin": POZNAN, "destination": SALZBURG, "start_date": "2027-05-10",
         "stops": [{**PRAGUE, "nights": 2}, {"label": "Linz", "nights": 0}, {"label": ""}]},
        today=TODAY)
    assert [s["label"] for s in args["route_stops"]] == ["Prague", "Linz"]
    assert [s["nights"] for s in args["route_stops"]] == [2, 0]
    assert {s["leg"] for s in args["route_stops"]} == {"out"}
    assert "Poznań → Prague (2 nights) → Linz → Salzburg (point-to-point)" in summary


def test_turnaround_puts_back_stops_after_the_destination():
    args, summary = form_to_plan_args(
        {"mode": "turnaround", "origin": POZNAN, "destination": SALZBURG, "num_days": 7,
         "stops": [{**PRAGUE, "nights": 1}], "back_stops": [{**DRESDEN, "nights": 0}],
         "dest_nights": 3}, today=TODAY)
    assert args["round_trip"] is True
    assert [(s["label"], s["leg"]) for s in args["route_stops"]] == [("Prague", "out"), ("Dresden", "back")]
    assert args["stays"] == [{"label": None, "days": 2}]     # 3 nights = 2 full days
    assert "Prague (1 night) → Salzburg (3 nights) → Dresden → Poznań (turnaround)" in summary


def test_one_night_at_the_turnaround_is_an_overnight_there():
    args, _ = form_to_plan_args(
        {"mode": "turnaround", "origin": POZNAN, "destination": SALZBURG, "num_days": 4,
         "dest_nights": 1}, today=TODAY)
    assert args["route_stops"] == [{**SALZBURG, "nights": 1, "leg": "turn"}]
    assert "stays" not in args


@pytest.mark.parametrize("form, message", [
    ({"mode": "direct", "origin": POZNAN}, "destination"),
    ({"mode": "direct", "destination": SALZBURG}, "starting point"),
    ({"mode": "loop", "origin": POZNAN, "destination": SALZBURG}, "Choose"),
    ({"mode": "direct", "origin": POZNAN, "destination": SALZBURG, "start_date": "2020-01-01"}, "past"),
    ({"mode": "direct", "origin": POZNAN, "destination": SALZBURG, "num_days": 99}, "1 to 60"),
])
def test_bad_forms_say_what_is_missing(form, message):
    with pytest.raises(FormError, match=message):
        form_to_plan_args(form, today=TODAY)


def test_days_are_estimated_when_left_empty():
    args, summary = form_to_plan_args(
        {"mode": "turnaround", "origin": POZNAN, "destination": SALZBURG,
         "stops": [{**PRAGUE, "nights": 1}], "back_stops": [DRESDEN], "dest_nights": 3}, today=TODAY)
    assert args["num_days"] == 6          # 4 driving days (~1390 km) + 2 days in Salzburg
    assert "(estimated)" in summary
    assert estimate_days(POZNAN, SALZBURG, [], False) == 2   # ~670 km one way


# ── planner keeps the user's order ───────────────────────────

def _path_directions(*args, **kwargs):
    """Steps along origin -> waypoints -> destination (straight lines), 1 h per 100 km."""
    def pt(v):
        if isinstance(v, str):
            lat, lng = v.split(",")
            return float(lat), float(lng)
        return v["lat"], v["lng"]
    pts = [pt(kwargs["origin"]), *[pt(w) for w in kwargs.get("waypoints") or []],
           pt(kwargs["destination"])]
    steps, total = [], 0
    for (a_lat, a_lng), (b_lat, b_lng) in zip(pts, pts[1:]):
        d = pr._haversine_distance(a_lat, a_lng, b_lat, b_lng)
        n = max(1, int(d // 25))
        for i in range(1, n + 1):
            f = i / n
            steps.append({"duration": {"value": int(d / n * 36)}, "distance": {"value": int(d / n * 1000)},
                          "end_location": {"lat": a_lat + (b_lat - a_lat) * f, "lng": a_lng + (b_lng - a_lng) * f}})
        total += d
    return [{"legs": [{"distance": {"value": int(total * 1000)}, "duration": {"value": int(total * 36)},
                       "steps": steps}],
             "overview_polyline": {"points": "abc"},
             "waypoint_order": list(range(len(kwargs.get("waypoints") or [])))}]


@pytest.fixture
def maps(monkeypatch):
    client = MagicMock()
    client.directions.side_effect = _path_directions
    client.geocode.return_value = []
    monkeypatch.setattr(pr, "get_maps_client", lambda: client)
    monkeypatch.setattr(pr, "get_weather_forecast", lambda *a, **k: {"status": "error"})
    monkeypatch.setattr(pr, "search_campings", lambda lat, lng, **k: {"status": "success", "results": [
        {"name": f"Camp {lat:.2f},{lng:.2f}", "lat": lat, "lng": lng, "place_id": "c"}]})
    return client


def _day_ends(result):
    return [(d["waypoints"][-1]["lat"], d["waypoints"][-1]["lng"]) for d in result["daily_schedules"]]


def _near(p, place, km=15):
    return pr._haversine_distance(p[0], p[1], place["lat"], place["lng"]) < km


def test_turnaround_route_goes_there_and_back_in_the_given_order(maps):
    args, _ = form_to_plan_args(
        {"mode": "turnaround", "origin": POZNAN, "destination": SALZBURG, "num_days": 6,
         "stops": [{**PRAGUE, "nights": 1}], "back_stops": [{**DRESDEN, "nights": 1}],
         "dest_nights": 2}, today=TODAY)
    result = pr.plan_route(**args)
    assert result["status"] == "success", result
    total_call = maps.directions.call_args_list[0].kwargs
    assert total_call["optimize_waypoints"] is False
    assert total_call["waypoints"] == [
        f"{PRAGUE['lat']},{PRAGUE['lng']}", f"{SALZBURG['lat']},{SALZBURG['lng']}",
        f"{DRESDEN['lat']},{DRESDEN['lng']}"]
    ends = _day_ends(result)
    order = [e for e, d in zip(ends, result["daily_schedules"])
             if d["waypoints"][-1]["type"] in ("camping", "stay")]
    i_prague = next(i for i, e in enumerate(order) if _near(e, PRAGUE))
    i_salz = next(i for i, e in enumerate(order) if _near(e, SALZBURG))
    i_dresden = next(i for i, e in enumerate(order) if _near(e, DRESDEN))
    assert i_prague < i_salz < i_dresden
    assert _near(ends[-1], POZNAN)


def test_point_to_point_is_not_reordered(maps):
    # Dresden is listed after Prague although it is closer to Poznań: the user's order wins.
    args, _ = form_to_plan_args(
        {"mode": "p2p", "origin": POZNAN, "destination": SALZBURG, "num_days": 4,
         "stops": [{**PRAGUE, "nights": 1}, {**DRESDEN, "nights": 1}]}, today=TODAY)
    result = pr.plan_route(**args)
    assert result["status"] == "success", result
    ends = _day_ends(result)
    i_prague = next(i for i, e in enumerate(ends) if _near(e, PRAGUE))
    i_dresden = next(i for i, e in enumerate(ends) if _near(e, DRESDEN))
    assert i_prague < i_dresden and _near(ends[-1], SALZBURG)
    total_call = maps.directions.call_args_list[0].kwargs
    assert total_call["optimize_waypoints"] is False
    assert total_call["waypoints"][0].startswith(str(PRAGUE["lat"]))


# ── send_form: tool call without the model, then the model describes it ──

def test_send_form_plans_without_asking_the_model_first(monkeypatch):
    dispatched = []

    def fake_dispatch(name, args):
        dispatched.append((name, args))
        return {"status": "success", "trip": {"id": "trip-9", "origin": POZNAN, "destination": SALZBURG},
                "daily_schedules": [{"day_number": 1, "waypoints": []}], "num_days": 3}

    monkeypatch.setattr(ch, "dispatch", fake_dispatch)
    monkeypatch.setattr(ch, "_store_message", lambda *a, **k: None)
    monkeypatch.setattr(ch, "_stored_trip", lambda *a, **k: False)
    monkeypatch.setattr(ch, "log_chat_turn", lambda *a, **k: None)
    calls = []

    def create(**kwargs):
        calls.append(kwargs)
        return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(
            content="Three days to Salzburg, nights in Prague and Linz.", tool_calls=None))])

    session = {"client": SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=create))),
               "tools": [], "history": [{"role": "system", "content": "P"}], "lang": "en",
               "user_id": "anon", "active_trip_id": "old-trip"}
    result = ch.send_form(session, {"mode": "direct", "origin": POZNAN, "destination": SALZBURG,
                                    "num_days": 3})
    assert [d[0] for d in dispatched] == ["plan_route"]
    assert len(calls) == 1                                   # only the description
    roles = [m["role"] for m in calls[0]["messages"]]
    assert roles[-4:] == ["user", "assistant", "tool", "system"]   # + "describe the route" note
    assert session["active_trip_id"] == "trip-9"
    assert result["text"].startswith("Three days") and result["summary"].startswith("Plan a trip")


def test_send_form_reports_a_bad_form():
    result = ch.send_form({"history": [], "lang": "en"}, {"mode": "direct", "origin": POZNAN})
    assert result["status"] == "error" and "destination" in result["text"]


# ── /api/plan_form ───────────────────────────────────────────

def test_endpoint_uses_the_page_conversation(monkeypatch):
    import tools.server as server
    seen = []

    def fake_send_form(chat, form, user_location=None):
        seen.append((chat.get("conversation_id"), form))
        chat["active_trip_id"] = "trip-form"
        return {"status": "success", "text": "Planned.", "tool_calls": [], "summary": "Plan a trip: A → B"}

    monkeypatch.setattr(server, "send_form", fake_send_form)
    monkeypatch.setattr(server, "make_sniffer_line", lambda *a, **k: {"spoken": "Planned."})
    monkeypatch.setattr(server, "create_chat_session", lambda **k: {"history": [], "lang": "en"})
    server._CHAT_SESSIONS.clear()
    server.app.config["TESTING"] = True
    with server.app.test_client() as c:
        r = c.post("/api/plan_form", json={"form": {"mode": "direct"}, "conversation_id": "page-7"})
        assert r.status_code == 200 and r.get_json()["sniffer"] == {"spoken": "Planned."}
        assert seen[0][0] == "page-7"
        # the chat on the same page continues with this trip
        assert server._CHAT_SESSIONS["anon:page-7"]["active_trip_id"] == "trip-form"

        monkeypatch.setattr(server, "send_form", lambda *a, **k: {
            "status": "error", "text": "Please enter the destination.", "tool_calls": []})
        r = c.post("/api/plan_form", json={"form": {}, "conversation_id": "page-7"})
        assert r.status_code == 400 and "destination" in r.get_json()["text"]
    server._CHAT_SESSIONS.clear()

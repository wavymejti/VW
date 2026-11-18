"""
Regressions from the Poznań/Warsaw <-> Lausanne castles conversation (18 Nov 2026).
"""

from unittest.mock import MagicMock

import pytest

import tools.plan_route as pr
from navigation import chat_handler, dispatcher

POZNAN = {"label": "Poznań", "lat": 52.4064, "lng": 16.9252}
LAUSANNE = {"label": "Lausanne", "lat": 46.5197, "lng": 6.6323}


# ── planner ─────────────────────────────────────────────────────────────────

@pytest.fixture
def planner(monkeypatch):
    client = MagicMock()

    def directions(origin, destination, **kwargs):
        o = [float(x) for x in origin.split(",")]
        d = [float(x) for x in destination.split(",")]
        steps = [{"duration": {"value": 3600}, "distance": {"value": 100000},
                  "end_location": {"lat": o[0] + (d[0] - o[0]) * i / 10,
                                   "lng": o[1] + (d[1] - o[1]) * i / 10}} for i in range(1, 11)]
        return [{"legs": [{"distance": {"value": 1000000}, "duration": {"value": 36000}, "steps": steps}],
                 "overview_polyline": {"points": "x"}, "waypoint_order": []}]

    client.directions.side_effect = directions
    client.geocode.return_value = []
    monkeypatch.setattr(pr, "get_maps_client", lambda: client)
    monkeypatch.setattr(pr, "get_weather_forecast", lambda *a, **k: {"status": "error"})
    monkeypatch.setattr(pr, "search_campings", lambda lat, lng, **k: {
        "status": "success", "results": [{"name": "Camp", "lat": lat, "lng": lng}]})
    return client


def test_far_waypoints_are_skipped_with_a_warning(planner):
    r = pr.plan_route(POZNAN, LAUSANNE, num_days=4, start_date="2027-07-01",
                      max_daily_drive_hours=10, waypoints=[
                          {"label": "Neuschwanstein", "lat": 47.5576, "lng": 10.7498},
                          {"label": "Wooden Church of Vang, Norway", "lat": 61.12, "lng": 8.5},
                          {"label": "Zamek Krzyżtopór", "lat": 50.73, "lng": 21.52},
                      ])
    stops = [w["label"] for d in r["daily_schedules"] for w in d["waypoints"] if w["type"] == "attraction"]
    assert stops == ["Neuschwanstein"]
    assert sum("Skipped" in w for w in r["warnings"]) == 2


def test_far_waypoints_kept_when_allowed(planner):
    r = pr.plan_route(POZNAN, LAUSANNE, num_days=4, start_date="2027-07-01",
                      max_daily_drive_hours=20, allow_far_waypoints=True,
                      waypoints=[{"label": "Zamek Krzyżtopór", "lat": 50.73, "lng": 21.52}])
    assert any(w["type"] == "attraction" for d in r["daily_schedules"] for w in d["waypoints"])


def test_failed_save_is_reported(planner, monkeypatch):
    monkeypatch.setattr(pr, "get_engine", MagicMock(side_effect=RuntimeError("db down")))
    r = pr.plan_route(POZNAN, LAUSANNE, num_days=3, start_date="2027-07-01",
                      max_daily_drive_hours=10, user_id="u1")
    assert r["saved"] is False and "db down" in r["save_error"]
    r2 = pr.plan_route(POZNAN, LAUSANNE, num_days=3, start_date="2027-07-01",
                       max_daily_drive_hours=10)
    assert r2["saved"] is False and r2["save_error"] is None  # anonymous: nothing to save


# ── dispatcher ──────────────────────────────────────────────────────────────

def test_search_campings_at_zero_zero_is_refused():
    r = dispatcher.dispatch("search_campings", {"lat": 0, "lng": 0, "radius_km": 1})
    assert r["status"] == "error" and "No location" in r["message"]


def test_get_trip_summary_is_wired():
    assert "get_trip_summary" in dispatcher.TOOL_REGISTRY


def test_conversation_waypoints_survive_modify_without_db(monkeypatch):
    captured = {}
    monkeypatch.setattr(dispatcher, "plan_route", lambda **k: captured.update(k) or {"status": "success"})
    dispatcher.dispatch("modify_route", {
        "origin": POZNAN, "destination": LAUSANNE, "num_days": 10, "start_date": "2099-01-01",
        "exclude_places": ["Krzyżtopór"],
        "_conversation_waypoints": [{"label": "Zamek Krzyżtopór", "lat": 50.7, "lng": 21.5},
                                    {"label": "Neuschwanstein", "lat": 47.5, "lng": 10.7}]})
    assert [w["label"] for w in captured["waypoints"]] == ["Neuschwanstein"]


def test_descriptions_ask_for_concrete_places():
    tools = {t["function"]["name"]: t["function"] for t in dispatcher.OPENAI_TOOL_DEFINITIONS}
    assert "suggest_attractions" in tools["plan_route"]["parameters"]["properties"]["waypoints"]["description"]
    assert "DIFFERENT city" in tools["plan_route"]["description"]


# ── chat handler ────────────────────────────────────────────────────────────

def _completion(message):
    resp = MagicMock()
    resp.choices = [MagicMock(message=message)]
    return resp


def _tool_msg(name, arguments):
    tc = MagicMock()
    tc.id = f"call_{name}"
    tc.function.name = name
    tc.function.arguments = arguments
    msg = MagicMock(tool_calls=[tc], content=None)
    msg.model_dump.return_value = {"role": "assistant", "content": None, "tool_calls": [
        {"id": tc.id, "type": "function", "function": {"name": name, "arguments": arguments}}]}
    return msg


@pytest.fixture
def chat(monkeypatch):
    calls = []
    plan_result = {"status": "success", "num_days": 10,
                   "trip": {"id": "t1", "origin": POZNAN, "destination": LAUSANNE,
                            "start_date": "2026-11-19"},
                   "daily_schedules": [
                       {"day_number": 1, "driving_km": 400, "route_polyline": "ABC" * 500,
                        "waypoints": [{"type": "start", "label": "Poznań"},
                                      {"type": "attraction", "label": "Neuschwanstein", "lat": 47.5, "lng": 10.7},
                                      {"type": "camping", "label": "Camp"}],
                        "overnight_camping": {"name": "Camp", "photos": ["p"] * 20},
                        "overnight_options": [{"name": f"Opt {i}", "source": "park4night"} for i in range(9)]}]}

    def fake_dispatch(name, args):
        calls.append((name, dict(args)))
        if name == "plan_route":
            return plan_result
        if name == "get_trip_summary":
            return {"status": "error", "message": "Trip not found: t1"}
        return dispatcher.dispatch(name, args) if name == "modify_route" else {"status": "success"}

    monkeypatch.setattr(chat_handler, "dispatch", fake_dispatch)
    monkeypatch.setattr(dispatcher, "plan_route", lambda **k: calls.append(("planner", k)) or plan_result)
    for fn in ("_store_message", "log_interaction", "log_chat_turn"):
        monkeypatch.setattr(chat_handler, fn, lambda *a, **k: None)
    client = MagicMock()
    session = {"client": client, "tools": [], "user_id": "anon", "trip_id": None,
               "history": [{"role": "system", "content": "P"}], "lang": "en", "active_trip_id": None}
    final = MagicMock(tool_calls=None, content="ok")

    def turn(tool, args):
        client.chat.completions.create.side_effect = [_completion(_tool_msg(tool, args)), _completion(final)]
        return chat_handler.send_message(session, "msg")

    return session, calls, turn


def test_notes_only_modify_is_not_turned_into_a_replan(chat):
    session, calls, turn = chat
    turn("plan_route", '{"origin": {"label": "Poznań"}, "destination": {"label": "Lausanne"}, "num_days": 10, "start_date": "2026-11-19"}')
    result = turn("modify_route", '{"trip_id": "t1", "notes": "two overnight options per night"}')
    assert result["tool_calls"][0]["result"]["status"] == "error"
    assert "Nothing to change" in result["tool_calls"][0]["result"]["message"]
    assert not any(c[0] == "planner" for c in calls)


def test_get_trip_summary_falls_back_to_the_chat_trip(chat):
    session, calls, turn = chat
    turn("plan_route", '{"origin": {"label": "Poznań"}, "destination": {"label": "Lausanne"}, "num_days": 10, "start_date": "2026-11-19"}')
    result = turn("get_trip_summary", '{"trip_id": "t1"}')
    summary = result["tool_calls"][0]["result"]
    assert summary["status"] == "success"
    assert summary["days"][0]["stops"][1] == "attraction: Neuschwanstein"


def test_model_reads_a_slim_tool_result(chat):
    session, calls, turn = chat
    turn("plan_route", '{"origin": {"label": "Poznań"}, "destination": {"label": "Lausanne"}, "num_days": 10, "start_date": "2026-11-19"}')
    tool_msg = next(m for m in session["history"] if m.get("role") == "tool")
    assert "ABCABC" not in tool_msg["content"]          # no polyline
    assert '"photos"' not in tool_msg["content"]
    assert tool_msg["content"].count("Opt ") == 6       # options trimmed


def test_raw_reply_goes_to_the_log(monkeypatch):
    logged = {}
    monkeypatch.setattr(chat_handler, "log_chat_turn", lambda *a, **k: logged.update(k))
    for fn in ("_store_message", "log_interaction"):
        monkeypatch.setattr(chat_handler, fn, lambda *a, **k: None)
    client = MagicMock()
    raw = 'Hi!\n<slot_state>{}</slot_state>\nHello again!'
    client.chat.completions.create.return_value = _completion(MagicMock(tool_calls=None, content=raw))
    session = {"client": client, "tools": [], "user_id": "anon", "trip_id": None,
               "history": [{"role": "system", "content": "P"}], "lang": "en", "active_trip_id": None}
    chat_handler.send_message(session, "hi")
    assert logged["raw_reply"] == raw


def test_trip_ending_in_another_city_keeps_castles_near_the_stay(planner):
    """Poznań -> Lausanne (2 days) -> Warsaw: castles on the way to Lausanne are on the route."""
    warsaw = {"label": "Warszawa", "lat": 52.2297, "lng": 21.0122}
    r = pr.plan_route(POZNAN, warsaw, num_days=10, start_date="2027-07-01",
                      max_daily_drive_hours=10,
                      stays=[{"label": "Lausanne", "lat": LAUSANNE["lat"], "lng": LAUSANNE["lng"], "days": 2}],
                      waypoints=[{"label": "Schloss Heidelberg", "lat": 49.4106, "lng": 8.7153},
                                 {"label": "Kaiserburg Nürnberg", "lat": 49.458, "lng": 11.0757}])
    assert not any("Skipped" in w for w in r["warnings"]), r["warnings"]
    kinds = ["stay" if d.get("stay") else "drive" for d in r["daily_schedules"]]
    assert kinds.count("stay") == 2 and r["daily_schedules"][-1]["waypoints"][-1]["label"] == "Warszawa"


def test_skip_warning_explains_how_to_end_in_a_city(planner):
    r = pr.plan_route(POZNAN, LAUSANNE, num_days=4, start_date="2027-07-01", max_daily_drive_hours=10,
                      waypoints=[{"label": "Warszawa", "lat": 52.2297, "lng": 21.0122}])
    assert any("make it the destination" in w for w in r["warnings"])

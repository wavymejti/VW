"""
Overnight stops in plan_route, modify_route and the chat handler (Nov 2026 fix).

Regression: "Poznań → Berlin with a night in between" produced a route straight to
Berlin, because a night only exists when num_days >= 2 and nothing enforced it.
All Google Maps / campsite / weather / DB calls are mocked.
"""

from unittest.mock import MagicMock, patch

import pytest

import tools.plan_route as pr
from navigation import chat_handler

POZNAN = {"label": "Poznań", "lat": 52.4084, "lng": 16.9342}
BERLIN = {"label": "Berlin", "lat": 52.52, "lng": 13.405}
FRANKFURT_ODER = {"label": "Frankfurt (Oder)", "lat": 52.3471, "lng": 14.5506}


def _directions(*args, **kwargs):
    """Two-hour steps along a straight line Poznań → Berlin."""
    steps = []
    for i in range(1, 5):
        f = i / 4
        steps.append({
            "duration": {"value": 1800},
            "end_location": {
                "lat": POZNAN["lat"] + (BERLIN["lat"] - POZNAN["lat"]) * f,
                "lng": POZNAN["lng"] + (BERLIN["lng"] - POZNAN["lng"]) * f,
            },
        })
    return [{
        "legs": [{"distance": {"value": 280000}, "duration": {"value": 7200}, "steps": steps}],
        "overview_polyline": {"points": "abc"},
        "waypoint_order": [],
    }]


def _geocode(label):
    known = {"Frankfurt (Oder)": FRANKFURT_ODER, "Berlin": BERLIN, "Poznań": POZNAN}
    if label in known:
        p = known[label]
        return [{"geometry": {"location": {"lat": p["lat"], "lng": p["lng"]}}, "place_id": "x"}]
    return []


@pytest.fixture
def maps(monkeypatch):
    client = MagicMock()
    client.directions.side_effect = _directions
    client.geocode.side_effect = _geocode
    monkeypatch.setattr(pr, "get_maps_client", lambda: client)
    monkeypatch.setattr(pr, "get_weather_forecast", lambda *a, **k: {"status": "error"})
    return client


def _campings(found=True):
    calls = []

    def search(lat, lng, radius_km=30, **kwargs):
        calls.append(radius_km)
        if not found:
            return {"status": "success", "results": []}
        return {"status": "success", "results": [
            {"name": f"Camp near {lat:.2f},{lng:.2f}", "lat": lat, "lng": lng, "place_id": "c1"}
        ]}

    return search, calls


def test_one_night_on_the_way_gives_campsite_on_day_one(maps, monkeypatch):
    search, _ = _campings()
    monkeypatch.setattr(pr, "search_campings", search)
    result = pr.plan_route(POZNAN, BERLIN, num_days=2, start_date="2026-11-19")
    assert result["status"] == "success"
    assert result["overnight_count"] == 1
    day1, day2 = result["daily_schedules"]
    assert day1["waypoints"][-1]["type"] == "camping"
    assert day2["waypoints"][-1]["label"] == "Berlin"
    assert result["warnings"] == []


def test_overnight_stop_raises_num_days_and_is_used(maps, monkeypatch):
    search, _ = _campings()
    monkeypatch.setattr(pr, "search_campings", search)
    result = pr.plan_route(
        POZNAN, BERLIN, num_days=1, start_date="2026-11-19",
        overnight_stops=[{"label": "Frankfurt (Oder)"}],
    )
    assert result["status"] == "success"
    assert result["num_days"] == 2
    assert len(result["daily_schedules"]) == 2
    camp = result["daily_schedules"][0]["overnight_camping"]
    # campsite searched around the requested town, not the interpolated midpoint
    assert abs(camp["lat"] - FRANKFURT_ODER["lat"]) < 0.01
    assert abs(camp["lng"] - FRANKFURT_ODER["lng"]) < 0.01
    assert any("num_days raised" in w for w in result["warnings"])


def test_unknown_overnight_place_is_reported(maps, monkeypatch):
    search, _ = _campings()
    monkeypatch.setattr(pr, "search_campings", search)
    result = pr.plan_route(
        POZNAN, BERLIN, num_days=2, start_date="2026-11-19",
        overnight_stops=["Nowhereville"],
    )
    assert result["status"] == "success"
    assert any("Nowhereville" in w for w in result["warnings"])


def test_no_campsite_widens_search_then_warns(maps, monkeypatch):
    search, calls = _campings(found=False)
    monkeypatch.setattr(pr, "search_campings", search)
    result = pr.plan_route(POZNAN, BERLIN, num_days=2, start_date="2026-11-19")
    assert calls == [30, 50]
    assert result["daily_schedules"][0]["overnight_camping"] is None
    assert any("no campsite" in w for w in result["warnings"])


def test_origin_and_destination_by_name_are_geocoded(maps, monkeypatch):
    search, _ = _campings()
    monkeypatch.setattr(pr, "search_campings", search)
    result = pr.plan_route({"label": "Poznań"}, "Berlin", num_days=2, start_date="2026-11-19")
    assert result["status"] == "success"
    assert result["trip"]["destination"]["lat"] == BERLIN["lat"]


def test_apply_overnight_stops_keeps_travel_order():
    points = [{"lat": 0, "lng": i, "label": f"p{i}"} for i in range(1, 5)]
    stops = [{"label": "A", "lat": 0, "lng": 1.1}, {"label": "B", "lat": 0, "lng": 3.9}]
    out = pr._apply_overnight_stops(points, stops)
    assert [p["label"] for p in out] == ["A", "p2", "p3", "B"]


def test_modify_route_passes_overnight_stops(monkeypatch):
    from navigation import dispatcher
    captured = {}

    def fake_plan_route(**kwargs):
        captured.update(kwargs)
        return {"status": "success"}

    monkeypatch.setattr(dispatcher, "plan_route", fake_plan_route)
    dispatcher.dispatch("modify_route", {
        "origin": POZNAN, "destination": BERLIN, "num_days": 2,
        "start_date": "2099-01-01",
        "overnight_stops": [{"label": "Frankfurt (Oder)"}],
    })
    assert captured["overnight_stops"] == [{"label": "Frankfurt (Oder)"}]


def test_tool_schema_documents_overnights():
    from navigation.dispatcher import OPENAI_TOOL_DEFINITIONS
    tools = {t["function"]["name"]: t["function"] for t in OPENAI_TOOL_DEFINITIONS}
    for name in ("plan_route", "modify_route"):
        props = tools[name]["parameters"]["properties"]
        assert "overnight_stops" in props
        assert "nights + 1" in props["num_days"]["description"]


def _fake_completion(message):
    resp = MagicMock()
    resp.choices = [MagicMock(message=message)]
    return resp


def test_followup_call_keeps_language_note(monkeypatch):
    """The second OpenAI call (after a tool) must still carry the language note."""
    tc = MagicMock()
    tc.id = "call_1"
    tc.function.name = "search_campings"
    tc.function.arguments = '{"lat": 52.0, "lng": 15.0}'
    first = MagicMock(tool_calls=[tc], content=None)
    first.model_dump.return_value = {
        "role": "assistant", "content": None,
        "tool_calls": [{"id": "call_1", "type": "function",
                        "function": {"name": "search_campings", "arguments": "{}"}}],
    }
    final = MagicMock(tool_calls=None, content="Here are campsites.")

    client = MagicMock()
    client.chat.completions.create.side_effect = [_fake_completion(first), _fake_completion(final)]
    monkeypatch.setattr(chat_handler, "dispatch", lambda n, a: {"status": "success", "results": []})
    monkeypatch.setattr(chat_handler, "_store_message", lambda *a, **k: None)
    monkeypatch.setattr(chat_handler, "log_interaction", lambda *a, **k: None)
    monkeypatch.setattr(chat_handler, "log_chat_turn", lambda *a, **k: None)

    session = {"client": client, "tools": [], "user_id": "anon", "trip_id": None,
               "history": [{"role": "system", "content": "PROMPT"}], "lang": "en",
               "active_trip_id": None}
    result = chat_handler.send_message(session, "campsites near Słubice?")
    assert result["status"] == "success"
    second_call = client.chat.completions.create.call_args_list[1].kwargs["messages"]
    assert any(m.get("role") == "system" and "English" in m.get("content", "")
               for m in second_call if isinstance(m, dict))


def test_text_reply_without_slot_block_keeps_previous_slots():
    session = {"slot_state": {"origin": "Poznań", "destination": "Berlin"}}
    _, slots = chat_handler._parse_slot_state("No block here.", session)
    assert slots["origin"] == "Poznań"


def test_anonymous_session_has_no_user_id():
    assert chat_handler._real_user_id({"user_id": "anon"}) is None
    assert chat_handler._real_user_id({"user_id": "abc"}) == "abc"


def test_reply_repeated_after_slot_block_is_shown_once():
    raw = ('Shall I replace the current route?\n<slot_state>{"origin": "Poznań"}</slot_state>\n'
           'Would you like me to replace the current route?')
    text, slots = chat_handler._parse_slot_state(raw, {})
    assert text == "Shall I replace the current route?"
    assert slots["origin"] == "Poznań"


def test_reply_only_after_slot_block_is_kept():
    text, _ = chat_handler._parse_slot_state('<slot_state>{}</slot_state>\nHello!', {})
    assert text == "Hello!"

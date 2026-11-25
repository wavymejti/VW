"""
Changing part of a saved route with a drawn line (Nov 2026 tests).

Only the stretch between the line's ends changes: its days get the drawn points as hidden
"via" waypoints, campsites and other days stay.
"""

import pytest
from googlemaps.convert import encode_polyline

from navigation.route_reshape import plan_reshape, ReshapeError, SNAP_KM

POZNAN = (52.41, 16.93)
NUREMBERG = (49.45, 11.08)
PRAGUE = (50.08, 14.44)


def _line(a, b, n=40):
    return [{"lat": a[0] + (b[0] - a[0]) * i / n, "lng": a[1] + (b[1] - a[1]) * i / n} for i in range(n + 1)]


def _day(a, b, inner=()):
    return {"route_polyline": encode_polyline(_line(a, b)),
            "waypoints": [{"type": "start", "lat": a[0], "lng": a[1]}, *inner,
                          {"type": "camping", "label": "Camp", "lat": b[0], "lng": b[1]}]}


def _trip():
    stay = {"route_polyline": None, "waypoints": [{"type": "stay", "lat": PRAGUE[0], "lng": PRAGUE[1]}]}
    return [_day(POZNAN, NUREMBERG), _day(NUREMBERG, PRAGUE), stay]


# A detour south (via Regensburg-ish) on day 2, from just after Nuremberg to just before Prague.
DETOUR = [{"lat": 49.50, "lng": 11.30}, {"lat": 49.02, "lng": 12.10}, {"lat": 49.20, "lng": 13.40},
          {"lat": 50.02, "lng": 14.25}]


def test_only_the_drawn_stretch_changes():
    plan = plan_reshape(_trip(), DETOUR)
    assert set(plan["days"]) == {1}                        # day 2 only; day 1 and the stay stay
    wps = plan["days"][1]
    assert wps[0]["type"] == "start" and wps[-1]["type"] == "camping"   # campsite kept
    vias = [w for w in wps if w["type"] == "via"]
    assert [(v["lat"], v["lng"]) for v in vias] == [(p["lat"], p["lng"]) for p in DETOUR]


def test_line_drawn_backwards_is_turned_round():
    plan = plan_reshape(_trip(), DETOUR[::-1])
    vias = [w for w in plan["days"][1] if w["type"] == "via"]
    assert vias[0]["lng"] == DETOUR[0]["lng"] and vias[-1]["lng"] == DETOUR[-1]["lng"]


def test_a_stretch_over_a_night_splits_between_the_days():
    # From day 1 (Poznań–Nuremberg, ~3/4 of the way) to day 2, away from the night in Nuremberg.
    line = [{"lat": 50.2, "lng": 12.56}, {"lat": 50.3, "lng": 12.0}, {"lat": 50.1, "lng": 12.4},
            {"lat": 49.75, "lng": 12.8}, {"lat": 49.8, "lng": 13.4}]
    plan = plan_reshape(_trip(), line)
    assert set(plan["days"]) == {0, 1}
    assert any(w["type"] == "via" for w in plan["days"][0])
    assert any(w["type"] == "via" for w in plan["days"][1])
    assert plan["days"][0][-1]["label"] == "Camp"             # the night in between stays


def test_older_drawing_of_the_stretch_is_replaced_and_stops_are_kept():
    old_via = {"type": "via", "label": "via", "lat": 49.9, "lng": 13.0}
    castle = {"type": "attraction", "label": "Castle", "lat": 49.77, "lng": 12.76}
    trip = _trip()
    trip[1] = _day(NUREMBERG, PRAGUE, inner=[castle, old_via])
    wps = plan_reshape(trip, DETOUR)["days"][1]
    assert old_via not in wps
    assert castle in wps


@pytest.mark.parametrize("line, code", [
    ([{"lat": 45.0, "lng": 5.0}, {"lat": 50.0, "lng": 14.3}], "off_route"),
    ([{"lat": 49.6, "lng": 11.8}, {"lat": 49.61, "lng": 11.81}], "too_short"),
    ([{"lat": 49.6, "lng": 11.8}], "too_short"),
])
def test_lines_that_cannot_change_the_route(line, code):
    with pytest.raises(ReshapeError) as e:
        plan_reshape(_trip(), line)
    assert e.value.code == code


def test_endpoint_tells_the_chat(monkeypatch):
    import navigation.route_reshape as rr
    import tools.server as server
    monkeypatch.setattr(rr, "reshape_route", lambda trip_id, stroke: {
        "status": "success", "message": "The route now follows your line on day 2.",
        "warnings": ["Day 2 is now about 8.4 h of driving."], "days_changed": [2], "trip_data": {}})
    monkeypatch.setattr(server, "create_chat_session", lambda **k: {"history": [], "lang": "en"})
    server._CHAT_SESSIONS.clear()
    server.app.config["TESTING"] = True
    with server.app.test_client() as c:
        r = c.post("/api/reshape_route", json={"trip_id": "t1", "stroke": DETOUR})
        assert r.status_code == 401                              # not logged in
        with c.session_transaction() as s:
            s["user_id"] = "u1"
        r = c.post("/api/reshape_route", json={"trip_id": "t1", "stroke": DETOUR, "conversation_id": "p1"})
        assert r.status_code == 200 and r.get_json()["days_changed"] == [2]
        note = server._CHAT_SESSIONS["u1:p1"]["history"][-1]["content"]
        assert "redrew part of the route" in note and "8.4 h" in note
    server._CHAT_SESSIONS.clear()

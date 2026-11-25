"""
modify_route after a trip from the start form or a drawn line keeps the stop order and the
drawing (Nov 2026): route_stops / via_points travel with the trip (trips.plan_params, or the
chat session for unsaved trips) and are passed to plan_route again.
"""

import json
from types import SimpleNamespace

from navigation import chat_handler as ch
from navigation import dispatcher as dp

PRAGUE = {"label": "Prague", "lat": 50.08, "lng": 14.43, "nights": 0, "leg": "out"}
LINZ = {"label": "Linz", "lat": 48.31, "lng": 14.29, "nights": 3, "leg": "out"}
VIA = [{"lat": 51.0, "lng": 15.0}, {"lat": 50.5, "lng": 14.8}]
BERLIN = {"label": "Berlin, Germany", "lat": 52.52, "lng": 13.40}
VIENNA = {"label": "Vienna, Austria", "lat": 48.21, "lng": 16.37}


def test_shape_kept_without_duplicates():
    waypoints = [{"label": "Prague", "lat": 50.081, "lng": 14.431}, {"label": "Karlštejn", "lat": 49.94, "lng": 14.19}]
    stays = [{"label": "Linz", "lat": 48.32, "lng": 14.30, "days": 2}, {"days": 2}]
    rs, via, wps, st = dp._keep_trip_shape([PRAGUE, LINZ], VIA, [], False, waypoints, stays)
    assert [s["label"] for s in rs] == ["Prague", "Linz"] and via == VIA
    assert [w["label"] for w in wps] == ["Karlštejn"]          # Prague comes back via route_stops
    assert st == [{"days": 2}]                                 # Linz stay comes back via route_stops


def test_excluded_stop_and_moved_end():
    rs, via, _, _ = dp._keep_trip_shape([PRAGUE, LINZ], VIA, ["prague"], True, [], None)
    assert [s["label"] for s in rs] == ["Linz"] and via == []


def test_moved():
    assert not dp._moved(("Berlin", None), (BERLIN, VIENNA))
    assert not dp._moved((dict(BERLIN), None), (BERLIN, VIENNA))
    assert dp._moved((None, "Munich"), (BERLIN, VIENNA))
    assert dp._moved((None, {"label": "x", "lat": 48.14, "lng": 11.58}), (BERLIN, VIENNA))


def _capture_plan_route(monkeypatch):
    seen = {}

    def fake_plan_route(**kw):
        seen.update(kw)
        return {"status": "success", "trip": {"origin": kw["origin"], "destination": kw["destination"],
                                              "plan_params": {"route_stops": kw.get("route_stops"),
                                                              "via_points": kw.get("via_points")}},
                "daily_schedules": []}

    monkeypatch.setattr(dp, "plan_route", fake_plan_route)
    return seen


def test_modify_route_passes_route_stops_and_via(monkeypatch):
    seen = _capture_plan_route(monkeypatch)
    res = dp._handle_modify_route({
        "origin": BERLIN, "destination": VIENNA, "num_days": 6, "start_date": "2099-05-10",
        "max_daily_km": 400, "route_stops": [PRAGUE, LINZ], "via_points": VIA,
        "_conversation_waypoints": [{"label": "Prague", "lat": 50.08, "lng": 14.43}],
    })
    assert res["status"] == "success"
    assert [s["label"] for s in seen["route_stops"]] == ["Prague", "Linz"]
    assert seen["via_points"] == VIA and seen["waypoints"] == []


def test_saved_trip_reads_plan_params(monkeypatch):
    seen = _capture_plan_route(monkeypatch)
    import tools.plan_route as pr
    monkeypatch.setattr(pr, "load_plan_params", lambda tid: {"route_stops": [PRAGUE], "via_points": VIA})
    import tools.db
    monkeypatch.setattr(tools.db, "get_engine", lambda: (_ for _ in ()).throw(RuntimeError("no db")))
    dp._handle_modify_route({"trip_id": "t1", "origin": BERLIN, "destination": VIENNA, "num_days": 4,
                             "start_date": "2099-05-10", "max_daily_km": 300})
    assert seen["route_stops"] == [PRAGUE] and seen["via_points"] == VIA


def _call(name, args):
    return SimpleNamespace(id="c", function=SimpleNamespace(name=name, arguments=json.dumps(args)))


def test_chat_keeps_the_form_shape_for_the_next_change(monkeypatch):
    calls = []

    def fake_dispatch(name, args):
        calls.append((name, dict(args)))
        return {"status": "success", "num_days": 6, "daily_schedules": [],
                "trip": {"origin": BERLIN, "destination": VIENNA, "start_date": "2099-05-10",
                         "plan_params": {"route_stops": [PRAGUE, LINZ], "via_points": VIA}}}

    monkeypatch.setattr(ch, "dispatch", fake_dispatch)
    session = {"history": [], "lang": "en"}
    ch._run_tool(session, _call("plan_route", {"origin": BERLIN, "destination": VIENNA,
                                               "route_stops": [PRAGUE, LINZ], "via_points": VIA}), [])
    assert session["last_plan"]["route_stops"] == [PRAGUE, LINZ]

    ch._run_tool(session, _call("modify_route", {"max_daily_km": 350}), [])
    args = calls[-1][1]
    assert args["route_stops"] == [PRAGUE, LINZ] and args["via_points"] == VIA
    assert not args.get("_origin_changed")

    ch._run_tool(session, _call("modify_route", {"destination": "Munich"}), [])
    assert calls[-1][1]["_origin_changed"] is True

"""
Extending a saved trip with a line drawn from its end (Nov 2026 tests).

New days are planned along the line and added after the last day; the planned days stay,
and a trip that ended without a night gets a campsite there first.
"""

from contextlib import contextmanager

import pytest

import navigation.route_extend as re_
import tools.trip_store as ts
import tools.search_campings as sc
import tools.plan_route as pr
import navigation.dispatcher as disp
import tools.db as db

BRNO = {"lat": 49.19, "lng": 16.61}
FRANKIVSK = {"lat": 48.92, "lng": 24.71}
LINE = [{"lat": 49.2, "lng": 16.65}, {"lat": 48.95, "lng": 19.0}, {"lat": 48.7, "lng": 21.25}, FRANKIVSK]


def _trip(last_type="end"):
    return {"trip": {"id": "t1", "origin": {"label": "Płock"}},
            "daily_schedules": [
                {"day_number": 1, "date": "2026-11-25", "waypoints": [
                    {"type": "start", "lat": 52.5, "lng": 19.7}, {"type": "camping", "label": "Camp A", "lat": 51.0, "lng": 17.5}]},
                {"day_number": 2, "date": "2026-11-26", "waypoints": [
                    {"type": "start", "lat": 51.0, "lng": 17.5}, {"type": last_type, "label": "Brno", **BRNO}]},
            ]}


class FakeConn:
    def __init__(self):
        self.calls = []

    def execute(self, stmt, params=None):
        self.calls.append((str(stmt), params))


@pytest.fixture
def env(monkeypatch):
    conn = FakeConn()

    @contextmanager
    def begin():
        yield conn

    monkeypatch.setattr(db, "get_engine", lambda: type("E", (), {"begin": staticmethod(begin)})())
    state = {"trip": _trip(), "planned": None, "campsite": None}
    monkeypatch.setattr(ts, "get_trip_data", lambda tid: state["trip"] if tid == "t1" else None)
    monkeypatch.setattr(sc, "search_campings", lambda **k: {"results": [
        {"name": "Camping Hana", "lat": 49.18, "lng": 16.6}]})
    monkeypatch.setattr(disp, "apply_campsite_change",
                        lambda tid, day, camp: state.update(campsite=(day, camp["name"])) or {"status": "success"})

    def fake_plan(**kwargs):
        state["planned"] = kwargs
        n = kwargs["num_days"]
        return {"status": "success", "warnings": [], "daily_schedules": [
            {"day_number": i, "date": f"2026-11-{26 + i}", "driving_hours": 5.0, "driving_km": 400.0,
             "waypoints": [{"type": "start"}, {"type": "camping"}], "route_polyline": "x",
             "overnight_camping": {"id": None}} for i in range(1, n + 1)]}

    monkeypatch.setattr(pr, "plan_route", fake_plan)
    return state, conn


def test_days_are_added_after_the_last_day(env):
    state, conn = env
    res = re_.extend_route("t1", LINE, end_label="Ivano-Frankivsk", extra_days=3, dest_days=1)
    assert res["status"] == "success", res
    assert res["days_added"] == [3, 4, 5]
    plan = state["planned"]
    assert plan["start_date"] == "2026-11-27"                     # the day after the trip's last day
    assert plan["origin"]["label"] == "Camping Hana"               # from the new night at Brno
    assert plan["via_points"] == LINE[1:-1]
    assert plan["destination"] == {"label": "Ivano-Frankivsk", **FRANKIVSK}
    assert plan["stays"] == [{"label": None, "days": 1}]
    assert state["campsite"] == (2, "Camping Hana")               # night added where the trip ended
    inserts = [p for sql, p in conn.calls if "INSERT INTO daily_schedules" in sql]
    assert [p["day_number"] for p in inserts] == [3, 4, 5]
    update = next(p for sql, p in conn.calls if "UPDATE trips" in sql)
    assert update["title"] == "Płock to Ivano-Frankivsk" and update["end"] == "2026-11-29"


def test_a_trip_ending_at_a_campsite_goes_on_from_there(env):
    state, _ = env
    state["trip"] = _trip(last_type="camping")
    res = re_.extend_route("t1", LINE, end_label="Ivano-Frankivsk")
    assert res["status"] == "success"
    assert state["campsite"] is None
    assert state["planned"]["origin"]["label"] == "Brno"
    assert state["planned"]["num_days"] >= 2                       # estimated: ~700 km


@pytest.mark.parametrize("trip_id, line, code", [
    ("t1", [{"lat": 52.0, "lng": 21.0}, FRANKIVSK], "off_end"),     # doesn't start at the trip's end
    ("nope", LINE, "not_saved"),
    ("t1", [FRANKIVSK], "too_short"),
])
def test_lines_that_cannot_extend(env, trip_id, line, code):
    assert re_.extend_route(trip_id, line)["code"] == code


def test_attractions_cache_follows_route_changes(monkeypatch):
    """After extending (same trip id), /api/attractions must not serve the old days."""
    import tools.server as server
    day1 = (1, 240.0, [{"lat": 52.4, "lng": 16.9}, {"lat": 51.0, "lng": 15.0}])
    routes = {"v": [day1]}

    class Conn:
        def __enter__(self): return self
        def __exit__(self, *a): return False
        def execute(self, *a, **k):
            return type("R", (), {"fetchall": lambda _s: routes["v"]})()

    monkeypatch.setattr(server, "get_engine", lambda: type("E", (), {"connect": lambda _s: Conn()})())
    calls = []
    monkeypatch.setattr(server, "suggest_attractions",
                        lambda **k: calls.append(1) or {"status": "success", "attractions_by_day": {"1": []}})
    monkeypatch.setattr(server, "get_trip_attractions_cache", lambda *a: None)
    monkeypatch.setattr(server, "save_trip_attractions_cache", lambda *a: None)
    server._ATTRACTIONS_CACHE.clear()
    with server.app.test_client() as c:
        c.get("/api/attractions/t1")
        c.get("/api/attractions/t1")
        assert len(calls) == 1                    # same route: cached
        routes["v"] = [(1, 243.0, day1[2][:1] + [{"lat": 50.9, "lng": 15.1}, day1[2][1]])]
        c.get("/api/attractions/t1")
        assert len(calls) == 1                    # a stop added to the day: no new search
        routes["v"] = [day1, (2, 300.0, [{"lat": 51.0, "lng": 15.0}, {"lat": 50.1, "lng": 14.4}])]
        c.get("/api/attractions/t1")
        assert len(calls) == 2                    # trip extended: fetched again
    server._ATTRACTIONS_CACHE.clear()

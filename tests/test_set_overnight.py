"""
Changing one night (Nov 2026): trips with a DB campsite weren't saved (Decimal in
JSON), and the chat could only re-plan the whole trip to change a night.
"""

import json
from decimal import Decimal
from unittest.mock import MagicMock

import pytest

from navigation import dispatcher


# ── Decimal ─────────────────────────────────────────────────────────────────

def test_db_campsites_come_back_as_floats(monkeypatch):
    import tools.search_campings as sc
    result = MagicMock()
    result.keys.return_value = ["id", "name", "lat", "lng", "rating", "distance_m"]
    result.fetchall.return_value = [("uuid-1", "Camp", Decimal("50.11"), Decimal("8.68"), Decimal("4.5"), 1200.0)]
    conn = MagicMock()
    conn.execute.return_value = result
    engine = MagicMock()
    engine.connect.return_value.__enter__.return_value = conn
    monkeypatch.setattr(sc, "get_engine", lambda: engine)
    camps = sc._search_database(50.1, 8.7, 30, [], None, False, 5)
    assert camps[0]["lat"] == 50.11 and isinstance(camps[0]["lat"], float)
    json.dumps(camps)  # must not raise


def test_persist_trip_writes_decimal_waypoints(monkeypatch):
    import tools.plan_route as pr
    written = []
    conn = MagicMock()
    conn.execute.side_effect = lambda sql, params=None: written.append(params)
    engine = MagicMock()
    engine.connect.return_value.__enter__.return_value = conn
    monkeypatch.setattr(pr, "get_engine", lambda: engine)
    trip = {"id": "t", "user_id": "u", "title": "x", "start_date": "2027-01-01", "end_date": "2027-01-01",
            "status": "planned", "origin": {"label": "A", "lat": 1, "lng": 2},
            "destination": {"label": "B", "lat": 3, "lng": 4}}
    day = {"id": "d", "day_number": 1, "date": "2027-01-01", "driving_hours": 1, "driving_km": 2,
           "waypoints": [{"type": "camping", "label": "C", "lat": Decimal("50.1"), "lng": Decimal("8.6")}],
           "overnight_camping": {"id": None}}
    assert pr._persist_trip(trip, [day]) is None
    assert json.loads(written[-1]["waypoints"])[0]["lat"] == 50.1


# ── set_overnight ───────────────────────────────────────────────────────────

CAMP = {"name": "Wohnmobilstellplatz Wendelsweg", "lat": 50.093, "lng": 8.705}


def test_set_overnight_on_an_unsaved_trip_explains_the_fallback(monkeypatch):
    import tools.trip_store as ts
    monkeypatch.setattr(ts, "get_trip_data", lambda tid: None)
    r = dispatcher.dispatch("set_overnight", {"trip_id": "t1", "day_number": 6, "campsite": CAMP})
    assert r["status"] == "error" and "overnight_stops" in r["message"]


def test_set_overnight_changes_one_night_and_returns_the_trip(monkeypatch):
    import tools.trip_store as ts
    calls = []
    monkeypatch.setattr(ts, "get_trip_data", lambda tid: {
        "trip": {"id": tid}, "daily_schedules": [{"day_number": 1}], "total_driving_km": 1})
    monkeypatch.setattr(dispatcher, "apply_campsite_change",
                        lambda tid, day, camp: calls.append((tid, day, camp)) or {"status": "success", "day_number": day})
    r = dispatcher.dispatch("set_overnight", {"trip_id": "t1", "day_number": "6", "campsite": CAMP})
    assert r["status"] == "success" and r["trip"]["id"] == "t1" and r["daily_schedules"]
    assert calls == [("t1", 6, {**CAMP, "place_id": None, "id": None})]


class FakeDB:
    """daily_schedules rows {day: [id, waypoints]} behind the SQL used by apply_campsite_change."""

    def __init__(self, days):
        self.days = days
        self.updates = {}

    def execute(self, sql, params):
        q = str(sql)
        if q.startswith("SELECT id, waypoints FROM daily_schedules"):
            row = self.days.get(params["day"])
            res = MagicMock()
            res.fetchone.return_value = (row[0], json.loads(json.dumps(row[1]))) if row else None
            return res
        if q.startswith("UPDATE daily_schedules"):
            self.updates[params["sid"]] = json.loads(params["wps"])
        return MagicMock()


def _db(monkeypatch, days):
    db = FakeDB(days)
    engine = MagicMock()
    engine.begin.return_value.__enter__.return_value = db
    monkeypatch.setattr("tools.db.get_engine", lambda: engine)
    recalcs = {}

    def recalc(conn, sid, wps):
        recalcs[sid] = wps
        return True

    monkeypatch.setattr(dispatcher, "_recalculate_day_route", recalc)
    return db, recalcs


def test_changing_a_stay_night_moves_the_whole_stay(monkeypatch):
    stay = lambda: [{"type": "stay", "stay_kind": "stay", "label": "Old", "lat": 1, "lng": 1}]
    db, recalcs = _db(monkeypatch, {
        1: ["d1", [{"type": "start"}, {"type": "camping", "label": "Old", "lat": 1, "lng": 1}]],
        2: ["d2", stay()], 3: ["d3", stay()],
        4: ["d4", [{"type": "start", "label": "Old"}, {"type": "end", "label": "Home"}]],
    })
    r = dispatcher.apply_campsite_change("t", 3, CAMP)     # asked on a stay day
    assert r == {"status": "success", "day_number": 1}      # -> the arrival day changes
    assert recalcs["d1"][-1]["label"] == CAMP["name"]
    assert db.updates["d2"][0]["type"] == "stay" and db.updates["d2"][0]["label"] == CAMP["name"]
    assert db.updates["d3"][0]["lat"] == CAMP["lat"]
    assert recalcs["d4"][0]["label"] == CAMP["name"]        # next driving day starts there


def test_schema_and_prompt_point_to_set_overnight():
    from tools.openai_client import SYSTEM_PROMPT
    names = [t["function"]["name"] for t in dispatcher.OPENAI_TOOL_DEFINITIONS]
    assert "set_overnight" in names and "set_overnight" in SYSTEM_PROMPT

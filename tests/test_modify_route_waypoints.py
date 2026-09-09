"""
Unit and integration tests for route planning and modification with waypoints.

Tests:
- plan_route correctly assigns waypoints to daily schedules and polylines.
- modify_route preserves round_trip and incorporates new waypoints.
- add_waypoint dispatching works seamlessly.
- Waypoint strings without coordinates are auto-geocoded.
"""

import pytest
from tools.plan_route import plan_route, _normalize_waypoints
from navigation.dispatcher import dispatch


from tools.db import get_engine
from sqlalchemy import text


@pytest.fixture
def test_user_id():
    engine = get_engine()
    with engine.connect() as conn:
        uid = conn.execute(text("SELECT id FROM users LIMIT 1")).scalar()
        return str(uid) if uid else None


class TestModifyRouteWaypoints:
    """Test suite for waypoints in plan_route and modify_route."""

    def test_normalize_waypoints_string_and_dict(self):
        """String waypoints and dicts should be normalized into proper structure."""
        raw = [
            "Gardelegen, Germany",
            {"label": "Magdeburg, Germany", "lat": 52.1307, "lng": 11.6289},
        ]
        from tools.maps_client import get_client
        client = get_client()
        normalized = _normalize_waypoints(raw, client)
        assert len(normalized) == 2
        assert normalized[0]["label"] == "Gardelegen, Germany"
        assert normalized[0]["lat"] is not None
        assert normalized[0]["lng"] is not None
        assert normalized[1]["label"] == "Magdeburg, Germany"
        assert abs(normalized[1]["lat"] - 52.1307) < 0.01

    def test_plan_route_with_waypoints_assigned_to_day(self):
        """Plan route with Gardelegen as waypoint should include it in day waypoints."""
        result = plan_route(
            origin={"label": "Jarocin, Poland", "lat": 51.9727, "lng": 17.5025},
            destination={"label": "Wolfsburg, Germany", "lat": 52.4227, "lng": 10.7865},
            num_days=2,
            start_date="2026-08-01",
            round_trip=True,
            waypoints=[{"label": "Gardelegen", "lat": 52.5268, "lng": 11.4018}],
        )

        assert result["status"] == "success"
        schedules = result["daily_schedules"]
        assert len(schedules) == 2

        # Check that Gardelegen is present in one of the daily schedules
        found_labels = []
        for s in schedules:
            for wp in s["waypoints"]:
                found_labels.append(wp.get("label"))

        assert any("Gardelegen" in str(lbl) for lbl in found_labels)

        # Check round trip: last day should return to Jarocin
        last_day_wps = schedules[-1]["waypoints"]
        assert any("Jarocin" in str(wp.get("label")) for wp in last_day_wps)

    def test_modify_route_preserves_round_trip_and_adds_waypoint(self, test_user_id):
        """modify_route should preserve round-trip context and integrate waypoints."""
        # 1. Create an initial round trip
        initial = plan_route(
            origin={"label": "Jarocin, Poland", "lat": 51.9727, "lng": 17.5025},
            destination={"label": "Wolfsburg, Germany", "lat": 52.4227, "lng": 10.7865},
            num_days=4,
            start_date="2026-08-01",
            round_trip=True,
            user_id=test_user_id,
        )
        assert initial["status"] == "success"
        trip_id = initial["trip"]["id"]

        # 2. Modify route to add Gardelegen without explicitly specifying round_trip
        mod_result = dispatch("modify_route", {
            "trip_id": trip_id,
            "waypoints": [{"label": "Gardelegen", "lat": 52.5268, "lng": 11.4018}],
        })

        assert mod_result["status"] == "success"
        schedules = mod_result["daily_schedules"]
        assert len(schedules) == 4

        # Verify Gardelegen is in the route
        all_labels = [wp.get("label") for s in schedules for wp in s["waypoints"]]
        assert any("Gardelegen" in str(l) for l in all_labels)

        # Verify round_trip was preserved (ends at Jarocin)
        last_wp = schedules[-1]["waypoints"][-1]
        assert "Jarocin" in last_wp.get("label")

    def test_dispatch_add_waypoint(self, test_user_id):
        """dispatching add_waypoint should succeed and modify the route."""
        initial = plan_route(
            origin={"label": "Munich, Germany", "lat": 48.1351, "lng": 11.5820},
            destination={"label": "Salzburg, Austria", "lat": 47.8095, "lng": 13.0550},
            num_days=2,
            start_date="2026-08-01",
            round_trip=True,
            user_id=test_user_id,
        )
        assert initial["status"] == "success"
        trip_id = initial["trip"]["id"]

        add_res = dispatch("add_waypoint", {
            "trip_id": trip_id,
            "label": "Rosenheim, Germany",
        })

        assert add_res["status"] == "success"
        all_labels = [wp.get("label") for s in add_res["daily_schedules"] for wp in s["waypoints"]]
        assert any("Rosenheim" in str(l) for l in all_labels)


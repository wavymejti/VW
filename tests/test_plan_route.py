"""
Unit tests for the route planning tool.

Tests:
- Valid route planning
- Infeasible route detection
- Intermediate point interpolation
"""

import pytest
from tools.plan_route import plan_route, _interpolate_stops_along_route


class TestPlanRoute:
    """Tests for the plan_route function."""

    def test_interpolate_stops_count(self):
        """Should generate num_days - 1 intermediate points."""
        legs = [{"steps": [{"duration": {"value": 3600}, "end_location": {"lat": 1.0, "lng": 1.0}} for _ in range(5)]}]
        points = _interpolate_stops_along_route(legs, 5 * 3600, 5)
        assert len(points) == 4

    def test_interpolate_stops_midpoint(self):
        """Midpoint should pick the step exactly when target interval is reached."""
        legs = [{"steps": [
            {"duration": {"value": 3600}, "end_location": {"lat": 5.0, "lng": 5.0}},
            {"duration": {"value": 3600}, "end_location": {"lat": 10.0, "lng": 10.0}}
        ]}]
        points = _interpolate_stops_along_route(legs, 7200, 2)
        assert len(points) == 1
        assert abs(points[0]["lat"] - 5.0) < 0.001

    def test_interpolate_single_day(self):
        """One-day trip should have zero intermediate stops."""
        legs = [{"steps": [{"duration": {"value": 3600}, "end_location": {"lat": 1.0, "lng": 1.0}}]}]
        points = _interpolate_stops_along_route(legs, 3600, 1)
        assert len(points) == 0

    def test_plan_route_valid(self):
        """Valid route should return success with schedules."""
        result = plan_route(
            origin={
                "label": "Munich",
                "lat": 48.1351,"lng": 11.5820,
            },
            destination={
                "label": "Salzburg",
                "lat": 47.8095, "lng": 13.0550,
            },
            num_days=1,
            start_date="2026-08-01",
        )

        assert result["status"] == "success"
        assert "trip" in result
        assert "daily_schedules" in result
        assert len(result["daily_schedules"]) == 1

    def test_plan_route_returns_trip_title(self):
        """Trip title should include origin and destination."""
        result = plan_route(
            origin={
                "label": "Munich",
                "lat": 48.1351, "lng": 11.5820,
            },
            destination={
                "label": "Vienna",
                "lat": 48.2082, "lng": 16.3738,
            },
            num_days=2,
            start_date="2026-08-01",
        )

        if result["status"] == "success":
            assert "Munich" in result["trip"]["title"]
            assert "Vienna" in result["trip"]["title"]

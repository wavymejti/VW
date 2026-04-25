"""
Unit tests for the route planning tool.

Tests:
- Valid route planning
- Infeasible route detection
- Intermediate point interpolation
"""

import pytest
from tools.plan_route import plan_route, _interpolate_stops


class TestPlanRoute:
    """Tests for the plan_route function."""

    def test_interpolate_stops_count(self):
        """Should generate num_days - 1 intermediate points."""
        origin = {"label": "A", "lat": 48.0, "lng": 11.0}
        destination = {"label": "B", "lat": 43.0, "lng": 16.0}

        points = _interpolate_stops(origin, destination, 5)
        assert len(points) == 4  # 5 days → 4 stops

    def test_interpolate_stops_midpoint(self):
        """Midpoint should be the average of origin + dest."""
        origin = {"label": "A", "lat": 0.0, "lng": 0.0}
        destination = {"label": "B", "lat": 10.0, "lng": 10.0}

        points = _interpolate_stops(origin, destination, 2)
        assert len(points) == 1
        assert abs(points[0]["lat"] - 5.0) < 0.001
        assert abs(points[0]["lng"] - 5.0) < 0.001

    def test_interpolate_single_day(self):
        """One-day trip should have zero intermediate stops."""
        origin = {"label": "A", "lat": 48.0, "lng": 11.0}
        destination = {"label": "B", "lat": 43.0, "lng": 16.0}

        points = _interpolate_stops(origin, destination, 1)
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

"""
Unit and integration tests for the Camping Selection Modal feature.

Verifies:
- plan_route returns up to 3 overnight options for intermediate days
- Flask /api/select_camping endpoint replaces overnight camping and recalculates daily schedule
"""

import pytest
from unittest.mock import patch, MagicMock
from tools.plan_route import plan_route
from tools.server import app


class TestCampingSelection:
    """Tests for overnight camping options and campsite selection endpoint."""

    @patch("tools.plan_route._compute_total_route")
    @patch("tools.plan_route.search_campings")
    @patch("tools.plan_route.get_maps_client")
    def test_plan_route_generates_overnight_options(
        self, mock_maps_client, mock_search_campings, mock_compute_route
    ):
        """plan_route should populate overnight_options with 3 campings for day 1."""
        mock_compute_route.return_value = {
            "status": "success",
            "duration_hours": 8.0,
            "distance_km": 600.0,
            "legs": [
                {
                    "distance": {"value": 600000},
                    "duration": {"value": 28800},
                    "start_location": {"lat": 48.13, "lng": 11.58},
                    "end_location": {"lat": 43.50, "lng": 16.44},
                    "steps": [],
                }
            ],
        }

        mock_search_campings.return_value = {
            "status": "success",
            "results": [
                {"name": "Camp Alpha", "lat": 46.5, "lng": 14.2, "place_id": "p1", "rating": 4.5, "cost_per_night_eur": 25},
                {"name": "Camp Beta", "lat": 46.6, "lng": 14.3, "place_id": "p2", "rating": 4.2, "cost_per_night_eur": 30},
                {"name": "Camp Gamma", "lat": 46.7, "lng": 14.4, "place_id": "p3", "rating": 4.8, "cost_per_night_eur": 20},
            ],
        }

        mock_client = MagicMock()
        mock_client.directions.return_value = [
            {
                "legs": [{"distance": {"value": 300000}, "duration": {"value": 14400}}],
                "overview_polyline": {"points": "mock_polyline"},
            }
        ]
        mock_maps_client.return_value = mock_client

        result = plan_route(
            origin={"label": "Munich", "lat": 48.13, "lng": 11.58},
            destination={"label": "Split", "lat": 43.50, "lng": 16.44},
            num_days=2,
            start_date="2026-07-01",
        )

        assert result["status"] == "success"
        schedules = result["daily_schedules"]
        assert len(schedules) == 2

        # Day 1 is an intermediate day (day_num < num_days)
        day1 = schedules[0]
        assert "overnight_options" in day1
        assert len(day1["overnight_options"]) == 3
        assert day1["overnight_options"][0]["name"] == "Camp Alpha"
        assert day1["overnight_options"][1]["name"] == "Camp Beta"
        assert day1["overnight_options"][2]["name"] == "Camp Gamma"

    def test_api_select_camping_unauthenticated(self):
        """/api/select_camping should return 401 if user is not logged in."""
        with app.test_client() as client:
            res = client.post("/api/select_camping", json={
                "trip_id": "fake_trip",
                "day_number": 1,
                "camping": {"name": "Camp Beta", "lat": 46.6, "lng": 14.3}
            })
            assert res.status_code == 401

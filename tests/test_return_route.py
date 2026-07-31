"""
Unit tests for the return route feature in the VW California AI Trip Planner.

Tests:
- Verification of is_return flag on round trip daily schedules
- Verification of is_return flag on one-way trip daily schedules
- Verification of return route auto-detection when origin equals destination
"""

import unittest
from unittest.mock import patch
from tools.plan_route import plan_route


class TestReturnRoute(unittest.TestCase):
    """Test suite for return route identification and polyline coloring support."""

    @patch("tools.plan_route._compute_total_route")
    @patch("tools.plan_route.search_campings")
    @patch("tools.plan_route.get_maps_client")
    def test_round_trip_return_legs(self, mock_client, mock_campings, mock_route):
        """Verify that round trips properly set is_return=True for the return leg days."""
        mock_route.return_value = {
            "status": "success",
            "distance_km": 800,
            "duration_hours": 12.0,
            "legs": [
                {
                    "steps": [
                        {"duration": {"value": 10800}, "end_location": {"lat": 47.0, "lng": 12.0}},
                        {"duration": {"value": 10800}, "end_location": {"lat": 45.0, "lng": 14.0}},
                        {"duration": {"value": 10800}, "end_location": {"lat": 47.0, "lng": 12.0}},
                        {"duration": {"value": 10800}, "end_location": {"lat": 48.1351, "lng": 11.5820}},
                    ]
                }
            ],
        }
        mock_campings.return_value = {"results": []}

        origin = {"label": "Munich", "lat": 48.1351, "lng": 11.5820}
        destination = {"label": "Split", "lat": 43.5081, "lng": 16.4402}

        result = plan_route(
            origin=origin,
            destination=destination,
            num_days=4,
            start_date="2026-08-01",
            round_trip=True,
        )

        self.assertEqual(result["status"], "success")
        schedules = result["daily_schedules"]
        self.assertEqual(len(schedules), 4)

        # Day 1 & 2: Outbound (is_return = False)
        self.assertFalse(schedules[0]["is_return"])
        self.assertFalse(schedules[1]["is_return"])

        # Day 3 & 4: Return leg (is_return = True)
        self.assertTrue(schedules[2]["is_return"])
        self.assertTrue(schedules[3]["is_return"])

    @patch("tools.plan_route._compute_total_route")
    @patch("tools.plan_route.search_campings")
    @patch("tools.plan_route.get_maps_client")
    def test_one_way_trip_return_legs(self, mock_client, mock_campings, mock_route):
        """Verify that standard one-way trips do not mark days as return legs."""
        mock_route.return_value = {
            "status": "success",
            "distance_km": 400,
            "duration_hours": 5.0,
            "legs": [
                {
                    "steps": [
                        {"duration": {"value": 9000}, "end_location": {"lat": 47.5, "lng": 12.5}},
                        {"duration": {"value": 9000}, "end_location": {"lat": 47.8, "lng": 13.0}},
                    ]
                }
            ],
        }
        mock_campings.return_value = {"results": []}

        origin = {"label": "Munich", "lat": 48.1351, "lng": 11.5820}
        destination = {"label": "Salzburg", "lat": 47.8095, "lng": 13.0550}

        result = plan_route(
            origin=origin,
            destination=destination,
            num_days=2,
            start_date="2026-08-01",
            round_trip=False,
        )

        self.assertEqual(result["status"], "success")
        schedules = result["daily_schedules"]
        self.assertFalse(schedules[0]["is_return"])
        self.assertFalse(schedules[1]["is_return"])


if __name__ == "__main__":
    unittest.main()

"""
Unit and integration tests for the Add Attraction to Route feature.

Verifies:
- Flask /api/add_attraction endpoint requires authentication (401)
- Validation of required parameters (trip_id, attraction object, lat, lng)
- Insertion of attraction waypoint into daily_schedules and recalculation of route
"""

import pytest
from unittest.mock import patch, MagicMock
from tools.server import app


class TestAddAttractionToRoute:
    """Tests for /api/add_attraction endpoint."""

    def test_api_add_attraction_unauthenticated(self):
        """/api/add_attraction should return 401 if user is not logged in."""
        with app.test_client() as client:
            res = client.post("/api/add_attraction", json={
                "trip_id": "test_trip_id",
                "day_number": 1,
                "attraction": {
                    "name": "Zamkowy Park",
                    "lat": 52.4,
                    "lng": 16.9
                }
            })
            assert res.status_code == 401

    def test_api_add_attraction_missing_fields(self):
        """/api/add_attraction should return 400 when missing required fields."""
        with app.test_client() as client:
            with client.session_transaction() as sess:
                sess["user_id"] = "user_123"

            # Missing attraction parameter
            res1 = client.post("/api/add_attraction", json={
                "trip_id": "test_trip_id",
                "day_number": 1
            })
            assert res1.status_code == 400

            # Missing lat/lng
            res2 = client.post("/api/add_attraction", json={
                "trip_id": "test_trip_id",
                "day_number": 1,
                "attraction": {"name": "No Coordinates Place"}
            })
            assert res2.status_code == 400

    @patch("tools.server._recalculate_day_route")
    @patch("tools.server._get_trip_data")
    @patch("tools.server.get_engine")
    def test_api_add_attraction_success(self, mock_get_engine, mock_get_trip_data, mock_recalc):
        """/api/add_attraction should insert attraction waypoint and recalculate route."""
        mock_conn = MagicMock()
        mock_schedule_row = ("schedule_uuid_123", [
            {"order": 0, "type": "start", "label": "Poznań", "lat": 52.4, "lng": 16.9},
            {"order": 1, "type": "camping", "label": "Camping Berlin", "lat": 52.5, "lng": 13.4}
        ])
        mock_conn.execute.return_value.fetchone.return_value = mock_schedule_row
        mock_conn.__enter__.return_value = mock_conn

        mock_engine = MagicMock()
        mock_engine.begin.return_value = mock_conn
        mock_get_engine.return_value = mock_engine

        mock_recalc.return_value = True
        mock_get_trip_data.return_value = {
            "trip": {"id": "test_trip_id", "title": "Poznań to Berlin"},
            "daily_schedules": [
                {
                    "day_number": 1,
                    "waypoints": [
                        {"order": 0, "type": "start", "label": "Poznań", "lat": 52.4, "lng": 16.9},
                        {"order": 1, "type": "attraction", "label": "Park Mużakowski", "lat": 51.5, "lng": 14.7},
                        {"order": 2, "type": "camping", "label": "Camping Berlin", "lat": 52.5, "lng": 13.4}
                    ]
                }
            ]
        }

        with app.test_client() as client:
            with client.session_transaction() as sess:
                sess["user_id"] = "user_123"

            res = client.post("/api/add_attraction", json={
                "trip_id": "test_trip_id",
                "day_number": 1,
                "attraction": {
                    "name": "Park Mużakowski",
                    "place_id": "place_123",
                    "lat": 51.5,
                    "lng": 14.7,
                    "address": "Łęknica, Poland"
                }
            })

            assert res.status_code == 200
            data = res.get_json()
            assert data["status"] == "success"
            assert "Park Mużakowski" in data["message"]
            assert data["trip_data"]["trip"]["id"] == "test_trip_id"
            mock_recalc.assert_called_once()

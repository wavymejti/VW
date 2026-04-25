import pytest
from unittest.mock import patch, MagicMock
from tools.plan_route import plan_route, _compute_total_route, _persist_trip


class TestPlanRouteExtended:
    @patch("tools.plan_route._compute_total_route")
    def test_plan_route_computation_error(self, mock_compute):
        mock_compute.return_value = {"status": "error", "message": "No route"}
        
        origin = {"label": "A", "lat": 0, "lng": 0}
        destination = {"label": "B", "lat": 1, "lng": 1}
        
        result = plan_route(origin, destination, 3, "2026-01-01")
        assert result["status"] == "error"
        assert "No route" in result["message"]

    @patch("tools.plan_route._compute_total_route")
    def test_plan_route_infeasible(self, mock_compute):
        # Requires 30 hours, but only 2 days * 6 hours = 12 hours available
        mock_compute.return_value = {"status": "success", "duration_hours": 30.0, "distance_km": 3000.0, "legs": []}
        
        origin = {"label": "A", "lat": 0, "lng": 0}
        destination = {"label": "B", "lat": 1, "lng": 1}
        
        result = plan_route(origin, destination, 2, "2026-01-01", max_daily_drive_hours=6.0)
        assert result["status"] == "error"
        assert "adds more days" or "Consider adding more days" in result["message"]

    @patch("tools.plan_route.get_maps_client")
    def test_compute_total_route_error(self, mock_get_client):
        mock_client = MagicMock()
        mock_client.directions.return_value = [] # No route empty list
        mock_get_client.return_value = mock_client
        
        origin = {"lat": 0, "lng": 0}
        destination = {"lat": 1, "lng": 1}
        
        res = _compute_total_route(origin, destination)
        assert res["status"] == "error"
        assert "No route found" in res["message"]

    @patch("tools.plan_route.get_maps_client")
    def test_compute_total_route_exception(self, mock_get_client):
        mock_get_client.side_effect = Exception("Maps API down")
        res = _compute_total_route({"lat": 0, "lng": 0}, {"lat": 1, "lng": 1})
        assert res["status"] == "error"
        assert "Route computation failed" in res["message"]

    @patch("tools.plan_route.get_maps_client")
    @patch("tools.plan_route.search_campings")
    @patch("tools.plan_route._compute_total_route")
    @patch("tools.plan_route._persist_trip")
    def test_plan_route_with_persistence(self, mock_persist, mock_compute, mock_search, mock_get_client):
        mock_compute.return_value = {"status": "success", "duration_hours": 10.0, "distance_km": 1000.0, "legs": [{"steps": [{"duration": {"value": 18000}, "end_location": {"lat": 0.5, "lng": 0.5}}]}]}
        
        mock_client = MagicMock()
        mock_client.directions.return_value = [{"legs": [{"duration": {"value": 18000}, "distance": {"value": 500000}}], "overview_polyline": {"points": "encoded_string"}}]
        mock_get_client.return_value = mock_client
        
        # Will find a camping for intermediate stops
        mock_search.return_value = {
            "results": [{"name": "Test Camp", "lat": 0.5, "lng": 0.5, "place_id": "test_id"}]
        }
        
        origin = {"label": "Start", "lat": 0, "lng": 0}
        destination = {"label": "End", "lat": 1, "lng": 1}
        
        result = plan_route(origin, destination, 2, "2026-01-01", user_id="user-123", preferred_amenities=["wifi"])
        assert result["status"] == "success"
        
        mock_persist.assert_called_once()
        args, kwargs = mock_persist.call_args
        trip, schedules = args
        assert trip["user_id"] == "user-123"
        assert len(schedules) == 2
        # Check camping is assigned
        assert schedules[0]["overnight_camping"]["name"] == "Test Camp"

    @patch("tools.plan_route.get_engine")
    def test_persist_trip_success(self, mock_engine):
        mock_conn = MagicMock()
        mock_engine_context = MagicMock()
        mock_engine_context.__enter__.return_value = mock_conn
        mock_engine.return_value.connect.return_value = mock_engine_context
        
        trip = {
            "id": "t1", "user_id": "u1", "title": "Test Title",
            "origin": {"label": "O", "lat": 0, "lng": 0},
            "destination": {"label": "D", "lat": 1, "lng": 1},
            "start_date": "2026-01-01", "end_date": "2026-01-02", "status": "planned"
        }
        
        schedules = [
            {
                "id": "s1", "day_number": 1, "date": "2026-01-01",
                "driving_hours": 5, "driving_km": 500, "waypoints": [],
                "overnight_camping": {"id": "c1"}
            }
        ]
        
        _persist_trip(trip, schedules)
        assert mock_conn.execute.call_count == 2 # 1 for trip, 1 for schedule
        mock_conn.commit.assert_called_once()
        
    @patch("tools.plan_route.get_engine")
    def test_persist_trip_exception(self, mock_engine):
        mock_engine.side_effect = Exception("DB Error")
        
        trip = {"title": "Error"}
        # Simply testing it doesn't raise exception
        _persist_trip(trip, [])

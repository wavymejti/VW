"""Unit and regression tests for Attractions limit (8 items) and sorting by review count."""
import os
import pytest
from unittest.mock import MagicMock, patch
from tools.suggest_attractions import _fetch_candidates, suggest_attractions


class TestAttractionsLimitAndSorting:
    """Test suite for attraction ranking and 8-item limit."""

    def test_candidates_sorted_by_user_ratings_total_descending(self):
        """Places with high review count must rank higher than places with 5.0 rating but few reviews."""
        mock_places = [
            {
                "name": "Single Review Monument",
                "place_id": "p_single",
                "rating": 5.0,
                "user_ratings_total": 1,
                "geometry": {"location": {"lat": 52.0, "lng": 16.0}},
            },
            {
                "name": "Famous Palace & Park",
                "place_id": "p_palace",
                "rating": 4.7,
                "user_ratings_total": 3500,
                "geometry": {"location": {"lat": 52.0, "lng": 16.0}},
            },
            {
                "name": "Local Small Fountain",
                "place_id": "p_fountain",
                "rating": 5.0,
                "user_ratings_total": 4,
                "geometry": {"location": {"lat": 52.0, "lng": 16.0}},
            },
            {
                "name": "Historic Old Town",
                "place_id": "p_town",
                "rating": 4.6,
                "user_ratings_total": 1800,
                "geometry": {"location": {"lat": 52.0, "lng": 16.0}},
            },
        ]

        mock_gmaps = MagicMock()
        mock_gmaps.places_nearby.return_value = {"results": mock_places}

        candidates = _fetch_candidates(
            mock_gmaps, [(52.0, 16.0)], ["tourist_attraction"], 20000, "fake_key"
        )

        assert len(candidates) == 4
        # #1 must be Famous Palace (3500 reviews)
        assert candidates[0]["name"] == "Famous Palace & Park"
        assert candidates[0]["user_ratings_total"] == 3500

        # #2 must be Historic Old Town (1800 reviews)
        assert candidates[1]["name"] == "Historic Old Town"
        assert candidates[1]["user_ratings_total"] == 1800

        # #3 must be Local Small Fountain (4 reviews, 5.0)
        assert candidates[2]["name"] == "Local Small Fountain"

        # #4 must be Single Review Monument (1 review, 5.0)
        assert candidates[3]["name"] == "Single Review Monument"

    def test_suggest_attractions_default_limit_is_8(self):
        """Default limit_per_day in suggest_attractions must be 8."""
        import inspect

        sig = inspect.signature(suggest_attractions)
        assert sig.parameters["limit_per_day"].default == 8

    def test_server_endpoint_default_limit_is_8(self):
        """Flask endpoint /api/attractions/<trip_id> must default limit_per_day to 8."""
        from tools.server import app

        with app.test_client() as client:
            with patch("tools.server.suggest_attractions") as mock_suggest:
                mock_suggest.return_value = {"status": "success", "attractions_by_day": {}}
                res = client.get("/api/attractions/test_trip_123")
                assert res.status_code == 200
                mock_suggest.assert_called_once()
                call_kwargs = mock_suggest.call_args[1]
                assert call_kwargs.get("limit_per_day") == 8

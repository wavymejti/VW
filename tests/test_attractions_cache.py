"""
Unit and integration tests for persistent PostgreSQL attractions caching.

Verifies:
1. Spatial POI caching and retrieval via PostGIS ST_DWithin.
2. Trip-level aggregated cache persistence and retrieval.
3. Fail-safe behavior (graceful fallback on DB errors).
4. Zero external API calls when cached attractions are available.
"""

from unittest.mock import MagicMock, patch
import pytest

from tools.attractions_cache import (
    get_cached_attractions_near,
    save_cached_attractions,
    get_trip_attractions_cache,
    save_trip_attractions_cache,
)
from tools.suggest_attractions import _fetch_candidates


class TestAttractionsCacheUnit:
    """Unit tests with mocking for isolated validation."""

    def test_fail_safe_get_trip_cache_on_error(self):
        """Verify get_trip_attractions_cache returns None gracefully on DB exception."""
        with patch("tools.attractions_cache.get_engine", side_effect=Exception("Database down")):
            result = get_trip_attractions_cache("trip-123", "cache_key_test")
            assert result is None

    def test_fail_safe_save_trip_cache_on_error(self):
        """Verify save_trip_attractions_cache returns False gracefully on DB exception."""
        with patch("tools.attractions_cache.get_engine", side_effect=Exception("Database down")):
            result = save_trip_attractions_cache("trip-123", "cache_key_test", {"status": "ok"})
            assert result is False

    def test_fail_safe_get_cached_near_on_error(self):
        """Verify get_cached_attractions_near returns [] gracefully on DB exception."""
        with patch("tools.attractions_cache.get_engine", side_effect=Exception("Database down")):
            result = get_cached_attractions_near(48.1351, 11.5820, 20000)
            assert result == []

    def test_fail_safe_save_cached_attractions_on_error(self):
        """Verify save_cached_attractions returns 0 gracefully on DB exception."""
        with patch("tools.attractions_cache.get_engine", side_effect=Exception("Database down")):
            result = save_cached_attractions([{"place_id": "p1", "name": "N1", "lat": 48.1, "lng": 11.5}])
            assert result == 0

    def test_spatial_cache_avoids_google_maps_api_calls(self):
        """
        Verify that when sufficient cached POIs exist in the database,
        gmaps.places_nearby is NOT called (0 external API calls).
        """
        mock_gmaps = MagicMock()

        # Mock cached POIs returned from PostGIS
        mock_cached_pois = [
            {
                "place_id": f"cached_poi_{i}",
                "name": f"Cached Attraction {i}",
                "lat": 48.13 + i * 0.01,
                "lng": 11.58 + i * 0.01,
                "rating": 4.8,
                "user_ratings_total": 500 - i * 10,
                "address": f"Street {i}",
                "types": ["tourist_attraction"],
                "category": "tourist_attraction",
                "category_label": "Atrakcja",
                "emoji": "⭐",
                "color": "#F9A825",
                "photo_url": None,
                "google_maps_url": None,
            }
            for i in range(6)
        ]

        with patch("tools.suggest_attractions.get_cached_attractions_near", return_value=mock_cached_pois):
            sample_points = [(48.1351, 11.5820)]
            candidates = _fetch_candidates(
                gmaps=mock_gmaps,
                sample_points=sample_points,
                types_to_search=["tourist_attraction"],
                search_radius_m=20000,
                gmaps_key="dummy_key",
            )

            # Assert: Zero calls to Google Maps Places Nearby
            mock_gmaps.places_nearby.assert_not_called()
            assert len(candidates) == 6
            assert candidates[0]["place_id"] == "cached_poi_0"


class TestAttractionsCacheDatabaseIntegration:
    """Live database tests against PostgreSQL / PostGIS."""

    def test_live_db_save_and_retrieve_trip_cache(self):
        """Test persisting and retrieving trip-level cached JSON."""
        test_trip_id = "00000000-0000-0000-0000-000000000001"
        test_key = "test_trip_cache_key_integration_123"
        payload = {
            "status": "success",
            "trip_id": test_trip_id,
            "attractions_by_day": {
                "1": [{"name": "Test Castle", "place_id": "test_pid_999"}]
            },
        }

        # Save to DB
        ok = save_trip_attractions_cache(test_trip_id, test_key, payload)
        assert ok is True

        # Retrieve from DB
        retrieved = get_trip_attractions_cache(test_trip_id, test_key)
        assert retrieved is not None
        assert retrieved.get("status") == "success"
        assert retrieved.get("trip_id") == test_trip_id
        assert "1" in retrieved.get("attractions_by_day", {})

    def test_live_db_save_and_retrieve_spatial_poi(self):
        """Test persisting POI and retrieving it using PostGIS ST_DWithin."""
        test_place_id = "test_munich_residenz_integration_001"
        sample_item = [{
            "place_id": test_place_id,
            "name": "Munich Residenz (Test)",
            "lat": 48.1412,
            "lng": 11.5786,
            "rating": 4.7,
            "user_ratings_total": 21000,
            "address": "Residenzstraße 1, 80333 München, Germany",
            "types": ["tourist_attraction", "museum"],
            "category": "museum",
            "category_label": "Muzeum",
            "emoji": "🏛️",
            "color": "#5C6BC0",
            "photo_url": "https://example.com/residenz.jpg",
            "google_maps_url": f"https://maps.google.com/?cid={test_place_id}",
        }]

        saved_count = save_cached_attractions(sample_item)
        assert saved_count >= 1

        # Search within 3 km of Munich center (48.1371, 11.5754)
        results = get_cached_attractions_near(
            lat=48.1371,
            lng=11.5754,
            radius_m=3000,
            limit=10,
        )

        assert any(r["place_id"] == test_place_id for r in results)
        matched = next(r for r in results if r["place_id"] == test_place_id)
        assert matched["name"] == "Munich Residenz (Test)"
        assert matched["category_label"] == "Muzeum"

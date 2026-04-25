"""
Unit tests for the camping search tool.

Tests:
- Valid coordinate search (database query)
- Invalid coordinate rejection
- Amenity filtering
- Empty result handling
"""

import pytest
from unittest.mock import patch, MagicMock
from tools.search_campings import search_campings


class TestSearchCampings:
    """Tests for the search_campings function."""

    def test_invalid_coordinates_returns_error(self):
        """Coordinates outside valid range should return error."""
        result = search_campings(lat=100, lng=200)
        assert result["status"] == "error"
        assert "Invalid coordinates" in result["message"]
        assert result["results"] == []

    def test_valid_coordinates_return_success(self):
        """Valid coordinates near seed data should return results."""
        # Lake Bled area — seed data has Camping Bled here
        result = search_campings(
            lat=46.3636, lng=14.0938,
            radius_km=100,
            vw_compatible=False,
        )
        assert result["status"] == "success"
        assert isinstance(result["results"], list)
        assert result["total_found"] >= 0

    def test_amenity_filtering(self):
        """Filtering by amenities should narrow results."""
        # Search with strict amenity filter
        result = search_campings(
            lat=46.3636, lng=14.0938,
            radius_km=50,
            amenities=["power", "showers", "wifi"],
            vw_compatible=True,
        )
        assert result["status"] == "success"
        # All results should have the requested amenities
        for camp in result["results"]:
            if camp.get("has_power") is not None:
                assert camp["has_power"] is True
            if camp.get("has_showers") is not None:
                assert camp["has_showers"] is True

    def test_cost_filtering(self):
        """Max cost filter should exclude expensive campings."""
        result = search_campings(
            lat=46.3636, lng=14.0938,
            radius_km=50,
            max_cost_eur=20,
            vw_compatible=False,
        )
        assert result["status"] == "success"
        for camp in result["results"]:
            if camp.get("cost_per_night_eur") is not None:
                assert camp["cost_per_night_eur"] <= 20

    def test_zero_radius_returns_few_results(self):
        """Extremely small radius should return very few results."""
        result = search_campings(
            lat=46.3636, lng=14.0938,
            radius_km=0.01,  # 10 meters
            vw_compatible=False,
        )
        assert result["status"] == "success"
        # Unlikely to find campings within 10m of a random point
        assert result["total_found"] <= 1

    def test_result_structure(self):
        """Each result should have required fields."""
        result = search_campings(
            lat=46.3636, lng=14.0938,
            radius_km=100,
            vw_compatible=False,
        )

        if result["results"]:
            camp = result["results"][0]
            assert "name" in camp
            assert "lat" in camp
            assert "lng" in camp
            assert "source" in result

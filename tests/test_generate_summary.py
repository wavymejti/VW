"""
Unit tests for the trip summary generator tool.

Tests:
- Summary generation for existing trip
- Non-existent trip handling
- Slideshow output verification
"""

import os
import pytest
from tools.generate_summary import (
    get_trip_summary,
    generate_summary,
    _create_slide,
)


# Seed trip ID from db/seed.sql
SEED_TRIP_ID = "a0000001-0000-0000-0000-000000000001"
FAKE_TRIP_ID = "00000000-0000-0000-0000-000000000000"


class TestGetTripSummary:
    """Tests for fetching trip data."""

    def test_existing_trip(self):
        """Seed trip should return success with data."""
        result = get_trip_summary(SEED_TRIP_ID)
        assert result["status"] == "success"
        assert "trip" in result
        assert "daily_schedules" in result
        assert result["num_days"] == 3

    def test_nonexistent_trip(self):
        """Non-existent trip should return error."""
        result = get_trip_summary(FAKE_TRIP_ID)
        assert result["status"] == "error"
        assert "not found" in result["message"]

    def test_trip_data_fields(self):
        """Trip data should contain expected fields."""
        result = get_trip_summary(SEED_TRIP_ID)
        if result["status"] == "success":
            assert "total_driving_hours" in result
            assert "total_driving_km" in result
            assert "num_photos" in result


class TestCreateSlide:
    """Tests for slide image generation."""

    def test_slide_dimensions(self):
        """Slide should have correct dimensions."""
        slide = _create_slide("Test Title", width=1200, height=675)
        assert slide.size == (1200, 675)

    def test_custom_dimensions(self):
        """Custom dimensions should be respected."""
        slide = _create_slide("Test", width=800, height=400)
        assert slide.size == (800, 400)

    def test_slide_is_image(self):
        """Slide should be a PIL Image instance."""
        from PIL import Image
        slide = _create_slide("Test")
        assert isinstance(slide, Image.Image)


class TestGenerateSummary:
    """Tests for full summary generation."""

    def test_slideshow_generation(self):
        """Slideshow for seed trip should succeed."""
        result = generate_summary(
            SEED_TRIP_ID, format="image_slideshow"
        )
        assert result["status"] == "success"
        assert "file_url" in result
        # File should exist on disk
        assert os.path.exists(result["file_url"])

    def test_invalid_format(self):
        """Invalid format should return error."""
        result = generate_summary(
            SEED_TRIP_ID, format="invalid_format"
        )
        assert result["status"] == "error"
        assert "Unsupported format" in result["message"]

    def test_nonexistent_trip_summary(self):
        """Summary for non-existent trip should fail."""
        result = generate_summary(FAKE_TRIP_ID)
        assert result["status"] == "error"

"""
Unit tests for the EXIF extraction tool.

Tests:
- Supported format validation
- File not found handling
- DMS to decimal conversion
- Datetime parsing
"""

import os
import pytest
from unittest.mock import patch
from tools.extract_exif import (
    extract_exif,
    _dms_to_decimal,
    _parse_datetime,
    _empty_metadata,
    SUPPORTED_FORMATS,
)


class TestDmsToDecimal:
    """Tests for DMS to Decimal Degrees conversion."""

    def test_north_east(self):
        """North/East coordinates should be positive."""
        # 46° 21' 27.36" N
        lat = _dms_to_decimal((46, 21, 27.36), "N")
        assert abs(lat - 46.35760) < 0.001

    def test_south_west(self):
        """South/West coordinates should be negative."""
        lat = _dms_to_decimal((33, 51, 54), "S")
        assert lat < 0
        assert abs(lat + 33.865) < 0.001

    def test_zero_coordinates(self):
        """0°0'0" should return 0.0."""
        result = _dms_to_decimal((0, 0, 0), "N")
        assert result == 0.0

    def test_max_longitude(self):
        """180° should be valid."""
        result = _dms_to_decimal((180, 0, 0), "E")
        assert result == 180.0


class TestParseDatetime:
    """Tests for EXIF datetime parsing."""

    def test_valid_datetime(self):
        """Standard EXIF datetime should parse correctly."""
        result = _parse_datetime("2026:06:15 14:30:00")
        assert result == "2026-06-15T14:30:00"

    def test_none_input(self):
        """None input should return None."""
        result = _parse_datetime(None)
        assert result is None

    def test_invalid_format(self):
        """Invalid format should return None."""
        result = _parse_datetime("not-a-date")
        assert result is None

    def test_empty_string(self):
        """Empty string should return None."""
        result = _parse_datetime("")
        assert result is None


class TestExtractExif:
    """Tests for the main extract_exif function."""

    def test_file_not_found(self):
        """Non-existent file should return error."""
        result = extract_exif("/nonexistent/photo.jpg")
        assert result["status"] == "error"
        assert "not found" in result["message"]

    def test_unsupported_format(self):
        """Unsupported file extension should return error."""
        # Create a temp file with unsupported extension
        tmp_path = os.path.join(
            os.path.dirname(os.path.abspath(__file__)),
            "test_file.mp3",
        )
        try:
            with open(tmp_path, "w") as f:
                f.write("fake")
            result = extract_exif(tmp_path)
            assert result["status"] == "error"
            assert "Unsupported format" in result["message"]
        finally:
            os.remove(tmp_path)

    def test_empty_metadata_structure(self):
        """Empty metadata should contain all expected keys."""
        metadata = _empty_metadata("/path/to/photo.jpg")
        expected_keys = [
            "lat", "lng", "captured_at",
            "camera_make", "camera_model",
            "orientation", "original_filename",
        ]
        for key in expected_keys:
            assert key in metadata
        assert metadata["original_filename"] == "photo.jpg"

    def test_supported_formats_set(self):
        """SUPPORTED_FORMATS should contain common image types."""
        assert ".jpg" in SUPPORTED_FORMATS
        assert ".jpeg" in SUPPORTED_FORMATS
        assert ".png" in SUPPORTED_FORMATS

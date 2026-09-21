"""
Unit and integration tests for Poznań -> Warszawa mock trip photos.

Verifies:
- All 8 curated photo locations along Poznań -> Warszawa route.
- Correct date constraints (11.09.2026 - 14.09.2026).
- Valid EXIF extraction with GPS coordinates and timestamps.
- Brand camera metadata (Volkswagen California).
"""

import os
from datetime import datetime
import pytest

from tools.mock_trip_photos import (
    get_poznan_warszawa_photos_metadata,
    generate_poznan_warszawa_mock_photos,
)
from tools.extract_exif import extract_exif


def test_photos_metadata_structure_and_dates():
    """Verify that metadata contains 8 stops with dates strictly in 11.09 - 14.09.2026."""
    photos = get_poznan_warszawa_photos_metadata()
    assert len(photos) == 8, f"Expected 8 photos, found {len(photos)}"

    start_bound = datetime(2026, 9, 11, 0, 0, 0)
    end_bound = datetime(2026, 9, 14, 23, 59, 59)

    prev_lng = 16.0  # West of Poznań

    for p in photos:
        # Check required fields
        assert "filename" in p
        assert "lat" in p and "lng" in p
        assert "date_str" in p
        assert "day_number" in p
        assert 1 <= p["day_number"] <= 4

        # Check date within range
        dt = datetime.strptime(p["date_str"], "%Y-%m-%d %H:%M:%S")
        assert start_bound <= dt <= end_bound, f"Date {dt} out of 11-14.09.2026 range"

        # Check west-to-east route progression (Poznań ~16.9°E -> Warszawa ~21.0°E)
        assert p["lng"] >= prev_lng - 0.5, "Route longitude progression unexpected"
        prev_lng = p["lng"]


def test_generate_and_extract_exif_mock_photos(tmp_path):
    """Verify photo generation and ensure EXIF parser reads GPS & timestamps cleanly."""
    target_dir = str(tmp_path / "test_photos")
    results = generate_poznan_warszawa_mock_photos(
        primary_dir=target_dir,
        also_copy_to_root=False,
        verbose=False,
    )

    assert len(results) == 8

    for res in results:
        assert res["exif_status"] == "success"
        assert res["lat"] is not None
        assert res["lng"] is not None
        assert res["captured_at"] is not None
        assert res["camera_make"] == "Volkswagen"
        assert "California" in res["camera_model"]

        # Validate file on disk
        assert os.path.exists(res["filepath"])
        assert os.path.getsize(res["filepath"]) > 20000  # At least 20 KB

        # Re-extract independently
        extracted = extract_exif(res["filepath"])
        assert extracted["status"] == "success"
        meta = extracted["metadata"]
        assert round(meta["lat"], 2) == round(res["lat"], 2)
        assert round(meta["lng"], 2) == round(res["lng"], 2)

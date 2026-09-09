"""
Unit and integration tests for photo date/day editing, polyline lookahead, and trip dates.
"""

import math
from datetime import date, datetime, timedelta
import pytest
from tools.generate_summary import _interpolate_polyline_point
from tools.extract_exif import pin_photo_location
from tools.db import get_engine
from sqlalchemy import text


class TestPolylineInterpolationAndHeading:
    """Test geometric interpolation and circular angle heading smoothing."""

    def test_interpolate_polyline_point(self):
        points = [(50.0, 10.0), (50.0, 11.0), (51.0, 11.0)]
        distances = [0.0, 1000.0, 2000.0]

        # At start
        lat, lng, seg = _interpolate_polyline_point(points, distances, 0.0)
        assert lat == 50.0 and lng == 10.0

        # Halfway first segment
        lat, lng, seg = _interpolate_polyline_point(points, distances, 500.0)
        assert lat == 50.0 and lng == 10.5
        assert seg == 0

        # Halfway second segment
        lat, lng, seg = _interpolate_polyline_point(points, distances, 1500.0)
        assert lat == 50.5 and lng == 11.0
        assert seg == 1

        # Beyond end
        lat, lng, seg = _interpolate_polyline_point(points, distances, 2500.0)
        assert lat == 51.0 and lng == 11.0

    def test_circular_angle_difference(self):
        """Angle difference across 0/360 boundary must wrap correctly."""
        angle1 = 355.0
        angle2 = 5.0
        diff = (angle2 - angle1 + 180.0) % 360.0 - 180.0
        assert abs(diff - 10.0) < 1e-6

        angle1 = 10.0
        angle2 = 350.0
        diff = (angle2 - angle1 + 180.0) % 360.0 - 180.0
        assert abs(diff - (-20.0)) < 1e-6


class TestPinPhotoLocationWithDate:
    """Test updating photo location, date, and schedule day in database."""

    def test_pin_photo_location_fields(self):
        engine = get_engine()
        with engine.connect() as conn:
            p_row = conn.execute(
                text("SELECT id, user_id, trip_id FROM photos WHERE trip_id IS NOT NULL LIMIT 1")
            ).fetchone()

        if not p_row:
            pytest.skip("No photos with trip_id in database")

        photo_id = str(p_row[0])
        user_id = str(p_row[1])
        trip_id = str(p_row[2])

        res = pin_photo_location(
            photo_id=photo_id,
            lat=52.4064,
            lng=16.9252,
            user_id=user_id,
            captured_at="2026-09-09",
            day_number=1,
            trip_id=trip_id,
        )

        assert res["status"] == "success"
        assert res["photo_id"] == photo_id
        assert abs(res["lat"] - 52.4064) < 1e-4
        assert abs(res["lng"] - 16.9252) < 1e-4
        assert "2026-09-09" in res["captured_at"]
        assert res["day_number"] == 1
        assert res["linked"] is True

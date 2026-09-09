"""
Unit tests for interactive photo stop animations on route:
- Projection of photo coordinates onto polyline route
- Pulsing pin indicator animation frames
- Pop-up zoom and pop-down return photo card frames
"""

import os
import pytest
from PIL import Image
from tools.generate_summary import (
    _project_photo_to_route,
    _render_pin_pulse_frame,
    _render_photo_popup_frame,
    _interpolate_polyline_point,
)


class TestPhotoProjection:
    """Tests for projecting photo coordinates onto a polyline route."""

    def test_exact_and_near_projection(self):
        # A simple 3-point polyline along latitude
        points = [(52.0, 16.0), (52.0, 17.0), (52.0, 18.0)]
        distances = [0.0, 100000.0, 200000.0]
        total_dist = 200000.0

        # Photo exactly midway between point 0 and 1
        photo_mid = {"lat": 52.0, "lng": 16.5}
        dist, prog, coords = _project_photo_to_route(photo_mid, points, distances, total_dist)
        assert abs(prog - 0.25) < 0.05
        assert abs(dist - 50000.0) < 10000.0
        assert coords == (52.0, 16.5)

    def test_missing_coordinates_fallback(self):
        points = [(52.0, 16.0), (52.0, 17.0)]
        distances = [0.0, 100000.0]
        total_dist = 100000.0

        photo_no_coords = {"lat": None, "lng": None}
        dist, prog, coords = _project_photo_to_route(photo_no_coords, points, distances, total_dist)
        assert prog == 0.98
        assert dist == total_dist * 0.98


class TestPhotoAnimationFrames:
    """Tests for rendering individual animation frames."""

    def test_pin_pulse_frame_rendering(self):
        base_img = Image.new("RGB", (1280, 720), (0, 14, 38))
        pin_xy = (640, 360)

        frame = _render_pin_pulse_frame(base_img, pin_xy, pulse_ratio=0.5)
        assert frame is not None
        assert frame.size == (1280, 720)
        assert frame.mode == "RGB"

    def test_photo_popup_and_return_frames(self):
        base_img = Image.new("RGB", (1280, 720), (0, 14, 38))
        pin_xy = (300, 400)

        # Forward pop-up frame
        popup_frame = _render_photo_popup_frame(
            base_frame=base_img,
            photo_path=None,
            pin_xy=pin_xy,
            progress=0.75,
            day_number=1,
            schedule_date="2026-09-09",
            caption="Test Memory",
            reverse=False,
        )
        assert popup_frame is not None
        assert popup_frame.size == (1280, 720)

        # Return pop-down frame
        return_frame = _render_photo_popup_frame(
            base_frame=base_img,
            photo_path=None,
            pin_xy=pin_xy,
            progress=0.75,
            day_number=1,
            schedule_date="2026-09-09",
            caption="Test Memory",
            reverse=True,
        )
        assert return_frame is not None
        assert return_frame.size == (1280, 720)

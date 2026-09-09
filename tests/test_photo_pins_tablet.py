"""
Unit and integration tests for tablet photo pins loading, CORS headers,
on-demand thumbnail generation, and map pinning functionality.
"""

import os
import sys
import pytest
from PIL import Image

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from tools.server import app


@pytest.fixture
def client():
    app.config["TESTING"] = True
    with app.test_client() as client:
        yield client


def test_serve_photo_file_cors_options(client):
    """Ensure OPTIONS requests return 204 with CORS headers for ngrok/tablet preflight."""
    res = client.open("/photos/file/test_photo.jpg", method="OPTIONS")
    assert res.status_code == 204
    assert res.headers.get("Access-Control-Allow-Origin") == "*"
    assert "GET" in res.headers.get("Access-Control-Allow-Methods", "")


def test_serve_photo_file_existing_image_headers(client):
    """Ensure existing image responses have CORS and Cache-Control headers."""
    tmp_dir = os.path.join(ROOT, ".tmp")
    os.makedirs(tmp_dir, exist_ok=True)
    test_img_path = os.path.join(tmp_dir, "test_tablet_pin.jpg")
    if not os.path.exists(test_img_path):
        im = Image.new("RGB", (200, 200), color=(0, 30, 80))
        im.save(test_img_path, "JPEG")

    res = client.get("/photos/file/test_tablet_pin.jpg")
    assert res.status_code == 200
    assert res.headers.get("Access-Control-Allow-Origin") == "*"
    assert "public" in res.headers.get("Cache-Control", "")


def test_serve_photo_file_on_demand_thumbnail(client):
    """Ensure requesting a missing thumbnail auto-generates it and serves with 200."""
    tmp_dir = os.path.join(ROOT, ".tmp")
    uploads_dir = os.path.join(tmp_dir, "uploads")
    os.makedirs(uploads_dir, exist_ok=True)

    base_name = "test_ondemand_sample"
    orig_path = os.path.join(uploads_dir, f"{base_name}.jpg")
    thumb_path = os.path.join(tmp_dir, f"{base_name}_thumb.jpg")

    if os.path.exists(thumb_path):
        os.remove(thumb_path)

    im = Image.new("RGB", (800, 600), color=(10, 100, 200))
    im.save(orig_path, "JPEG")

    # Request the thumbnail
    res = client.get(f"/photos/file/{base_name}_thumb.jpg")
    assert res.status_code == 200
    assert res.headers.get("Access-Control-Allow-Origin") == "*"
    assert os.path.exists(thumb_path)


def test_serve_photo_file_404_cors(client):
    """Ensure 404 responses include CORS header so client scripts don't fail with CORS error."""
    res = client.get("/photos/file/non_existent_image_123456.jpg")
    assert res.status_code == 404
    assert res.headers.get("Access-Control-Allow-Origin") == "*"


def test_frontend_app_js_photo_pin_optimizations():
    """Verify that frontend/app.js contains thumbnail resolution, retina DPI, and manual pinning mode."""
    app_js_path = os.path.join(ROOT, "frontend", "app.js")
    with open(app_js_path, "r", encoding="utf-8") as f:
        content = f.read()

    assert "function startPinningPhotoOnMap(" in content
    assert "window.startPinningPhotoOnMap = startPinningPhotoOnMap;" in content
    assert "const dpr = Math.min(window.devicePixelRatio || 2, 2);" in content
    assert "thumbUrl" in content
    assert "scaledSize: new google.maps.Size(48, 56)" in content
    assert "anchor: new google.maps.Point(24, 54)" in content


def test_frontend_styles_pin_photo_overlay():
    """Verify that frontend/styles.css contains elevated z-index and touch-friendly overlay styles."""
    styles_css_path = os.path.join(ROOT, "frontend", "styles.css")
    with open(styles_css_path, "r", encoding="utf-8") as f:
        content = f.read()

    assert ".pin-photo-overlay" in content
    assert "z-index: 100 !important;" in content
    assert ".pin-photo-banner" in content

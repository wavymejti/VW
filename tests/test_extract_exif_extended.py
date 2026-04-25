import os
import pytest
from unittest.mock import patch, MagicMock
from tools.extract_exif import (
    extract_exif,
    _parse_gps,
    generate_thumbnail,
    store_photo,
    MAX_FILE_SIZE_BYTES
)


class TestExtractExifFunction:
    @patch("os.path.getsize")
    @patch("os.path.exists")
    def test_file_too_large(self, mock_exists, mock_getsize):
        mock_exists.return_value = True
        mock_getsize.return_value = MAX_FILE_SIZE_BYTES + 1
        
        result = extract_exif("dummy.jpg")
        assert result["status"] == "error"
        assert "too large" in result["message"]

    @patch("tools.extract_exif.Image.open")
    @patch("os.path.getsize")
    @patch("os.path.exists")
    def test_no_exif_data(self, mock_exists, mock_getsize, mock_image_open):
        mock_exists.return_value = True
        mock_getsize.return_value = 1000
        
        mock_img_instance = MagicMock()
        mock_img_instance._getexif.return_value = None
        mock_image_open.return_value = mock_img_instance
        
        result = extract_exif("dummy.jpg")
        assert result["status"] == "warning"
        assert "No EXIF data found" in result["message"]
        assert result["metadata"]["original_filename"] == "dummy.jpg"

    @patch("tools.extract_exif.Image.open")
    @patch("os.path.getsize")
    @patch("os.path.exists")
    def test_with_exif_gps_data(self, mock_exists, mock_getsize, mock_image_open):
        mock_exists.return_value = True
        mock_getsize.return_value = 1000
        
        mock_img_instance = MagicMock()
        
        # 34853 is GPSInfo tag.
        # Let's mock the keys returned. But we need GPSTAGS mapping.
        # Actually _parse_gps takes the dict.
        mock_img_instance._getexif.return_value = {
            34853: {
                2: (46.0, 21.0, 27.36), # GPSLatitude
                1: 'N',                 # GPSLatitudeRef
                4: (14.0, 5.0, 30.0),   # GPSLongitude
                3: 'E',                 # GPSLongitudeRef
            },
            306: "2026:06:15 14:30:00", # DateTime
            271: "TestMake", # Make
            272: "TestModel", # Model
        }
        mock_image_open.return_value = mock_img_instance
        
        result = extract_exif("dummy.jpg")
        assert result["status"] == "success"
        meta = result["metadata"]
        assert meta["camera_make"] == "TestMake"
        assert meta["camera_model"] == "TestModel"
        assert abs(meta["lat"] - 46.3576000) < 0.001

    @patch("tools.extract_exif.Image.open")
    @patch("os.path.getsize")
    @patch("os.path.exists")
    def test_extract_exif_exception(self, mock_exists, mock_getsize, mock_image_open):
        mock_exists.return_value = True
        mock_getsize.return_value = 1000
        mock_image_open.side_effect = Exception("Mocked exception")
        
        result = extract_exif("dummy.jpg")
        assert result["status"] == "error"
        assert "Failed to extract EXIF: Mocked exception" in result["message"]


class TestParseGps:
    def test_empty_gps_info(self):
        assert _parse_gps(None) == (None, None)
        assert _parse_gps({}) == (None, None)

    def test_missing_lat_lng(self):
        # GPSTAGS maps 2 to GPSLatitude, etc. We just provide some invalid tags
        assert _parse_gps({"invalid": "data"}) == (None, None)

    def test_out_of_range_coordinates(self):
        # 2: GPSLatitude, 4: GPSLongitude
        gps_info = {
            2: ((100, 1), (0, 1), (0, 1)), # Lat 100 (out of range)
            1: 'N',
            4: ((0, 1), (0, 1), (0, 1)),
            3: 'E'
        }
        assert _parse_gps(gps_info) == (None, None)

    def test_invalid_type(self):
        gps_info = {
            2: "Not a tuple",
            1: 'N',
            4: "Not a tuple",
            3: 'E'
        }
        assert _parse_gps(gps_info) == (None, None)


class TestGenerateThumbnail:
    @patch("tools.extract_exif.Image.open")
    @patch("os.makedirs")
    def test_generate_thumbnail_success(self, mock_makedirs, mock_image_open):
        mock_img = MagicMock()
        mock_img.size = (800, 600)
        
        mock_resized_img = MagicMock()
        mock_img.resize.return_value = mock_resized_img
        
        mock_image_open.return_value = mock_img
        
        res = generate_thumbnail("path/to/image.jpg")
        assert res is not None
        assert res.endswith("image_thumb.jpg")
        mock_resized_img.save.assert_called_once()
        mock_img.resize.assert_called_once()

    @patch("tools.extract_exif.Image.open")
    def test_generate_thumbnail_exception(self, mock_image_open):
        mock_image_open.side_effect = Exception("Mock thumbnail error")
        res = generate_thumbnail("image.jpg")
        assert res is None


class TestStorePhoto:
    @patch("tools.extract_exif.get_engine")
    @patch("tools.extract_exif.generate_thumbnail")
    @patch("tools.extract_exif.extract_exif")
    def test_store_photo_success(self, mock_extract, mock_thumbnail, mock_engine):
        mock_extract.return_value = {
            "status": "success",
            "message": "OK",
            "metadata": {
                "lat": 10.0, "lng": 20.0,
                "captured_at": "2026-01-01",
                "camera_make": "A", "camera_model": "B",
                "orientation": 1,
                "original_filename": "test.jpg"
            }
        }
        mock_thumbnail.return_value = "test_thumb.jpg"
        
        mock_conn = MagicMock()
        mock_engine_context = MagicMock()
        mock_engine_context.__enter__.return_value = mock_conn
        mock_engine.return_value.connect.return_value = mock_engine_context
        
        result = store_photo("test.jpg", "user123")
        assert result["status"] == "success"
        assert result["photo"]["file_url"] == "test.jpg"
        assert result["photo"]["lat"] == 10.0
        
        mock_conn.execute.assert_called_once()
        mock_conn.commit.assert_called_once()
    
    @patch("tools.extract_exif.get_engine")
    @patch("tools.extract_exif.generate_thumbnail")
    @patch("tools.extract_exif.extract_exif")
    def test_store_photo_db_exception(self, mock_extract, mock_thumbnail, mock_engine):
        mock_extract.return_value = {"status": "success", "metadata": {}}
        mock_thumbnail.return_value = "test_thumb.jpg"
        
        mock_engine.side_effect = Exception("DB Error")
        
        # Exception should be caught and printed, not crashing
        result = store_photo("test.jpg", "user123")
        assert result["status"] == "success"

"""
Unit and integration tests for Audius streaming service and video soundtrack integration.
"""

import os
import unittest
from unittest.mock import patch, MagicMock
from flask import Flask

from tools import audius_service
from tools.generate_summary import _resolve_music_track
from tools.server import app


class TestAudiusService(unittest.TestCase):
    """Test suite for tools.audius_service functions."""

    def test_format_seconds(self):
        """Test formatting of seconds into MM:SS string."""
        self.assertEqual(audius_service._format_seconds(0), "0:00")
        self.assertEqual(audius_service._format_seconds(38), "0:38")
        self.assertEqual(audius_service._format_seconds(65), "1:05")
        self.assertEqual(audius_service._format_seconds(185), "3:05")

    def test_format_track(self):
        """Test conversion of raw Audius JSON track to normalized schema."""
        raw_track = {
            "id": "trk12345",
            "title": "Roadtrip Sunshine",
            "user": {"name": "VW Camper", "handle": "vw_camper"},
            "duration": 182,
            "genre": "Lo-Fi",
            "artwork": {
                "150x150": "https://audius.co/art_150.jpg",
                "480x480": "https://audius.co/art_480.jpg",
            },
        }
        host = "https://discoveryprovider.audius.co"
        formatted = audius_service._format_track(raw_track, host)

        self.assertEqual(formatted["id"], "audius:trk12345")
        self.assertEqual(formatted["track_id"], "trk12345")
        self.assertEqual(formatted["title"], "Roadtrip Sunshine")
        self.assertEqual(formatted["artist"], "VW Camper")
        self.assertEqual(formatted["duration"], 182)
        self.assertEqual(formatted["formatted_duration"], "3:02")
        self.assertEqual(formatted["genre"], "Lo-Fi")
        self.assertEqual(formatted["artwork_url"], "https://audius.co/art_480.jpg")
        self.assertIn("trk12345/stream", formatted["stream_url"])
        self.assertEqual(formatted["source"], "audius")

    def test_get_mood_tracks_offline(self):
        """Test retrieval of offline fallback procedural tracks."""
        result = audius_service.get_mood_tracks("offline")
        self.assertEqual(result["mood"], "offline")
        self.assertIn("Offline", result["label"])
        self.assertGreaterEqual(len(result["tracks"]), 5)
        first = result["tracks"][0]
        self.assertEqual(first["source"], "local")
        self.assertTrue(first["track_id"].startswith("vanlife_") or first["track_id"].startswith("acoustic_"))

    def test_get_mood_presets_exist(self):
        """Verify all planned mood presets exist in dictionary."""
        expected_moods = ["roadtrip", "lofi", "acoustic", "nature", "summer", "jazz"]
        for m in expected_moods:
            self.assertIn(m, audius_service.MOOD_PRESETS)
            self.assertIn("query", audius_service.MOOD_PRESETS[m])
            self.assertIn("label", audius_service.MOOD_PRESETS[m])

    @patch("tools.audius_service.requests.get")
    def test_search_tracks_mocked(self, mock_get):
        """Test searching tracks with mocked HTTP response."""
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "data": [
                {
                    "id": "t1",
                    "title": "Sunset Drive",
                    "user": {"name": "DJ Camper"},
                    "duration": 150,
                    "genre": "Chillout",
                },
                {
                    "id": "t2",
                    "title": "Too Short",
                    "duration": 10,  # Should be filtered out (< 20s)
                },
                {
                    "id": "t3",
                    "title": "Deleted Track",
                    "is_delete": True,  # Should be filtered out
                    "duration": 180,
                },
            ]
        }
        mock_get.return_value = mock_resp

        results = audius_service.search_tracks("sunset")
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["id"], "audius:t1")
        self.assertEqual(results[0]["title"], "Sunset Drive")

    def test_download_and_cache_track_local(self):
        """Test resolving local procedural track via download_and_cache_track."""
        path = audius_service.download_and_cache_track("vanlife_chill")
        self.assertIsNotNone(path)
        self.assertTrue(os.path.exists(path))
        self.assertTrue(path.endswith("vanlife_chill.mp3"))

    def test_download_and_cache_track_cached(self):
        """Test that already cached MP3 files are returned directly."""
        os.makedirs(audius_service.CACHE_DIR, exist_ok=True)
        fake_id = "test_cache_track_999"
        cache_file = os.path.join(audius_service.CACHE_DIR, f"audius_{fake_id}.mp3")

        # Create dummy cache file > 100KB
        with open(cache_file, "wb") as f:
            f.write(b"0" * 120_000)

        try:
            resolved = audius_service.download_and_cache_track(f"audius:{fake_id}")
            self.assertEqual(resolved, cache_file)
        finally:
            if os.path.exists(cache_file):
                os.remove(cache_file)

    def test_resolve_music_track_in_generate_summary(self):
        """Test _resolve_music_track integration with audius prefix and offline fallback."""
        # Offline track
        path = _resolve_music_track("vanlife_chill")
        self.assertIsNotNone(path)
        self.assertTrue(os.path.exists(path))

        # None / none
        self.assertIsNone(_resolve_music_track(None))
        self.assertIsNone(_resolve_music_track("none"))


class TestServerMusicEndpoints(unittest.TestCase):
    """Test suite for server Flask endpoints related to music."""

    def setUp(self):
        self.client = app.test_client()

    def test_api_music_moods_endpoint(self):
        """Test GET /api/music/moods."""
        resp = self.client.get("/api/music/moods?mood=offline")
        self.assertEqual(resp.status_code, 200)
        data = resp.get_json()
        self.assertEqual(data["status"], "success")
        self.assertIn("presets", data)
        self.assertIn("current_mood", data)
        self.assertEqual(data["current_mood"]["mood"], "offline")

    def test_api_music_search_endpoint_empty(self):
        """Test GET /api/music/search with empty query."""
        resp = self.client.get("/api/music/search?q=")
        self.assertEqual(resp.status_code, 200)
        data = resp.get_json()
        self.assertEqual(data["status"], "success")
        self.assertEqual(data["tracks"], [])


if __name__ == "__main__":
    unittest.main()

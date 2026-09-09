"""
Unit and integration tests for User Geolocation and Chat Location Awareness.

Tests coordinate sanitization, reverse geocoding fallback and mocked Google Maps,
prompt formatting in PL, DE, EN, and Flask REST API endpoints (/api/location/reverse, /api/chat).
"""

import json
import unittest
from unittest.mock import MagicMock, patch

from tools.location_service import (
    sanitize_coordinates,
    reverse_geocode_coordinates,
    format_location_for_prompt,
)
from tools.server import app


class TestLocationService(unittest.TestCase):
    """Test suite for location_service module and location-aware chat API."""

    def test_sanitize_coordinates(self):
        """Verify coordinate sanitization and bounds checking."""
        # Valid cases
        self.assertEqual(sanitize_coordinates(52.406374, 16.925168), (52.406374, 16.925168))
        self.assertEqual(sanitize_coordinates("52.406374", "16.925168"), (52.406374, 16.925168))
        self.assertEqual(sanitize_coordinates(-33.8688, 151.2093), (-33.8688, 151.2093))
        self.assertEqual(sanitize_coordinates(0, 0), (0.0, 0.0))

        # Invalid cases
        self.assertIsNone(sanitize_coordinates(None, 16.0))
        self.assertIsNone(sanitize_coordinates(52.0, None))
        self.assertIsNone(sanitize_coordinates("invalid", 16.0))
        self.assertIsNone(sanitize_coordinates(91.0, 16.0))  # Lat > 90
        self.assertIsNone(sanitize_coordinates(-95.0, 16.0))  # Lat < -90
        self.assertIsNone(sanitize_coordinates(52.0, 185.0))  # Lng > 180
        self.assertIsNone(sanitize_coordinates(52.0, -190.0))  # Lng < -180

    def test_reverse_geocode_fallback_on_error(self):
        """Verify graceful fallback when Google Maps API raises an exception."""
        with patch("tools.maps_client.get_client", side_effect=RuntimeError("API offline")):
            res = reverse_geocode_coordinates(52.4064, 16.9252, lang="pl")
            self.assertEqual(res["status"], "fallback")
            self.assertEqual(res["lat"], 52.4064)
            self.assertEqual(res["lng"], 16.9252)
            self.assertIn("°N", res["name"])
            self.assertIn("°E", res["name"])

    def test_reverse_geocode_mocked_success(self):
        """Verify reverse geocoding with a mocked Google Maps response."""
        mock_client = MagicMock()
        mock_client.reverse_geocode.return_value = [
            {
                "formatted_address": "Stary Rynek, 61-772 Poznań, Polska",
                "address_components": [
                    {"long_name": "Poznań", "types": ["locality", "political"]},
                    {"long_name": "Wielkopolskie", "types": ["administrative_area_level_1"]},
                    {"long_name": "Polska", "types": ["country", "political"]},
                ],
            }
        ]

        with patch("tools.maps_client.get_client", return_value=mock_client):
            res = reverse_geocode_coordinates(52.4064, 16.9252, lang="pl")
            self.assertEqual(res["status"], "success")
            self.assertEqual(res["city"], "Poznań")
            self.assertEqual(res["country"], "Polska")
            self.assertEqual(res["name"], "Poznań, Polska")
            self.assertIn("Poznań", res["address"])

    def test_format_location_for_prompt_languages(self):
        """Verify system prompt generation across Polish, German, and English."""
        loc_data = {
            "lat": 52.4064,
            "lng": 16.9252,
            "name": "Poznań, Polska",
            "city": "Poznań",
        }

        # Polish
        prompt_pl = format_location_for_prompt(loc_data, lang="pl")
        self.assertIn("[SYSTEM NOTE] User Current Location: Poznań, Polska", prompt_pl)
        self.assertIn("VW California", prompt_pl)
        self.assertIn("kempingi", prompt_pl)
        self.assertIn("origin", prompt_pl)

        # German
        prompt_de = format_location_for_prompt(loc_data, lang="de")
        self.assertIn("[SYSTEM NOTE] User Current Location: Poznań, Polska", prompt_de)
        self.assertIn("Standort", prompt_de)
        self.assertIn("Campingplätzen", prompt_de)

        # English
        prompt_en = format_location_for_prompt(loc_data, lang="en")
        self.assertIn("[SYSTEM NOTE] User Current Location: Poznań, Polska", prompt_en)
        self.assertIn("campervan", prompt_en)
        self.assertIn("campsites", prompt_en)

    def test_api_reverse_location_endpoint(self):
        """Verify POST /api/location/reverse returns status and data."""
        client = app.test_client()

        # Valid request (with fallback or mocked response)
        resp = client.post(
            "/api/location/reverse",
            data=json.dumps({"lat": 48.1351, "lng": 11.5820, "lang": "de"}),
            content_type="application/json",
        )
        self.assertEqual(resp.status_code, 200)
        data = resp.get_json()
        self.assertIn(data.get("status"), ["success", "fallback"])
        self.assertIn("name", data)
        self.assertEqual(data.get("lat"), 48.1351)
        self.assertEqual(data.get("lng"), 11.582)

        # Invalid coordinates
        resp_invalid = client.post(
            "/api/location/reverse",
            data=json.dumps({"lat": "invalid", "lng": 1000}),
            content_type="application/json",
        )
        self.assertEqual(resp_invalid.status_code, 200)
        data_invalid = resp_invalid.get_json()
        self.assertEqual(data_invalid.get("status"), "error")

    def test_api_chat_passes_user_location(self):
        """Verify POST /api/chat passes user_location to send_message."""
        client = app.test_client()
        mock_result = {
            "status": "success",
            "text": "Witaj! Ruszamy z Poznania.",
            "tool_calls": [],
        }

        with patch("tools.server.send_message", return_value=mock_result) as mock_send:
            resp = client.post(
                "/api/chat",
                data=json.dumps({
                    "message": "Gdzie jesteśmy?",
                    "user_location": {
                        "lat": 52.4064,
                        "lng": 16.9252,
                        "name": "Poznań, Polska",
                    },
                }),
                content_type="application/json",
            )
            self.assertEqual(resp.status_code, 200)
            self.assertTrue(mock_send.called)
            _, kwargs = mock_send.call_args
            self.assertEqual(kwargs.get("user_location"), {
                "lat": 52.4064,
                "lng": 16.9252,
                "name": "Poznań, Polska",
            })


if __name__ == "__main__":
    unittest.main()

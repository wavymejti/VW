"""
Google Maps API client for the VW California AI Trip Planner.

Provides wrapper functions for:
- Places API (campground search)
- Routes API (multi-stop routing)
- Geocoding API (address ↔ coordinates)
"""

import os
import sys
from dotenv import load_dotenv
import googlemaps

# Load environment variables from .env file
load_dotenv()

# Google Maps API key from environment
GOOGLE_MAPS_API_KEY = os.getenv("GOOGLE_MAPS_API_KEY")

# Cost switch (Nov 2026): which Google Maps features may be called.
#   lite (default) — only Geocoding and Directions, so the planner can still build routes;
#                    no interactive map, Places search/details/photos or Static Maps.
#   full           — everything (interactive map, Places, photos, Static Maps).
#   off            — no Google Maps calls at all (route planning fails gracefully).
GOOGLE_MAPS_MODE = os.getenv("GOOGLE_MAPS_MODE", "lite").strip().lower()
_ALLOWED = {
    "full": {"routing", "map", "places", "photos", "static"},
    "lite": {"routing"},
    "off": set(),
}
MAPS_DISABLED_MESSAGE = (
    "This Google Maps feature is switched off to save costs (GOOGLE_MAPS_MODE={mode}). "
    "Set GOOGLE_MAPS_MODE=full in .env to enable it."
)


def maps_allows(feature):
    """True if a Google Maps feature ('routing', 'map', 'places', 'photos', 'static') may be used."""
    return feature in _ALLOWED.get(GOOGLE_MAPS_MODE, _ALLOWED["lite"])


def disabled_message():
    return MAPS_DISABLED_MESSAGE.format(mode=GOOGLE_MAPS_MODE)


def get_client():
    """
    Create and return a Google Maps API client.

    Returns:
        googlemaps.Client: Configured Google Maps client.

    Raises:
        ValueError: If GOOGLE_MAPS_API_KEY is not set.
    """
    if not GOOGLE_MAPS_API_KEY:
        raise ValueError(
            "GOOGLE_MAPS_API_KEY is not set. "
            "Please configure it in your .env file."
        )
    if not maps_allows("routing"):
        raise ValueError(disabled_message())
    return googlemaps.Client(key=GOOGLE_MAPS_API_KEY)


def verify_connection():
    """
    Verify that the Google Maps API key is valid by performing
    a simple geocoding request.

    Returns:
        dict: Connection status and API response info.
    """
    try:
        client = get_client()

        # Test with a simple geocode request (Wolfsburg, VW HQ)
        result = client.geocode("Wolfsburg, Germany")

        if result:
            location = result[0]["geometry"]["location"]
            return {
                "status": "connected",
                "test_query": "Wolfsburg, Germany",
                "lat": location["lat"],
                "lng": location["lng"],
                "formatted_address": result[0]["formatted_address"],
            }
        else:
            return {
                "status": "error",
                "message": "Geocoding returned empty results.",
            }
    except ValueError as e:
        return {"status": "error", "message": str(e)}
    except googlemaps.exceptions.ApiError as e:
        return {"status": "error", "message": f"API Error: {e}"}
    except Exception as e:
        return {"status": "error", "message": str(e)}


if __name__ == "__main__":
    # Run as standalone handshake verification
    print("🔗 Verifying Google Maps API connection...")
    result = verify_connection()

    if result["status"] == "connected":
        print(f"  ✅ API key valid")
        print(f"  ✅ Test geocode: {result['test_query']}")
        print(f"     → {result['formatted_address']}")
        print(f"     → lat: {result['lat']}, lng: {result['lng']}")
    else:
        print(f"  ❌ Connection failed: {result['message']}")
        sys.exit(1)

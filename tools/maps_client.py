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

# Cost switch (Nov 2026). Billing showed 76% of the cost in Places Photo and the rest in the
# Atmosphere/Contact data that legacy Places searches always add; everything else stayed free.
#   basic (default) — everything except those: interactive map, Directions, Geocoding, Static Maps
#                     and Places search/details through Places API (New) with a field mask of
#                     basic fields only (no photos, ratings, reviews, phone, website, hours).
#   full            — also photos, ratings and contact data (legacy Places API, as before).
#   lite            — only Geocoding and Directions; no map, Places or Static Maps.
#   off             — no Google Maps calls at all.
GOOGLE_MAPS_MODE = os.getenv("GOOGLE_MAPS_MODE", "basic").strip().lower()
_ALLOWED = {
    "full": {"routing", "map", "static", "places", "places_rich"},
    "basic": {"routing", "map", "static", "places"},
    "lite": {"routing"},
    "off": set(),
}
MAPS_DISABLED_MESSAGE = (
    "This Google Maps feature is switched off to save costs (GOOGLE_MAPS_MODE={mode}). "
    "Set GOOGLE_MAPS_MODE=full in .env to enable it."
)


def maps_allows(feature):
    """True if a Google Maps feature may be used:
    'routing', 'map', 'static', 'places' (basic fields) or 'places_rich' (photos, ratings, contact)."""
    return feature in _ALLOWED.get(GOOGLE_MAPS_MODE, _ALLOWED["basic"])


def disabled_message():
    return MAPS_DISABLED_MESSAGE.format(mode=GOOGLE_MAPS_MODE)


# ── Places API (New), basic fields only ─────────────────────────────────────
# Only "Pro" fields: no photos, rating, userRatingCount, phone, website or opening hours, which
# are billed as Enterprise / Atmosphere / Contact. Results are returned in the legacy shape
# ({place_id, name, geometry.location, types, vicinity, formatted_address}) so callers that
# were written for the legacy client keep working; ratings and photos are simply absent.
PLACES_NEW_URL = "https://places.googleapis.com/v1"
_BASIC_PLACE_FIELDS = ["id", "displayName", "location", "types", "primaryType",
                       "formattedAddress", "shortFormattedAddress", "googleMapsUri"]
# Legacy type names that Nearby Search (New) does not accept as includedTypes.
_NEW_TYPE_FALLBACK = {
    "natural_feature": "tourist_attraction", "viewpoint": "tourist_attraction",
    "castle": "historical_landmark", "ruins": "historical_landmark",
    "landmark": "historical_landmark", "waterfall": "tourist_attraction",
    "point_of_interest": "tourist_attraction",
}


def _places_new_post(path, body, fields, timeout=15):
    import requests

    resp = requests.post(
        f"{PLACES_NEW_URL}/{path}",
        json=body,
        headers={
            "X-Goog-Api-Key": GOOGLE_MAPS_API_KEY or "",
            "X-Goog-FieldMask": ",".join(f"places.{f}" for f in fields),
        },
        timeout=timeout,
    )
    data = resp.json() if resp.content else {}
    if resp.status_code != 200:
        msg = (data.get("error") or {}).get("message") or resp.text[:300]
        if resp.status_code == 403:
            msg += " (enable 'Places API (New)' for this key in Google Cloud)"
        raise RuntimeError(f"Places API (New) {resp.status_code}: {msg}")
    return data.get("places", [])


def _to_legacy(place):
    loc = place.get("location") or {}
    return {
        "place_id": place.get("id"),
        "name": (place.get("displayName") or {}).get("text", ""),
        "geometry": {"location": {"lat": loc.get("latitude"), "lng": loc.get("longitude")}},
        "types": place.get("types") or ([place["primaryType"]] if place.get("primaryType") else []),
        "vicinity": place.get("shortFormattedAddress") or place.get("formattedAddress", ""),
        "formatted_address": place.get("formattedAddress", ""),
        "url": place.get("googleMapsUri"),
    }


def places_nearby_basic(lat, lng, radius_m, place_type, max_results=20):
    """Nearby Search (New), basic fields, ranked by popularity. Returns {"results": [...]}."""
    place_type = _NEW_TYPE_FALLBACK.get(place_type, place_type)
    body = {
        "includedTypes": [place_type],
        "maxResultCount": max(1, min(int(max_results), 20)),
        "rankPreference": "POPULARITY",
        "locationRestriction": {"circle": {
            "center": {"latitude": lat, "longitude": lng},
            "radius": float(min(max(radius_m, 1), 50000)),
        }},
    }
    try:
        places = _places_new_post("places:searchNearby", body, _BASIC_PLACE_FIELDS)
    except RuntimeError as e:
        # An unsupported type gives 400; fall back to the generic attraction type once.
        if "400" in str(e) and place_type != "tourist_attraction":
            body["includedTypes"] = ["tourist_attraction"]
            places = _places_new_post("places:searchNearby", body, _BASIC_PLACE_FIELDS)
        else:
            raise
    return {"results": [_to_legacy(p) for p in places]}


def places_text_basic(query, lat=None, lng=None, radius_m=80000, max_results=5):
    """Text Search (New), basic fields. Returns {"results": [...]}."""
    body = {"textQuery": query, "pageSize": max(1, min(int(max_results), 20))}
    if lat is not None and lng is not None:
        body["locationBias"] = {"circle": {
            "center": {"latitude": lat, "longitude": lng},
            "radius": float(min(radius_m, 50000)),
        }}
    places = _places_new_post("places:searchText", body, _BASIC_PLACE_FIELDS)
    return {"results": [_to_legacy(p) for p in places]}


def place_details_basic(place_id):
    """Place Details (New), basic fields. Returns a legacy-shaped dict (no photos/ratings)."""
    import requests

    resp = requests.get(
        f"{PLACES_NEW_URL}/places/{place_id}",
        headers={
            "X-Goog-Api-Key": GOOGLE_MAPS_API_KEY or "",
            "X-Goog-FieldMask": ",".join(_BASIC_PLACE_FIELDS),
        },
        timeout=15,
    )
    if resp.status_code != 200:
        raise RuntimeError(f"Places API (New) {resp.status_code}: {resp.text[:300]}")
    return _to_legacy(resp.json())


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

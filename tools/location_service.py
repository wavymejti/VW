"""
Location service module for the VW California AI Trip Planner.

Handles user coordinate validation, reverse geocoding via Google Maps API,
and system prompt context formatting for conversational AI location awareness.
"""

import logging
from typing import Any, Dict, Optional, Tuple

logger = logging.getLogger(__name__)


def sanitize_coordinates(lat: Any, lng: Any) -> Optional[Tuple[float, float]]:
    """
    Validate and convert latitude and longitude to float numbers.

    Args:
        lat: Latitude value (number or string).
        lng: Longitude value (number or string).

    Returns:
        Optional[Tuple[float, float]]: (lat, lng) as floats if valid,
        otherwise None.
    """
    try:
        if lat is None or lng is None:
            return None
        f_lat = float(lat)
        f_lng = float(lng)

        # Check geographic boundaries
        if not (-90.0 <= f_lat <= 90.0):
            return None
        if not (-180.0 <= f_lng <= 180.0):
            return None

        return round(f_lat, 6), round(f_lng, 6)
    except (TypeError, ValueError):
        return None


def reverse_geocode_coordinates(
    lat: float,
    lng: float,
    lang: str = "pl",
) -> Dict[str, Any]:
    """
    Reverse geocode coordinates into a human-readable location name.

    Uses Google Maps Geocoding API when available, with a graceful
    fallback to formatted coordinate strings.

    Args:
        lat: Latitude.
        lng: Longitude.
        lang: Target language code ('pl', 'de', or 'en').

    Returns:
        Dict[str, Any]: Formatted location info with keys:
            - status: "success" or "fallback"
            - name: Human-friendly display string (e.g. "Poznań, Polska")
            - city: City / town name if resolved
            - country: Country name if resolved
            - address: Formatted full address
            - lat: Normalized latitude
            - lng: Normalized longitude
    """
    coords = sanitize_coordinates(lat, lng)
    if not coords:
        return {
            "status": "error",
            "message": "Invalid coordinates provided.",
            "name": "Nieznana lokalizacja",
            "city": None,
            "country": None,
            "address": None,
            "lat": lat,
            "lng": lng,
        }

    c_lat, c_lng = coords
    fallback_name = (
        f"{abs(c_lat):.4f}°{'N' if c_lat >= 0 else 'S'}, "
        f"{abs(c_lng):.4f}°{'E' if c_lng >= 0 else 'W'}"
    )

    try:
        from tools.maps_client import get_client
        client = get_client()
        results = client.reverse_geocode((c_lat, c_lng), language=lang)

        if results and len(results) > 0:
            formatted_address = results[0].get("formatted_address", "")
            city = None
            country = None

            # Extract city and country from address components
            for res in results:
                for comp in res.get("address_components", []):
                    types = comp.get("types", [])
                    if not city and ("locality" in types or "postal_town" in types):
                        city = comp.get("long_name")
                    elif not city and "administrative_area_level_2" in types:
                        city = comp.get("long_name")
                    if not country and "country" in types:
                        country = comp.get("long_name")

            if city and country:
                display_name = f"{city}, {country}"
            elif city:
                display_name = city
            elif country:
                display_name = country
            elif formatted_address:
                display_name = formatted_address
            else:
                display_name = fallback_name

            return {
                "status": "success",
                "name": display_name,
                "city": city,
                "country": country,
                "address": formatted_address,
                "lat": c_lat,
                "lng": c_lng,
            }
    except Exception as err:
        logger.warning(
            "Google Maps reverse geocode failed for (%s, %s): %s",
            c_lat,
            c_lng,
            err,
        )

    # Return graceful fallback
    return {
        "status": "fallback",
        "name": fallback_name,
        "city": None,
        "country": None,
        "address": None,
        "lat": c_lat,
        "lng": c_lng,
    }


def format_location_for_prompt(
    location_data: Dict[str, Any],
    lang: str = "pl",
) -> str:
    """
    Format user location context as a system prompt instruction.

    Args:
        location_data: Dictionary containing 'lat', 'lng', and optional 'name' / 'city'.
        lang: Target conversation language ('pl', 'de', or 'en').

    Returns:
        str: Context string to inject into the OpenAI system messages.
    """
    lat = location_data.get("lat")
    lng = location_data.get("lng")
    name = (
        location_data.get("name")
        or location_data.get("city")
        or f"{lat}, {lng}"
    )

    if lang == "de":
        return (
            f"[SYSTEM NOTE] User Current Location: {name} (lat: {lat}, lng: {lng}). "
            "Der VW California Camper des Nutzers befindet sich aktuell an diesem Standort. "
            "Wenn der Nutzer nach Campingplätzen oder Attraktionen in der Nähe ('in der Nähe', 'hier', 'um mich herum') "
            "oder 'Wo bin ich?' fragt, nutze diesen Standort. Wenn der Nutzer eine Route plant und keinen anderen Startort "
            f"nennt oder 'von hier' sagt, übernimm '{name}' als Standard-Startpunkt (origin)."
        )
    elif lang == "en":
        return (
            f"[SYSTEM NOTE] User Current Location: {name} (lat: {lat}, lng: {lng}). "
            "The user's VW California campervan is currently at this location. "
            "If the user asks for campsites, attractions, or routes 'near me', 'around here', 'nearby', "
            "or asks 'where am I?', use this location. When planning a route without a specified start or when "
            f"the user says 'from here', default the origin to '{name}'."
        )
    else:
        # Default Polish
        return (
            f"[SYSTEM NOTE] User Current Location: {name} (lat: {lat}, lng: {lng}). "
            "Camper VW California użytkownika znajduje się obecnie w tej lokalizacji. "
            "Gdy użytkownik pyta o kempingi lub atrakcje 'w pobliżu', 'blisko mnie', 'w okolicy' lub 'gdzie jestem?', "
            "skorzystaj z tej lokalizacji. Gdy użytkownik planuje trasę i nie poda innego miejsca startu lub powie "
            f"'stąd' / 'z obecnego miejsca', przyjmij '{name}' jako domyślny punkt początkowy (origin)."
        )

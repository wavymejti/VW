"""
Attraction suggestion tool for the VW California AI Trip Planner.

Suggests interesting points of interest (POI) along a planned route by:
1. Decoding the encoded polyline for each day's route
2. Sampling the polyline at regular intervals (~30 km)
3. Calling Google Maps Places Nearby API at each sample point
4. Deduplicating results by place_id
5. Grouping results by day and returning with photo URLs

See: architecture/routing_sop.md
"""

import os
import math

import googlemaps
from tools.db import get_engine
from sqlalchemy import text


# ---------------------------------------------------------------------------
# Category mapping: Google place types → emoji, colour, category label
# ---------------------------------------------------------------------------
CATEGORY_MAP = {
    "tourist_attraction": ("⭐", "#F9A825", "Atrakcja"),
    "museum":             ("🏛️", "#5C6BC0", "Muzeum"),
    "natural_feature":    ("🌿", "#2E7D32", "Natura"),
    "amusement_park":     ("🎡", "#C62828", "Park rozrywki"),
    "viewpoint":          ("👁️", "#E65100", "Punkt widokowy"),
    "castle":             ("🏰", "#8B4513", "Zamek"),
    "national_park":      ("🌲", "#1B5E20", "Park narodowy"),
    "zoo":                ("🦁", "#F57F17", "Zoo"),
    "aquarium":           ("🐠", "#0277BD", "Akwarium"),
    "art_gallery":        ("🎨", "#880E4F", "Galeria sztuki"),
    "church":             ("⛪", "#4E342E", "Kościół / Katedra"),
    "ruins":              ("🏚️", "#6D4C41", "Ruiny"),
    "waterfall":          ("💧", "#00838F", "Wodospad"),
    "beach":              ("🏖️", "#FF8F00", "Plaża"),
    "spa":                ("♨️", "#7B1FA2", "SPA / Termy"),
    "stadium":            ("🏟️", "#37474F", "Stadion"),
    "landmark":           ("📍", "#B71C1C", "Zabytek"),
}

# Types sent to the Places Nearby search (ordered by priority)
SEARCH_TYPES = [
    "tourist_attraction",
    "museum",
    "natural_feature",
    "amusement_park",
    "viewpoint",
    "castle",
    "national_park",
    "zoo",
    "aquarium",
    "art_gallery",
    "church",
    "ruins",
    "waterfall",
    "beach",
    "spa",
    "landmark",
]


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def suggest_attractions(
    trip_id,
    preferences=None,
    limit_per_day=5,
    sample_every_km=30,
    search_radius_m=20000,
):
    """
    Suggest attractions along the route for a given trip.

    Reads encoded polylines from daily_schedules, samples the route
    at regular intervals, queries Google Places Nearby API, deduplicates
    results, and groups them by day.

    Args:
        trip_id (str): The ID of the trip.
        preferences (str | None): User preferences or comma-separated
            place types (e.g. 'castles, lakes, museums').
            If None, all SEARCH_TYPES are used.
        limit_per_day (int): Max number of suggestions per day.
        sample_every_km (float): Approximate sampling interval in km.
        search_radius_m (int): Search radius in metres around each sample.

    Returns:
        dict: {
            "status": "success",
            "trip_id": str,
            "attractions_by_day": {
                "<day_number>": [ <attraction>, ... ]
            }
        }
    """
    gmaps_key = os.getenv("GOOGLE_MAPS_API_KEY")
    if not gmaps_key:
        return {"status": "error", "message": "GOOGLE_MAPS_API_KEY not configured."}

    gmaps = googlemaps.Client(key=gmaps_key)

    # Determine which place types to query
    types_to_search = _parse_preferences(preferences)

    # Load daily schedules (polylines + fallback waypoints)
    engine = get_engine()
    with engine.connect() as conn:
        schedules = conn.execute(
            text(
                "SELECT day_number, waypoints, route_polyline "
                "FROM daily_schedules "
                "WHERE trip_id = :tid ORDER BY day_number ASC"
            ),
            {"tid": trip_id},
        ).fetchall()

    if not schedules:
        return {"status": "error", "message": "Trip or schedules not found."}

    # Global deduplication across all days
    seen_place_ids = set()
    attractions_by_day = {}

    for row in schedules:
        day_number = row[0]
        waypoints = row[1] or []
        route_polyline = row[2]

        # Collect sample points along this day's route
        sample_points = _sample_route(
            route_polyline, waypoints, sample_every_km
        )

        if not sample_points:
            continue

        # Query Places Nearby at each sample and collect candidates
        candidates = _fetch_candidates(
            gmaps, sample_points, types_to_search, search_radius_m, gmaps_key
        )

        # Deduplicate globally
        day_attractions = []
        for place in candidates:
            pid = place.get("place_id")
            if pid and pid in seen_place_ids:
                continue
            if pid:
                seen_place_ids.add(pid)
            day_attractions.append(place)
            if len(day_attractions) >= limit_per_day:
                break

        if day_attractions:
            attractions_by_day[str(day_number)] = day_attractions

    return {
        "status": "success",
        "trip_id": trip_id,
        "preferences": preferences,
        "attractions_by_day": attractions_by_day,
    }


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _parse_preferences(preferences):
    """
    Convert user preference string to a list of Google place types.

    If no preferences are given, returns all SEARCH_TYPES.
    If preferences are given, tries to match keywords to known types.

    Args:
        preferences (str | None): Free-text preferences.

    Returns:
        list[str]: Place types to search.
    """
    if not preferences:
        return SEARCH_TYPES

    prefs_lower = preferences.lower()

    # Keyword-to-type mapping
    keyword_map = {
        "zamek": "castle",
        "zamki": "castle",
        "castle": "castle",
        "muzeum": "museum",
        "muzea": "museum",
        "museum": "museum",
        "natura": "natural_feature",
        "nature": "natural_feature",
        "jezioro": "natural_feature",
        "jeziora": "natural_feature",
        "lake": "natural_feature",
        "park": "national_park",
        "park rozrywki": "amusement_park",
        "amusement": "amusement_park",
        "aquapark": "amusement_park",
        "widok": "viewpoint",
        "viewpoint": "viewpoint",
        "zoo": "zoo",
        "akwarium": "aquarium",
        "aquarium": "aquarium",
        "galeria": "art_gallery",
        "gallery": "art_gallery",
        "art": "art_gallery",
        "kościół": "church",
        "kościoły": "church",
        "church": "church",
        "katedra": "church",
        "cathedral": "church",
        "ruiny": "ruins",
        "ruins": "ruins",
        "wodospad": "waterfall",
        "wodospady": "waterfall",
        "waterfall": "waterfall",
        "plaża": "beach",
        "plaże": "beach",
        "beach": "beach",
        "spa": "spa",
        "termy": "spa",
    }

    # Tokenise preferences: split on commas + whitespace for exact-word matching
    # e.g. "zamki, jeziora" → {"zamki", "jeziora"}
    import re as _re
    tokens = set(_re.split(r"[\s,;/]+", prefs_lower))

    matched = []
    for keyword, place_type in keyword_map.items():
        if keyword in tokens and place_type not in matched:
            matched.append(place_type)

    return matched if matched else SEARCH_TYPES


def _sample_route(route_polyline, waypoints, sample_every_km):
    """
    Decode a polyline and return sample points at regular intervals.

    Falls back to waypoints if no polyline is available.

    Args:
        route_polyline (str | None): Google encoded polyline string.
        waypoints (list[dict]): Fallback waypoints from the schedule.
        sample_every_km (float): Distance between samples in km.

    Returns:
        list[tuple[float, float]]: List of (lat, lng) sample points.
    """
    points = []

    if route_polyline:
        try:
            # googlemaps.convert.decode_polyline returns list of dicts
            decoded = googlemaps.convert.decode_polyline(route_polyline)
            points = [(p["lat"], p["lng"]) for p in decoded]
        except Exception as e:
            print(f"[suggest_attractions] Failed to decode polyline: {e}")

    if not points and waypoints:
        # Fall back to waypoints
        points = [
            (wp["lat"], wp["lng"])
            for wp in waypoints
            if "lat" in wp and "lng" in wp
        ]

    if not points:
        return []

    # Downsample: pick every N points so we cover ~sample_every_km
    # Rough estimate: polyline step ≈ 50-200 m, so steps per 30 km ≈ 150-600
    # We calculate actual cumulative distance and sample at intervals
    samples = [points[0]]
    accumulated_km = 0.0

    for i in range(1, len(points)):
        accumulated_km += _haversine_km(points[i - 1], points[i])
        if accumulated_km >= sample_every_km:
            samples.append(points[i])
            accumulated_km = 0.0

    # Always include the last point
    if samples[-1] != points[-1]:
        samples.append(points[-1])

    return samples


def _haversine_km(p1, p2):
    """
    Calculate the great-circle distance between two points in km.

    Args:
        p1 (tuple[float, float]): (lat, lng)
        p2 (tuple[float, float]): (lat, lng)

    Returns:
        float: Distance in km.
    """
    lat1, lng1 = math.radians(p1[0]), math.radians(p1[1])
    lat2, lng2 = math.radians(p2[0]), math.radians(p2[1])

    dlat = lat2 - lat1
    dlng = lng2 - lng1

    a = math.sin(dlat / 2) ** 2 + (
        math.cos(lat1) * math.cos(lat2) * math.sin(dlng / 2) ** 2
    )
    return 6371.0 * 2 * math.asin(math.sqrt(a))


def _fetch_candidates(gmaps, sample_points, types_to_search,
                      search_radius_m, gmaps_key):
    """
    Query Google Maps Places API for POI near each sample point.

    Uses ``places_nearby`` (one call per sample, type='tourist_attraction')
    to avoid rate-limit and latency issues. Additional specific types are
    fetched only when the caller passed explicit preferences.

    Args:
        gmaps: googlemaps.Client instance.
        sample_points (list[tuple]): (lat, lng) sample points.
        types_to_search (list[str]): Place types to include.
        search_radius_m (int): Search radius in metres.
        gmaps_key (str): API key for building photo URLs.

    Returns:
        list[dict]: Sorted candidate places.
    """
    local_seen = set()
    candidates = []

    # Decide which types to actually query.
    # If caller gave explicit preferences, use those (max 3 to avoid slowness).
    # Otherwise do a single broad tourist_attraction search per point.
    if types_to_search == SEARCH_TYPES:
        # Broad search — use a single "tourist_attraction" call per sample
        query_types = ["tourist_attraction"]
    else:
        # Specific preferences — use up to 3 types
        query_types = types_to_search[:3]

    for lat, lng in sample_points:
        for place_type in query_types:
            try:
                result = gmaps.places_nearby(
                    location=(lat, lng),
                    radius=search_radius_m,
                    type=place_type,
                    rank_by="prominence",
                )
                for place in result.get("results", []):
                    pid = place.get("place_id")
                    if not pid or pid in local_seen:
                        continue
                    local_seen.add(pid)
                    candidates.append(_map_place(place, gmaps_key))

            except Exception as e:
                print(
                    f"[suggest_attractions] Places Nearby error "
                    f"({place_type} at {lat:.3f},{lng:.3f}): {e}"
                )
            # Hard limit: stop early if we already have plenty of candidates
            if len(candidates) >= 100:
                break
        if len(candidates) >= 100:
            break

    # Sort by rating descending (None ratings go last)
    candidates.sort(
        key=lambda p: p.get("rating") or 0,
        reverse=True,
    )

    return candidates



def _map_place(place, gmaps_key):
    """
    Map a Google Places Nearby result to our attraction schema.

    Args:
        place (dict): Raw Google Places API result item.
        gmaps_key (str): API key for building photo URLs.

    Returns:
        dict: Normalised attraction dictionary.
    """
    # Determine best-matching category
    place_types = place.get("types", [])
    category_key = None
    emoji = "⭐"
    color = "#F9A825"
    category_label = "Atrakcja"

    for pt in place_types:
        if pt in CATEGORY_MAP:
            category_key = pt
            emoji, color, category_label = CATEGORY_MAP[pt]
            break

    # Build photo URL from first available photo reference
    photo_url = None
    photos = place.get("photos", [])
    if photos and gmaps_key:
        ref = photos[0].get("photo_reference")
        if ref:
            photo_url = (
                f"https://maps.googleapis.com/maps/api/place/photo"
                f"?maxwidth=600&photoreference={ref}&key={gmaps_key}"
            )

    loc = place.get("geometry", {}).get("location", {})

    return {
        "name": place.get("name", ""),
        "place_id": place.get("place_id"),
        "lat": loc.get("lat"),
        "lng": loc.get("lng"),
        "rating": place.get("rating"),
        "user_ratings_total": place.get("user_ratings_total", 0),
        "address": place.get("vicinity", ""),
        "types": place_types,
        "category": category_key or "tourist_attraction",
        "category_label": category_label,
        "emoji": emoji,
        "color": color,
        "photo_url": photo_url,
        "google_maps_url": (
            f"https://www.google.com/maps/place/?q=place_id:{place.get('place_id')}"
            if place.get("place_id") else None
        ),
    }

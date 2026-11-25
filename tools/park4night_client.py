"""
park4night overnight spots via the unofficial, unauthenticated endpoint used
by the park4night mobile app (documented in github.com/gtoselli/park4night-api).

POC ONLY: park4night has no public API, this endpoint is undocumented and may
change or disappear at any time, and park4night's terms do not license reuse
of its content. Before this goes into a product, data access must be agreed
with park4night (AppMobilEdition). Enabled with PARK4NIGHT_ENABLED=1.

Be gentle: one request per searched area, results cached in memory (6 h) and
in the campings table. Contact data (phone, e-mail) is never read or stored.

See: architecture/camping_search_sop.md
"""

import json
import math
import os
import ssl
import time
import urllib.error
import urllib.parse
import urllib.request

_ENDPOINT = "https://guest.park4night.com/services/V4.1/lieuxGetFilter.php"

# park4night service flag -> our amenity column
_SERVICE_MAP = {
    "electricite": "has_power",
    "point_eau": "has_water",
    "wifi": "has_wifi",
    "douche": "has_showers",
    "wc_public": "has_toilets",
    "eau_noire": "has_waste_disposal",
    "eau_usee": "has_waste_disposal",
}

# park4night place type codes -> label. Not an official list: unknown codes
# fall back to the raw code. Types that are not a place to sleep are skipped.
_TYPE_LABELS = {
    "C": "Camping",
    "P": "Parking day/night",
    "PN": "Surrounded by nature",
    "APN": "Free motorhome area",
    "ACC_G": "Free motorhome area",
    "ACC_P": "Paying motorhome area",
    "ACC_PR": "Private motorhome area",
    "AR": "Rest area",
    "F": "Farm / host",  # farms, wineries, restaurants hosting campers
    "OR": "Off-road 4x4",
}
_NOT_OVERNIGHT = {"PJ", "DS", "EP", "ASS"}  # day-only parking, service area, picnic, services

def _ssl_context():
    # python.org builds on macOS ship without system CA certs; prefer certifi.
    try:
        import certifi
        return ssl.create_default_context(cafile=certifi.where())
    except ImportError:
        return ssl.create_default_context()


_CACHE = {}  # (lat, lng) rounded -> (timestamp, all spots for that point)
_CACHE_TTL_S = 6 * 3600


def is_enabled():
    return os.getenv("PARK4NIGHT_ENABLED", "").lower() in ("1", "true", "yes")


def search_spots(lat, lng, radius_km=30, max_items=20):
    """
    Overnight spots from park4night near a point, in the `campings` dict format,
    nearest first, within radius_km. The endpoint returns ~200 places nearest
    to the point; radius and limit are applied here.

    Returns [] when disabled, on timeout or on any error (never raises).
    """
    if not is_enabled():
        return []

    spots = _fetch(lat, lng)
    spots = [s for s in spots if s["distance_km"] <= radius_km]
    spots.sort(key=lambda s: s["distance_km"])
    return [dict(s) for s in spots[:max_items]]


def _fetch(lat, lng):
    key = (round(lat, 2), round(lng, 2))
    hit = _CACHE.get(key)
    if hit and time.time() - hit[0] < _CACHE_TTL_S:
        return hit[1]

    timeout_s = float(os.getenv("PARK4NIGHT_TIMEOUT", "10"))
    query = urllib.parse.urlencode({"latitude": f"{lat:.6f}", "longitude": f"{lng:.6f}"})
    req = urllib.request.Request(
        f"{_ENDPOINT}?{query}",
        headers={"Accept": "application/json", "User-Agent": "VW-TripPlanner-POC/0.1"},
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout_s, context=_ssl_context()) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except (urllib.error.URLError, TimeoutError, ValueError, OSError) as e:
        print(f"  ⚠️  park4night search failed: {e}")
        return []

    items = data.get("lieux", data.get("data", [])) if isinstance(data, dict) else data
    if not isinstance(items, list):
        print(f"  ⚠️  park4night unexpected response: {str(data)[:200]}")
        return []

    spots = []
    for item in items:
        camp = to_camping(item, lat, lng)
        if camp:
            spots.append(camp)

    _CACHE[key] = (time.time(), spots)
    return spots


def to_camping(item, origin_lat=None, origin_lng=None):
    """Map one park4night place to the camping dict used by search_campings.
    Returns None for invalid places and types that are not for overnight stays."""
    if not isinstance(item, dict):
        return None
    try:
        lat = float(item.get("latitude"))
        lng = float(item.get("longitude"))
    except (TypeError, ValueError):
        return None

    code = str(item.get("code") or "").upper()
    if code in _NOT_OVERNIGHT:
        return None

    amenities = {col: False for col in set(_SERVICE_MAP.values())}
    for flag, col in _SERVICE_MAP.items():
        if _truthy(item.get(flag)):
            amenities[col] = True

    rating = _float(item.get("note_moyenne"))
    if rating is not None:
        rating = round(max(0.0, min(rating, 5.0)), 1) or None

    address = ", ".join(
        str(p) for p in (item.get("route"), item.get("code_postal"), item.get("ville")) if p
    ) or None

    country = item.get("pays_iso")
    country = country.upper() if isinstance(country, str) and len(country) == 2 else None

    place_id = item.get("id")
    camp = {
        "id": None,
        "name": _clean_name(item.get("name")) or _clean_name(item.get("titre"))
                or "park4night spot",
        "lat": lat,
        "lng": lng,
        "place_id": f"p4n:{place_id}" if place_id not in (None, "") else None,
        "address": address,
        "country": country,
        "cost_per_night_eur": None,
        **amenities,
        "shore_power_hookup": amenities["has_power"],
        "max_vehicle_length_m": None,
        "level_ground": None,
        "rating": rating,
        "review_count": int(_float(item.get("nb_commentaires")) or 0),
        "photos": _photo_urls(item.get("photos")),
        "source": "park4night",
        "spot_type": _TYPE_LABELS.get(code, code or None),
        "spot_code": code or None,
        "price_info": (item.get("prix_stationnement") or "").strip() or None,
        "external_url": f"https://park4night.com/en/place/{place_id}" if place_id else None,
    }
    if origin_lat is not None and origin_lng is not None:
        camp["distance_km"] = round(haversine_km(origin_lat, origin_lng, lat, lng), 1)
    return camp


def haversine_km(lat1, lng1, lat2, lng2):
    r = 6371.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = p2 - p1
    dl = math.radians(lng2 - lng1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


def _photo_urls(photos):
    urls = []
    for p in photos or []:
        if isinstance(p, dict):
            p = p.get("link_large") or p.get("link_thumb") or p.get("url")
        if isinstance(p, str) and p.startswith("https://"):
            urls.append(p)
    return urls[:5]


def _clean_name(value):
    # Spots without a street name come back as ", 9 Kolodvorska cesta".
    return str(value or "").strip().strip(",").strip()


def _truthy(value):
    return str(value).strip().lower() in ("1", "true", "yes")


def _float(value):
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


if __name__ == "__main__":
    os.environ.setdefault("PARK4NIGHT_ENABLED", "1")
    spots = search_spots(46.3636, 14.0938, radius_km=20, max_items=10)
    print(f"park4night: {len(spots)} spots")
    for s in spots:
        print(f"  📍 {s['name']} ({s['spot_type']} [{s['spot_code']}]) — {s['distance_km']} km, ⭐ {s['rating']}")

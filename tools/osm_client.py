"""
OpenStreetMap places via the Overpass API: fuel stations, EV chargers, restaurants.

Free (no Google Places cost): one Overpass query per request covers all the points asked
for, results are cached in memory. Public Overpass servers ask for moderate use and a
User-Agent; a second server is tried when the first is busy.
"""

import os
import time

import requests

OVERPASS_URLS = [
    u.strip() for u in os.getenv(
        "OVERPASS_URLS",
        "https://overpass-api.de/api/interpreter,https://overpass.kumi.systems/api/interpreter",
    ).split(",") if u.strip()
]
USER_AGENT = "VW-Sniffer-TripPlanner-POC/1.0"
TIMEOUT_S = 25
CACHE_TTL_S = 24 * 3600

KIND_FILTERS = {
    "fuel": ['["amenity"="fuel"]'],
    "ev_charging": ['["amenity"="charging_station"]'],
    "restaurant": ['["amenity"="restaurant"]', '["amenity"="fast_food"]'],
}

_cache = {}


class OverpassError(RuntimeError):
    pass


def build_query(kind, points, radius_m):
    """One Overpass QL query: every filter of `kind` around every point."""
    parts = []
    for f in KIND_FILTERS[kind]:
        for p in points:
            parts.append(f'nwr{f}(around:{int(radius_m)},{p["lat"]:.5f},{p["lng"]:.5f});')
    return f"[out:json][timeout:{TIMEOUT_S - 5}];({''.join(parts)});out center tags;"


def _power_kw(tags):
    """Highest charging power in kW from socket:*:output tags ("150 kW", "22kW", "50")."""
    best = None
    for key, value in tags.items():
        if key.startswith("socket:") and key.endswith(":output"):
            num = "".join(ch for ch in str(value).split(";")[0] if ch.isdigit() or ch == ".")
            try:
                kw = float(num)
            except ValueError:
                continue
            if "w" in str(value).lower() and "kw" not in str(value).lower():
                kw /= 1000.0  # plain watts
            best = kw if best is None else max(best, kw)
    return best


def _sockets(tags):
    names = {"type2": "Type 2", "type2_combo": "CCS", "chademo": "CHAdeMO", "tesla_supercharger": "Tesla",
             "schuko": "Schuko"}
    return [label for key, label in names.items() if tags.get(f"socket:{key}") not in (None, "no", "0")]


def to_place(element, kind):
    tags = element.get("tags") or {}
    lat = element.get("lat", (element.get("center") or {}).get("lat"))
    lng = element.get("lon", (element.get("center") or {}).get("lon"))
    if lat is None or lng is None:
        return None
    name = tags.get("name") or tags.get("brand") or tags.get("operator")
    if not name:
        name = {"fuel": "Fuel station", "ev_charging": "EV charger", "restaurant": "Restaurant"}[kind]
    place = {
        "osm_id": f"{element.get('type', 'node')}/{element.get('id')}",
        "name": name,
        "lat": float(lat),
        "lng": float(lng),
        "kind": kind,
        "brand": tags.get("brand"),
        "opening_hours": tags.get("opening_hours"),
    }
    if kind == "ev_charging":
        place["power_kw"] = _power_kw(tags)
        place["sockets"] = _sockets(tags)
        place["operator"] = tags.get("operator")
    if kind == "restaurant":
        place["cuisine"] = (tags.get("cuisine") or "").replace("_", " ").replace(";", ", ") or None
        place["fast_food"] = tags.get("amenity") == "fast_food"
    if kind == "fuel":
        place["diesel"] = tags.get("fuel:diesel") != "no"
        place["lpg"] = tags.get("fuel:lpg") == "yes"
    return place


def find_places(kind, points, radius_m=5000):
    """
    Places of `kind` within radius_m of any of `points` ([{"lat", "lng"}]).

    Returns:
        list: places (deduplicated), each with osm_id, name, lat, lng, kind and extras.
    Raises:
        OverpassError: when no Overpass server answered.
    """
    if kind not in KIND_FILTERS:
        raise ValueError(f"Unknown kind: {kind}")
    if not points:
        return []
    key = (kind, int(radius_m), tuple((round(p["lat"], 2), round(p["lng"], 2)) for p in points))
    hit = _cache.get(key)
    if hit and time.time() - hit[0] < CACHE_TTL_S:
        return hit[1]

    query = build_query(kind, points, radius_m)
    last_error = None
    for url in OVERPASS_URLS:
        try:
            resp = requests.post(url, data={"data": query}, timeout=TIMEOUT_S,
                                 headers={"User-Agent": USER_AGENT})
            if resp.status_code in (429, 502, 503, 504):
                last_error = f"{url}: HTTP {resp.status_code}"
                continue
            resp.raise_for_status()
            elements = resp.json().get("elements") or []
            break
        except (requests.RequestException, ValueError) as e:
            last_error = f"{url}: {e}"
    else:
        raise OverpassError(f"OpenStreetMap search is not available right now ({last_error}).")

    seen, places = set(), []
    for el in elements:
        place = to_place(el, kind)
        if place and place["osm_id"] not in seen:
            seen.add(place["osm_id"])
            places.append(place)
    _cache[key] = (time.time(), places)
    return places

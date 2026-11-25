"""
Fuel stations, EV chargers and restaurants near route points from Google Places API (New).

Only "Pro" fields are requested (id, name, location, types, address, businessStatus), so every
call is billed as Nearby Search Pro (5,000 free calls a month per billing account, shared with
the campsite and attraction searches). Opening hours, ratings, price level (Enterprise) and
evChargeOptions / fuelOptions (Enterprise + Atmosphere) are deliberately left out: one such
field moves the whole call to a SKU with only 1,000 free calls a month.

Each place: {"place_id", "name", "lat", "lng", "kind", "address", "url", "primary_type"} (+ fast_food).
"""

import time

import requests

from tools import maps_client

FIELDS = ["id", "displayName", "location", "types", "primaryType", "shortFormattedAddress",
          "formattedAddress", "googleMapsUri", "businessStatus"]
KIND_TYPES = {
    "fuel": ["gas_station"],
    "ev_charging": ["electric_vehicle_charging_station"],
    "restaurant": ["restaurant", "fast_food_restaurant"],
}
MAX_RESULTS = 10
CACHE_TTL_S = 24 * 3600
TIMEOUT_S = 10

_cache = {}


class GooglePlacesError(RuntimeError):
    pass


def available():
    """True when Google Places may be used for stops (key set and GOOGLE_MAPS_MODE allows Places)."""
    return bool(maps_client.GOOGLE_MAPS_API_KEY) and maps_client.maps_allows("places")


def _nearby(kind, point, radius_m):
    body = {
        "includedTypes": KIND_TYPES[kind],
        "maxResultCount": MAX_RESULTS,
        "rankPreference": "DISTANCE",
        "locationRestriction": {"circle": {
            "center": {"latitude": point["lat"], "longitude": point["lng"]},
            "radius": float(min(max(radius_m, 1), 50000)),
        }},
    }
    resp = requests.post(
        f"{maps_client.PLACES_NEW_URL}/places:searchNearby",
        json=body,
        headers={"X-Goog-Api-Key": maps_client.GOOGLE_MAPS_API_KEY or "",
                 "X-Goog-FieldMask": ",".join(f"places.{f}" for f in FIELDS)},
        timeout=TIMEOUT_S,
    )
    data = resp.json() if resp.content else {}
    if resp.status_code != 200:
        msg = (data.get("error") or {}).get("message") or resp.text[:200]
        raise GooglePlacesError(f"Google Places {resp.status_code}: {msg}")
    return data.get("places") or []


# Places to eat whose main type is not "*_restaurant" (pub = Kneipe, often serves lunch).
FOOD_TYPES = {"diner", "bar_and_grill", "food_court", "pub", "gastropub", "cafeteria", "steak_house"}


def _main_type_fits(kind, primary_type):
    """
    Google also tags places that merely sit at a station (tyre air, car wash, shop) with
    gas_station, so for fuel and chargers the main type must be the one asked for. Restaurants
    have many main types (german_restaurant, pizza_restaurant, ...), so anything "*_restaurant"
    or a FOOD_TYPES place counts. No main type at all: keep the place.
    """
    if not primary_type:
        return True
    if kind == "restaurant":
        return primary_type.endswith("restaurant") or primary_type in FOOD_TYPES
    return primary_type in KIND_TYPES[kind]


def _bounds(point, radius_m):
    """Rectangle around a circle (Text Search accepts only a rectangle as a hard limit)."""
    import math
    dlat = radius_m / 111320
    dlng = radius_m / (111320 * max(0.2, math.cos(math.radians(point["lat"]))))
    return {"rectangle": {"low": {"latitude": point["lat"] - dlat, "longitude": point["lng"] - dlng},
                          "high": {"latitude": point["lat"] + dlat, "longitude": point["lng"] + dlng}}}


def _text_search(query, point, radius_m):
    """Text Search (New), Pro fields only (billed as Text Search Pro, its own 5,000 free a month)."""
    body = {"textQuery": query, "pageSize": MAX_RESULTS, "locationRestriction": _bounds(point, radius_m)}
    resp = requests.post(
        f"{maps_client.PLACES_NEW_URL}/places:searchText",
        json=body,
        headers={"X-Goog-Api-Key": maps_client.GOOGLE_MAPS_API_KEY or "",
                 "X-Goog-FieldMask": ",".join(f"places.{f}" for f in FIELDS)},
        timeout=TIMEOUT_S,
    )
    data = resp.json() if resp.content else {}
    if resp.status_code != 200:
        msg = (data.get("error") or {}).get("message") or resp.text[:200]
        raise GooglePlacesError(f"Google Places {resp.status_code}: {msg}")
    return data.get("places") or []


def _norm(text_value):
    import re
    return re.sub(r"[^0-9a-ząćęłńóśźżäöüß]", "", (text_value or "").lower())


def _named(places, query):
    """
    A brand or a name ("McDonald's", "Shell") keeps only places carrying it; a cuisine
    ("pizza", "Italian") usually is not in the name, so then everything Google found stays.
    """
    q = _norm(query)
    named = [p for p in places if q and q in _norm(p["name"])]
    return named or places


def to_place(p, kind):
    loc = p.get("location") or {}
    if loc.get("latitude") is None or loc.get("longitude") is None:
        return None
    if p.get("businessStatus") in ("CLOSED_PERMANENTLY", "CLOSED_TEMPORARILY"):
        return None
    types = p.get("types") or []
    if not _main_type_fits(kind, p.get("primaryType")):
        return None
    place = {
        "place_id": p.get("id"),
        "name": (p.get("displayName") or {}).get("text") or
                {"fuel": "Fuel station", "ev_charging": "EV charger", "restaurant": "Restaurant"}[kind],
        "lat": float(loc["latitude"]),
        "lng": float(loc["longitude"]),
        "kind": kind,
        "address": p.get("shortFormattedAddress") or p.get("formattedAddress"),
        "url": p.get("googleMapsUri"),
        "primary_type": p.get("primaryType"),
    }
    if kind == "restaurant":
        place["fast_food"] = "fast_food_restaurant" in types or p.get("primaryType") == "fast_food_restaurant"
    return place


# Words and brands that mark the station itself (not the tyre pump or car wash at it).
_STATION_WORDS = {
    "fuel": ["fuel", "station", "tankstelle", "stacja", "paliw", "petrol", "gas", "aral", "shell", "bp", "esso",
             "total", "orlen", "avia", "jet", "agip", "eni", "omv", "circle k", "lotos", "mol", "q8", "repsol",
             "star", "hem", "westfalen", "raiffeisen", "tamoil", "texaco", "moya", "amic", "bft"],
    "ev_charging": ["charg", "lade", "ładow", "ionity", "enbw", "tesla", "fastned", "allego", "ewe go", "aral pulse",
                    "shell recharge", "greenway", "orlen charge", "e.on", "elli", "mer", "maingau", "evbox"],
}


def _station_score(place, kind):
    name = place["name"].lower()
    return sum(1 for w in _STATION_WORDS.get(kind, []) if w in name)


def _one_per_address(places, kind):
    """
    Fuel and chargers: Google lists several places at one station (station, tyre air, car wash),
    all typed gas_station. Keep one per address (or per ~50 m), the one whose name looks most
    like the station; on a tie the first (nearest). Restaurants are left alone (food courts).
    """
    if kind not in _STATION_WORDS:
        return places
    kept = []
    for p in places:
        same = next((i for i, k in enumerate(kept)
                     if (p.get("address") and p.get("address") == k.get("address"))
                     or (abs(p["lat"] - k["lat"]) < 0.0005 and abs(p["lng"] - k["lng"]) < 0.0007)), None)
        if same is None:
            kept.append(p)
        elif _station_score(p, kind) > _station_score(kept[same], kind):
            kept[same] = p
    return kept


def find_places(kind, points, radius_m=5000, query=None):
    """
    Places of `kind` near each of `points` ([{"lat", "lng"}]): one call per point, Nearby
    Search by type, or Text Search when the user asked for a name, brand or cuisine (`query`).

    Raises:
        GooglePlacesError: when Google is not configured or a call fails.
    """
    if kind not in KIND_TYPES:
        raise ValueError(f"Unknown kind: {kind}")
    if not available():
        raise GooglePlacesError("Google Places is not available (no key or GOOGLE_MAPS_MODE).")
    seen, places = set(), []
    for pt in points:
        key = (kind, int(radius_m), round(pt["lat"], 2), round(pt["lng"], 2), (query or "").lower())
        hit = _cache.get(key)
        if hit and time.time() - hit[0] < CACHE_TTL_S:
            found = hit[1]
        else:
            try:
                raw = _text_search(query, pt, radius_m) if query else _nearby(kind, pt, radius_m)
            except requests.RequestException as e:
                raise GooglePlacesError(f"Google Places: {e}") from e
            found = _one_per_address([x for x in (to_place(p, kind) for p in raw) if x], kind)
            if query:
                found = _named(found, query)
            _cache[key] = (time.time(), found)
        for p in found:
            if p["place_id"] not in seen:
                seen.add(p["place_id"])
                places.append(p)
    return places

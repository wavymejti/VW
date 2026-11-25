"""
Street-level photo of a place from Mapillary (free, also for commercial use; images CC-BY-SA).

Used for fuel / charging / lunch stops instead of Google Places photos (which are billed).
The photo is taken from the street near the place, so it is picked to face the place:
a 360° panorama or an image whose camera points towards it, newer and nearer first.

Needs MAPILLARY_TOKEN (client token from mapillary.com/dashboard/developers) in .env;
without it available() is False and the app shows no photos.
"""

import math
import os
import time
from datetime import datetime, timezone

import requests

GRAPH_URL = "https://graph.mapillary.com/images"
FIELDS = "id,thumb_1024_url,captured_at,computed_geometry,geometry,computed_compass_angle,compass_angle,is_pano,creator"
RADII_M = (60, 150)          # look close first, then a bit further
FACING_DEG = 70              # camera within this of the bearing to the place counts as facing it
NOT_FACING_PENALTY_M = 120   # a photo pointing away counts as this much further
AGE_PENALTY_M_PER_YEAR = 8   # older photos rank lower
TIMEOUT_S = 8
CACHE_TTL_S = 6 * 3600       # thumbnail URLs are signed and expire, so not longer than this

_cache = {}


def available():
    return bool(os.getenv("MAPILLARY_TOKEN"))


def _km(a_lat, a_lng, b_lat, b_lng):
    r = math.pi / 180
    h = (math.sin((b_lat - a_lat) * r / 2) ** 2
         + math.cos(a_lat * r) * math.cos(b_lat * r) * math.sin((b_lng - a_lng) * r / 2) ** 2)
    return 2 * 6371 * math.asin(math.sqrt(h))


def _bearing(a_lat, a_lng, b_lat, b_lng):
    r = math.pi / 180
    y = math.sin((b_lng - a_lng) * r) * math.cos(b_lat * r)
    x = (math.cos(a_lat * r) * math.sin(b_lat * r)
         - math.sin(a_lat * r) * math.cos(b_lat * r) * math.cos((b_lng - a_lng) * r))
    return (math.degrees(math.atan2(y, x)) + 360) % 360


def _bbox(lat, lng, radius_m):
    dlat = radius_m / 111320
    dlng = radius_m / (111320 * max(0.2, math.cos(math.radians(lat))))
    return f"{lng - dlng:.6f},{lat - dlat:.6f},{lng + dlng:.6f},{lat + dlat:.6f}"


def _score(img, lat, lng):
    """Lower is better: metres away + penalties; None if the image has no position."""
    geom = img.get("computed_geometry") or img.get("geometry") or {}
    coords = geom.get("coordinates") or []
    if len(coords) < 2:
        return None
    i_lng, i_lat = coords[0], coords[1]
    dist_m = _km(i_lat, i_lng, lat, lng) * 1000
    score = dist_m
    if not img.get("is_pano"):
        angle = img.get("computed_compass_angle", img.get("compass_angle"))
        if angle is not None and dist_m > 5:
            diff = abs((_bearing(i_lat, i_lng, lat, lng) - float(angle) + 180) % 360 - 180)
            if diff > FACING_DEG:
                score += NOT_FACING_PENALTY_M
    captured = img.get("captured_at")
    if captured:
        years = (time.time() - float(captured) / 1000) / (365.25 * 86400)
        score += max(0.0, years) * AGE_PENALTY_M_PER_YEAR
    return score


def _to_photo(img):
    captured = img.get("captured_at")
    year = datetime.fromtimestamp(float(captured) / 1000, tz=timezone.utc).year if captured else None
    creator = (img.get("creator") or {}).get("username")
    return {
        "url": img.get("thumb_1024_url"),
        "image_id": img.get("id"),
        "viewer_url": f"https://www.mapillary.com/app/?pKey={img.get('id')}",
        "year": year,
        "credit": f"© {creator} / Mapillary, CC BY-SA" if creator else "© Mapillary, CC BY-SA",
    }


def nearest_photo(lat, lng):
    """
    The best street-level photo of the place at (lat, lng), or None.

    Returns:
        dict | None: {"url", "image_id", "viewer_url", "year", "credit"}.
    """
    if not available():
        return None
    key = (round(float(lat), 5), round(float(lng), 5))
    hit = _cache.get(key)
    if hit and time.time() - hit[0] < CACHE_TTL_S:
        return hit[1]
    best = None
    for radius in RADII_M:
        try:
            resp = requests.get(GRAPH_URL, params={
                "access_token": os.getenv("MAPILLARY_TOKEN"), "fields": FIELDS,
                "bbox": _bbox(float(lat), float(lng), radius), "limit": 50,
            }, timeout=TIMEOUT_S)
            if resp.status_code != 200:
                print(f"[mapillary] HTTP {resp.status_code}: {resp.text[:200]}")
                return None  # not cached: a bad token or rate limit should not stick
            images = [i for i in (resp.json().get("data") or []) if i.get("thumb_1024_url")]
        except (requests.RequestException, ValueError) as e:
            print(f"[mapillary] {e}")
            return None
        scored = [(s, i) for i in images if (s := _score(i, float(lat), float(lng))) is not None]
        if scored:
            best = _to_photo(min(scored, key=lambda x: x[0])[1])
            break
    _cache[key] = (time.time(), best)
    return best

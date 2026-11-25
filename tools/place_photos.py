"""
Free photos of attractions (Nov 2026), instead of Google Places photos (billed, off by default).

1. Wikimedia Commons: photos with coordinates near the place (no key). A file whose title
   names the place wins; without a name match only a photo very close to the place is used.
2. Mapillary street-level photo (tools/mapillary_client.py) when Commons has nothing.

Every photo comes with its credit (author, licence), which the UI shows.
"""

import html
import math
import re
import time

import requests

from tools import mapillary_client

COMMONS_API = "https://commons.wikimedia.org/w/api.php"
USER_AGENT = "VW-Sniffer-TripPlanner-POC/1.0 (https://github.com/wavymejti/VW)"
RADIUS_M = 300          # attractions (castles, lakes) are big: their point is rarely the photo's
CLOSE_M = 120           # a photo without the place's name in its title must be this close
NAME_BONUS_M = 250      # each name word in the file title counts as this much nearer
PHOTO_MIME = ("image/jpeg", "image/png", "image/webp")
SKIP_TITLE = re.compile(r"\b(map|karte|mapa|plan|logo|wappen|coat of arms|sign|schild|diagram)\b", re.I)
TIMEOUT_S = 8
CACHE_TTL_S = 24 * 3600

_cache = {}


def _m(a_lat, a_lng, b_lat, b_lng):
    r = math.pi / 180
    h = (math.sin((b_lat - a_lat) * r / 2) ** 2
         + math.cos(a_lat * r) * math.cos(b_lat * r) * math.sin((b_lng - a_lng) * r / 2) ** 2)
    return 2 * 6371000 * math.asin(math.sqrt(h))


def _words(name):
    return {w for w in re.findall(r"\w+", (name or "").lower()) if len(w) >= 4}


def _plain(value):
    """Commons metadata is HTML ("<a ...>Jan Kowalski</a>"): plain text, short."""
    text = html.unescape(re.sub(r"<[^>]+>", "", value or "")).strip()
    return re.sub(r"\s+", " ", text)[:80]


def commons_photo(lat, lng, name=None):
    """Best Commons photo near (lat, lng) for the place `name`, or None (never raises)."""
    try:
        resp = requests.get(COMMONS_API, params={
            "action": "query", "format": "json", "generator": "geosearch",
            "ggscoord": f"{lat}|{lng}", "ggsradius": RADIUS_M, "ggsnamespace": 6, "ggslimit": 30,
            "prop": "imageinfo|coordinates", "iiprop": "url|mime|extmetadata", "iiurlwidth": 640,
            "iiextmetadatafilter": "Artist|LicenseShortName",
        }, headers={"User-Agent": USER_AGENT}, timeout=TIMEOUT_S)
        pages = ((resp.json() or {}).get("query") or {}).get("pages") or {}
    except (requests.RequestException, ValueError) as e:
        print(f"[commons] {e}")
        return None
    words = _words(name)
    best = None
    for page in pages.values():
        info = (page.get("imageinfo") or [{}])[0]
        title = page.get("title") or ""
        coords = (page.get("coordinates") or [{}])[0]
        if info.get("mime") not in PHOTO_MIME or not info.get("thumburl") or SKIP_TITLE.search(title):
            continue
        if coords.get("lat") is None:
            continue
        dist = _m(lat, lng, coords["lat"], coords["lon"])
        hits = len(words & _words(title))
        if not hits and dist > CLOSE_M:
            continue
        score = dist - hits * NAME_BONUS_M
        if best is None or score < best[0]:
            best = (score, page, info)
    if not best:
        return None
    _, page, info = best
    meta = info.get("extmetadata") or {}
    author = _plain((meta.get("Artist") or {}).get("value"))
    licence = _plain((meta.get("LicenseShortName") or {}).get("value"))
    credit = " / ".join(x for x in (f"© {author}" if author else "", "Wikimedia Commons", licence) if x)
    return {"url": info["thumburl"], "viewer_url": info.get("descriptionurl"),
            "credit": credit, "year": None, "source": "commons"}


def attraction_photo(lat, lng, name=None):
    """Commons first, then Mapillary; None if neither has one. Cached for a day."""
    key = (round(float(lat), 4), round(float(lng), 4), (name or "").strip().lower())
    hit = _cache.get(key)
    if hit and time.time() - hit[0] < CACHE_TTL_S:
        return hit[1]
    photo = commons_photo(float(lat), float(lng), name)
    if photo is None and mapillary_client.available():
        photo = mapillary_client.nearest_photo(lat, lng)
        if photo:
            photo = {**photo, "source": "mapillary"}
    _cache[key] = (time.time(), photo)
    return photo

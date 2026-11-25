"""Street-level photos of stops from Mapillary (Nov 2026); the API is mocked."""

import time

from tools import mapillary_client as mc

PLACE = (52.2000, 8.8000)  # lat, lng
NOW_MS = time.time() * 1000


def _img(i, dlat, dlng, angle=None, pano=False, years_old=1):
    return {"id": str(i), "thumb_1024_url": f"https://img/{i}.jpg", "is_pano": pano,
            "computed_compass_angle": angle, "creator": {"username": "anna"},
            "captured_at": NOW_MS - years_old * 365.25 * 86400 * 1000,
            "computed_geometry": {"type": "Point", "coordinates": [PLACE[1] + dlng, PLACE[0] + dlat]}}


class Resp:
    def __init__(self, data, code=200):
        self.status_code, self._data, self.text = code, data, ""

    def json(self):
        return {"data": self._data}


def _setup(monkeypatch, pages):
    calls = []

    def fake_get(url, params=None, timeout=None):
        calls.append(params)
        return pages[min(len(calls) - 1, len(pages) - 1)]

    monkeypatch.setenv("MAPILLARY_TOKEN", "MLY|test")
    monkeypatch.setattr(mc.requests, "get", fake_get)
    mc._cache.clear()
    return calls


def test_no_token_no_call(monkeypatch):
    monkeypatch.delenv("MAPILLARY_TOKEN", raising=False)
    monkeypatch.setattr(mc.requests, "get", lambda *a, **k: (_ for _ in ()).throw(AssertionError("called")))
    assert mc.available() is False and mc.nearest_photo(*PLACE) is None


def test_photo_facing_the_place_beats_a_nearer_one_facing_away(monkeypatch):
    # 20 m south of the place: north (0°) faces it, south (180°) faces away.
    away = _img(1, -0.00018, 0, angle=180)
    facing = _img(2, -0.00030, 0, angle=5)
    _setup(monkeypatch, [Resp([away, facing])])
    photo = mc.nearest_photo(*PLACE)
    assert photo["image_id"] == "2" and photo["url"] == "https://img/2.jpg"
    assert photo["credit"] == "© anna / Mapillary, CC BY-SA"
    assert photo["viewer_url"].endswith("pKey=2")


def test_panorama_needs_no_direction_and_old_photos_rank_lower(monkeypatch):
    old = _img(1, 0.0002, 0, pano=True, years_old=9)
    new = _img(2, 0.0003, 0, pano=True, years_old=1)
    _setup(monkeypatch, [Resp([old, new])])
    assert mc.nearest_photo(*PLACE)["image_id"] == "2"


def test_wider_search_when_nothing_close_and_result_cached(monkeypatch):
    calls = _setup(monkeypatch, [Resp([]), Resp([_img(3, 0.001, 0, pano=True)])])
    assert mc.nearest_photo(*PLACE)["image_id"] == "3"
    assert len(calls) == 2 and calls[0]["access_token"] == "MLY|test" and "bbox" in calls[0]
    mc.nearest_photo(*PLACE)
    assert len(calls) == 2  # cached


def test_api_error_is_not_cached(monkeypatch):
    calls = _setup(monkeypatch, [Resp([], code=401), Resp([_img(4, 0.0001, 0, pano=True)])])
    assert mc.nearest_photo(*PLACE) is None
    assert mc.nearest_photo(*PLACE)["image_id"] == "4" and len(calls) == 2

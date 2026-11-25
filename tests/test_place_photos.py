"""Free attraction photos: Wikimedia Commons first, Mapillary next (Nov 2026); APIs mocked."""

from tools import place_photos as pp

CASTLE = (49.9390, 14.1880)  # Karlštejn


def _page(i, title, dlat, mime="image/jpeg", artist='<a href="x">Jan Nowak</a>', lic="CC BY-SA 4.0"):
    return {"title": title, "coordinates": [{"lat": CASTLE[0] + dlat, "lon": CASTLE[1]}],
            "imageinfo": [{"mime": mime, "thumburl": f"https://up/{i}.jpg", "descriptionurl": f"https://c/{i}",
                           "extmetadata": {"Artist": {"value": artist}, "LicenseShortName": {"value": lic}}}]}


class Resp:
    def __init__(self, pages):
        self._pages = pages

    def json(self):
        return {"query": {"pages": {str(i): p for i, p in enumerate(self._pages)}}}


def _commons(monkeypatch, pages):
    sent = {}

    def fake_get(url, params=None, headers=None, timeout=None):
        sent.update(params=params, headers=headers)
        return Resp(pages)

    monkeypatch.setattr(pp.requests, "get", fake_get)
    pp._cache.clear()
    return sent


def test_named_photo_beats_a_closer_random_one(monkeypatch):
    sent = _commons(monkeypatch, [
        _page(1, "File:Bench in the park.jpg", 0.0003),             # ~33 m
        _page(2, "File:Hrad Karlštejn from the valley.jpg", 0.002),  # ~220 m, names the place
    ])
    photo = pp.commons_photo(*CASTLE, name="Karlštejn Castle")
    assert photo["url"] == "https://up/2.jpg"
    assert photo["credit"] == "© Jan Nowak / Wikimedia Commons / CC BY-SA 4.0"
    assert sent["params"]["ggsnamespace"] == 6 and "User-Agent" in sent["headers"]


def test_maps_logos_and_far_unnamed_photos_are_skipped(monkeypatch):
    _commons(monkeypatch, [
        _page(1, "File:Karlštejn map.png", 0.0001, mime="image/png"),
        _page(2, "File:Karlstejn coat.svg", 0.0001, mime="image/svg+xml"),
        _page(3, "File:Some road.jpg", 0.002),
    ])
    assert pp.commons_photo(*CASTLE, name="Karlštejn") is None


def test_mapillary_when_commons_has_nothing(monkeypatch):
    _commons(monkeypatch, [])
    monkeypatch.setattr(pp.mapillary_client, "available", lambda: True)
    monkeypatch.setattr(pp.mapillary_client, "nearest_photo",
                        lambda lat, lng: {"url": "https://mly/1.jpg", "credit": "© Mapillary, CC BY-SA"})
    photo = pp.attraction_photo(*CASTLE, name="Karlštejn")
    assert photo["url"] == "https://mly/1.jpg" and photo["source"] == "mapillary"


def test_commons_down_is_no_photo(monkeypatch):
    def boom(*a, **k):
        raise pp.requests.ConnectionError("down")
    monkeypatch.setattr(pp.requests, "get", boom)
    monkeypatch.setattr(pp.mapillary_client, "available", lambda: False)
    pp._cache.clear()
    assert pp.attraction_photo(*CASTLE, name="Karlštejn") is None

"""Unit tests for tools/park4night_client.py (HTTP mocked) and its use in search_campings."""

import json
from unittest.mock import patch, MagicMock

from tools import park4night_client
from tools.park4night_client import to_camping, search_spots

# Shape of the app endpoint (github.com/gtoselli/park4night-api, models/place.model.md)
SAMPLE = {
    "id": "58511",
    "latitude": "46.3700",
    "longitude": "14.1000",
    "titre": "Bled, Cesta svobode",
    "name": "Camping Olmellu",
    "route": "Cesta svobode",
    "code_postal": "4260",
    "ville": "Bled",
    "pays_iso": "si",
    "prix_stationnement": "25€",
    "tel": "+386000000",
    "mail": "someone@example.com",
    "note_moyenne": "3.47",
    "nb_commentaires": "19",
    "point_eau": "1",
    "eau_noire": "0",
    "eau_usee": "1",
    "wc_public": "0",
    "douche": "1",
    "electricite": "1",
    "wifi": "0",
    "code": "C",
    "photos": [
        {"link_large": "https://cdn3.park4night.com/lieu/a_gd.jpg", "link_thumb": "https://cdn3.park4night.com/lieu/a_pt.jpg"},
        {"link_large": "http://insecure.example/b.jpg"},
    ],
}
FAR = dict(SAMPLE, id="2", latitude="47.5", longitude="15.5")
DAY_ONLY = dict(SAMPLE, id="3", code="PJ")


def _resp(payload):
    resp = MagicMock()
    resp.read.return_value = json.dumps(payload).encode()
    resp.__enter__.return_value = resp
    return resp


def test_to_camping_maps_fields():
    camp = to_camping(SAMPLE, 46.3636, 14.0938)
    assert camp["place_id"] == "p4n:58511"
    assert camp["source"] == "park4night"
    assert camp["spot_type"] == "Camping"
    assert camp["has_power"] and camp["shore_power_hookup"]
    assert camp["has_water"] and camp["has_showers"] and camp["has_waste_disposal"]
    assert not camp["has_toilets"] and not camp["has_wifi"]
    assert camp["rating"] == 3.5 and camp["review_count"] == 19
    assert camp["country"] == "SI"
    assert camp["address"] == "Cesta svobode, 4260, Bled"
    assert camp["price_info"] == "25€"
    assert camp["photos"] == ["https://cdn3.park4night.com/lieu/a_gd.jpg"]
    assert camp["external_url"] == "https://park4night.com/en/place/58511"
    assert camp["distance_km"] < 2
    # contact data is never carried over
    assert "+386000000" not in json.dumps(camp) and "example.com" not in json.dumps(camp)


def test_to_camping_skips_invalid_and_day_only():
    assert to_camping({"id": 1, "name": "x"}) is None
    assert to_camping(DAY_ONLY) is None


def test_search_spots_disabled_by_default(monkeypatch):
    monkeypatch.delenv("PARK4NIGHT_ENABLED", raising=False)
    with patch("tools.park4night_client.urllib.request.urlopen") as urlopen:
        assert search_spots(46.36, 14.09) == []
    urlopen.assert_not_called()


def test_search_spots_filters_radius_and_caches(monkeypatch):
    monkeypatch.setenv("PARK4NIGHT_ENABLED", "1")
    park4night_client._CACHE.clear()
    with patch("tools.park4night_client.urllib.request.urlopen",
               return_value=_resp([FAR, SAMPLE, DAY_ONLY])) as urlopen:
        first = search_spots(46.3636, 14.0938, radius_km=30)
        second = search_spots(46.3636, 14.0938, radius_km=200)
    assert urlopen.call_count == 1
    assert [s["place_id"] for s in first] == ["p4n:58511"]
    assert [s["place_id"] for s in second] == ["p4n:58511", "p4n:2"]
    url = urlopen.call_args[0][0].full_url
    assert "lieuxGetFilter.php" in url and "latitude=46.363600" in url


def test_search_spots_returns_empty_on_error(monkeypatch):
    import urllib.error
    monkeypatch.setenv("PARK4NIGHT_ENABLED", "1")
    park4night_client._CACHE.clear()
    with patch("tools.park4night_client.urllib.request.urlopen",
               side_effect=urllib.error.URLError("timeout")):
        assert search_spots(10.0, 10.0) == []


@patch("tools.search_campings._cache_maps_results")
@patch("tools.search_campings._search_google_maps", side_effect=lambda *a, **k: [])
@patch("tools.search_campings._search_database", side_effect=lambda *a, **k: [])
def test_search_campings_includes_park4night(_db, _maps, _cache, monkeypatch):
    from tools.search_campings import search_campings
    monkeypatch.setenv("PARK4NIGHT_ENABLED", "1")
    with patch("tools.park4night_client.search_spots",
               return_value=[to_camping(SAMPLE, 46.3636, 14.0938)]):
        res = search_campings(46.3636, 14.0938, amenities=["power"])
        assert res["source"] == "mixed"
        assert res["results"][0]["source"] == "park4night"
        # amenity filter is applied locally
        res = search_campings(46.3636, 14.0938, amenities=["wifi"])
        assert res["results"] == []

"""Free or paid on every place to stay (Nov 2026 tests)."""

import pytest

from tools.camping_price import price_of
import tools.search_campings as sc


@pytest.mark.parametrize("camp, kind, label", [
    ({"cost_per_night_eur": 0}, "free", "Free"),
    ({"cost_per_night_eur": 18.5}, "paid", "Paid · €18.5/night"),
    ({"source": "park4night", "price_info": "Gratuit"}, "free", "Free"),
    ({"source": "park4night", "price_info": "10 €/nuit"}, "paid", "Paid · 10 €/nuit"),
    ({"source": "park4night", "price_info": "0"}, "free", "Free"),
    ({"source": "park4night", "spot_code": "ACC_G"}, "free", "Free"),
    ({"source": "park4night", "spot_code": "PN"}, "free", "Free"),
    ({"source": "park4night", "spot_code": "F"}, "free", "Free · host spot"),
    ({"source": "park4night", "spot_code": "C"}, "paid", "Paid · price not listed"),
    ({"source": "google_maps"}, "paid", "Paid · price not listed"),
    ({"place_id": "ChIJabc"}, "paid", "Paid · price not listed"),
    ({"source": "park4night", "place_id": "p4n:1"}, "unknown", "Price not listed"),
])
def test_price_of(camp, kind, label):
    assert price_of(camp) == {"price_kind": kind, "price_label": label}


def test_search_results_always_have_a_price(monkeypatch):
    monkeypatch.setattr(sc, "_search_database", lambda *a, **k: [
        {"place_id": "p4n:7", "source": "park4night", "name": "Lake spot", "lat": 1, "lng": 1},
        {"place_id": "g1", "source": "google_maps", "name": "Camping X", "lat": 1, "lng": 1},
        {"place_id": "db1", "source": "partner_db", "name": "Camping Y", "lat": 1, "lng": 1,
         "cost_per_night_eur": 0},
    ])
    monkeypatch.setattr(sc.park4night_client, "is_enabled", lambda: True)
    monkeypatch.setattr(sc, "_search_park4night", lambda *a, **k: [
        {"place_id": "p4n:7", "spot_code": "ACC_G", "spot_type": "Free motorhome area", "price_info": None}])
    cached = []
    monkeypatch.setattr(sc, "_cache_maps_results", lambda camps: cached.extend(camps))
    res = sc.search_campings(1.0, 1.0)
    kinds = {c["name"]: (c["price_kind"], c["price_label"]) for c in res["results"]}
    assert kinds == {"Lake spot": ("free", "Free"),          # filled from a fresh park4night search
                     "Camping X": ("paid", "Paid · price not listed"),
                     "Camping Y": ("free", "Free")}
    assert cached and cached[0]["spot_code"] == "ACC_G"      # stored for next time

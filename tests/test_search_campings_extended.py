import pytest
from unittest.mock import patch, MagicMock
from tools.search_campings import search_campings, _search_database, _search_google_maps, _cache_maps_results


class TestSearchCampingsExtended:
    @patch("tools.search_campings.get_engine")
    def test_search_database_exception(self, mock_engine):
        mock_engine.side_effect = Exception("DB Connection Refused")
        results = _search_database(0, 0, 10, [], None, False, 10)
        assert results == []

    @patch("tools.search_campings.get_maps_client")
    def test_search_google_maps_exception(self, mock_client):
        mock_client.side_effect = Exception("Maps API down")
        results = _search_google_maps(0, 0, 10)
        assert results == []

    @patch("tools.search_campings.get_engine")
    def test_cache_maps_results_exception(self, mock_engine):
        mock_engine.side_effect = Exception("DB Error")
        # Should catch and not crash
        _cache_maps_results([{"place_id": "test", "lat": 0, "lng": 0}])

    def test_cache_maps_results_empty(self):
        # Should return early
        assert _cache_maps_results([]) is None

    @patch("tools.search_campings._search_database")
    @patch("tools.search_campings._search_google_maps")
    def test_search_falls_back_to_maps_and_merges(self, mock_maps, mock_db):
        # DB returns 1 result (less than 3, triggers fallback)
        mock_db.return_value = [{"place_id": "db_id", "name": "DB Camp"}]
        # Maps returns 2 results, 1 is duplicate, 1 is new
        mock_maps.return_value = [
            {"place_id": "db_id", "name": "DB Camp"},  # duplicate
            {"place_id": "new_id", "name": "Maps Camp"} # new
        ]
        
        # Patch caching to prevent DB interaction
        with patch("tools.search_campings._cache_maps_results"):
            res = search_campings(0, 0)
        
        assert res["status"] == "success"
        assert res["source"] == "mixed"
        assert res["total_found"] == 2
        
        # Verify deduplication
        names = [c["name"] for c in res["results"]]
        assert "DB Camp" in names
        assert "Maps Camp" in names

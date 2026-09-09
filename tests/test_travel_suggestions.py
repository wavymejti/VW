"""
Unit and integration tests for Suggestive Travel Inspirations (Variant B) with RAG.

Tests dynamic generation, curated fallbacks, multi-language support,
RAG preference reinforcement, and Flask REST API endpoints.
"""

import os
import json
import unittest
from unittest.mock import MagicMock, patch

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

from tools.travel_suggestions import (
    get_curated_fallback_suggestions,
    generate_dynamic_suggestions,
    record_suggestion_choice,
    format_enriched_suggestion_prompt,
    SCENIC_THEME_IMAGES,
)
from tools.server import app


class TestTravelSuggestions(unittest.TestCase):
    """Test suite for Travel Suggestions tool and API endpoints."""

    def test_format_enriched_suggestion_prompt_with_location_pl(self):
        """Verify prompt enrichment includes duration, starting location, destination, and highlights in Polish."""
        card = {
            "title": "Mazurskie Uroki",
            "subtitle": "Odkryj krystaliczne jeziora i malownicze lasy.",
            "duration_days": 3,
            "duration_category": "weekend",
            "vw_highlights": ["Blisko jezior", "Przyłącze prądu 230V"],
        }
        prompt = format_enriched_suggestion_prompt(card, user_location="Poznań", lang="pl")
        self.assertIn("3-dniowy wyjazd", prompt)
        self.assertIn("ze startem z: Poznań", prompt)
        self.assertIn("Cel: Mazurskie Uroki", prompt)
        self.assertIn("Blisko jezior, Przyłącze prądu 230V", prompt)

    def test_format_enriched_suggestion_prompt_without_location_pl(self):
        """Verify prompt enrichment without location cleanly omits start location clause."""
        card = {
            "title": "Morawskie Smaki",
            "subtitle": "Zanurz się w winach.",
            "duration_days": 7,
            "duration_category": "week",
            "vw_highlights": ["Winnice"],
        }
        prompt = format_enriched_suggestion_prompt(card, user_location=None, lang="pl")
        self.assertIn("7-dniowy wyjazd", prompt)
        self.assertNotIn("ze startem z:", prompt)
        self.assertIn("Cel: Morawskie Smaki", prompt)

    def test_format_enriched_suggestion_prompt_multilang(self):
        """Verify prompt enrichment in German and English."""
        card = {
            "title": "Kärntner Seen",
            "subtitle": "Schöne Seeblicke.",
            "duration_days": 4,
            "vw_highlights": ["Stellplatz am See"],
        }
        de_prompt = format_enriched_suggestion_prompt(card, user_location="München", lang="de")
        self.assertIn("4-tägige Reise", de_prompt)
        self.assertIn("mit Start ab: München", de_prompt)
        self.assertIn("Ziel: Kärntner Seen", de_prompt)

        en_prompt = format_enriched_suggestion_prompt(card, user_location="London", lang="en")
        self.assertIn("4-day road trip", en_prompt)
        self.assertIn("starting from: London", en_prompt)
        self.assertIn("Destination: Kärntner Seen", en_prompt)

    def test_curated_fallback_suggestions_with_location(self):
        """Verify fallback suggestions enrich prompt when user_location is provided."""
        cards = get_curated_fallback_suggestions(lang="pl", user_location="Poznań")
        for card in cards:
            self.assertIn("ze startem z: Poznań", card["prompt"])


    def test_get_curated_fallback_suggestions_pl(self):
        """Verify curated Polish suggestions contain required fields and persona constraints."""
        cards = get_curated_fallback_suggestions(lang="pl")
        self.assertEqual(len(cards), 4)

        for card in cards:
            self.assertIn("id", card)
            self.assertIn("title", card)
            self.assertIn("subtitle", card)
            self.assertIn("image_url", card)
            self.assertIn("tags", card)
            self.assertIn("prompt", card)
            self.assertIn("vw_highlights", card)
            self.assertIn("duration_category", card)
            self.assertIn("duration_days", card)
            self.assertIn("rag_reason", card)
            self.assertIn(card["duration_category"], ("weekend", "week", "expedition"))
            self.assertIsInstance(card["duration_days"], int)
            self.assertTrue(len(card["rag_reason"]) > 10)
            self.assertTrue(len(card["tags"]) > 0)
            self.assertTrue(card["image_url"].startswith("http"))

    def test_get_curated_fallback_suggestions_duration_filter(self):
        """Verify filtering suggestions by duration_category."""
        weekend_cards = get_curated_fallback_suggestions(lang="pl", duration="weekend")
        self.assertTrue(len(weekend_cards) > 0)
        for card in weekend_cards:
            self.assertEqual(card["duration_category"], "weekend")

        week_cards = get_curated_fallback_suggestions(lang="pl", duration="week")
        self.assertTrue(len(week_cards) > 0)
        for card in week_cards:
            self.assertEqual(card["duration_category"], "week")

        expedition_cards = get_curated_fallback_suggestions(lang="pl", duration="expedition")
        self.assertTrue(len(expedition_cards) > 0)
        for card in expedition_cards:
            self.assertEqual(card["duration_category"], "expedition")

    def test_get_curated_fallback_suggestions_multilang(self):
        """Verify German and English localized fallbacks with duration and RAG reasons."""
        de_cards = get_curated_fallback_suggestions(lang="de")
        self.assertEqual(len(de_cards), 4)
        self.assertTrue(any("Toskana" in c["title"] for c in de_cards))
        self.assertTrue(any("Landstrom 230V" in c["tags"] for c in de_cards))
        for c in de_cards:
            self.assertIn("rag_reason", c)
            self.assertIn("duration_category", c)

        en_cards = get_curated_fallback_suggestions(lang="en")
        self.assertEqual(len(en_cards), 4)
        self.assertTrue(any("Tuscan" in c["title"] for c in en_cards))
        self.assertTrue(any("230V Shore Power" in c["vw_highlights"] for c in en_cards))
        for c in en_cards:
            self.assertIn("rag_reason", c)
            self.assertIn("duration_category", c)

    def test_generate_dynamic_suggestions_mocked_llm(self):
        """Verify dynamic suggestions generation with duration and rag_reason from mocked LLM response."""
        mock_llm_json = {
            "suggestions": [
                {
                    "id": "dyn-wine-1",
                    "category": "wine_gastronomy",
                    "duration_category": "weekend",
                    "duration_days": 3,
                    "title": "Winnice Morawskie i Spokój",
                    "subtitle": "Klimatyczne piwniczki, degustacje i cichy kemping wśród winorośli.",
                    "tags": ["Winnice", "Slow Travel", "Prąd 230V"],
                    "prompt": "Zaplanuj 3 dni na Morawach camperem VW California z naciskiem na winnice.",
                    "badge": "Dopasowane do Ciebie ✨",
                    "rag_matched": True,
                    "rag_reason": "Polecamy, ponieważ w swoich preferencjach cenisz degustacje lokalnych win i spokój.",
                    "vw_highlights": ["Przyłącze 230V", "Trasa widokowa"],
                    "inferred_preference": "Lubi podróżować szlakiem winnic i degustacji regionalnych",
                }
            ]
        }

        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_choice = MagicMock()
        mock_choice.message.content = json.dumps(mock_llm_json)
        mock_response.choices = [mock_choice]
        mock_client.chat.completions.create.return_value = mock_response

        with patch("tools.travel_suggestions.get_client", return_value=mock_client), \
             patch("tools.travel_suggestions.list_user_memories", return_value=[{"content": "Uwielbia wino", "polarity": "like"}]):

            results = generate_dynamic_suggestions(user_id="test-user-uuid", lang="pl", count=1, duration="weekend")

            self.assertEqual(len(results), 1)
            card = results[0]
            self.assertEqual(card["title"], "Winnice Morawskie i Spokój")
            self.assertEqual(card["duration_category"], "weekend")
            self.assertEqual(card["duration_days"], 3)
            self.assertEqual(card["rag_reason"], "Polecamy, ponieważ w swoich preferencjach cenisz degustacje lokalnych win i spokój.")
            self.assertTrue(card["rag_matched"])
            self.assertEqual(card["badge"], "Dopasowane do Ciebie ✨")
            self.assertEqual(card["image_url"], SCENIC_THEME_IMAGES["wine_gastronomy"])
            self.assertEqual(card["inferred_preference"], "Lubi podróżować szlakiem winnic i degustacji regionalnych")

    def test_generate_dynamic_suggestions_german(self):
        """Verify dynamic German suggestions produce German system instructions and German content."""
        mock_llm_json = {
            "suggestions": [
                {
                    "id": "dyn-lakes-de-1",
                    "category": "lakes_mountains",
                    "duration_category": "weekend",
                    "duration_days": 3,
                    "title": "Bayerische Seen & Bergzauber",
                    "subtitle": "Kristallklare Bergseen, malerische Ausblicke und erholsame Stunden auf Campingplätzen am See.",
                    "tags": ["Bayern", "Seen", "Erholung"],
                    "prompt": "Plane für mich eine 3-tägige Reise mit dem VW California mit Start ab: München. Ziel: Chiemsee.",
                    "badge": "Auf Dich abgestimmt ✨",
                    "rag_matched": True,
                    "rag_reason": "Perfekt für Deine Vorliebe für ruhige Uferstellplätze und Alpenpanoramen.",
                    "vw_highlights": ["230V Stromanschluss", "Stellplatz am See"],
                    "inferred_preference": "Liebt ruhige Seen und Alpenlandschaften",
                }
            ]
        }

        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_choice = MagicMock()
        mock_choice.message.content = json.dumps(mock_llm_json)
        mock_response.choices = [mock_choice]
        mock_client.chat.completions.create.return_value = mock_response

        with patch("tools.travel_suggestions.get_client", return_value=mock_client):
            results = generate_dynamic_suggestions(user_id=None, lang="de", count=1, duration="weekend", user_location="München")

            self.assertEqual(len(results), 1)
            card = results[0]
            self.assertEqual(card["title"], "Bayerische Seen & Bergzauber")
            self.assertEqual(card["badge"], "Auf Dich abgestimmt ✨")
            self.assertIn("3-tägige Reise", card["prompt"])
            self.assertIn("München", card["prompt"])

            # Verify the prompt sent to OpenAI was in German
            args, kwargs = mock_client.chat.completions.create.call_args
            system_msg = kwargs["messages"][0]["content"]
            user_msg = kwargs["messages"][1]["content"]
            self.assertIn("Du bist das Modul für Reiseinspirationen", system_msg)
            self.assertIn("Antworte ausnahmslos auf Deutsch!", user_msg)

    def test_generate_dynamic_suggestions_leak_fallback(self):
        """Verify that if the LLM hallucinates Polish when German requested, leak detector replaces with German fallback."""
        mock_leaked_json = {
            "suggestions": [
                {
                    "id": "leak-1",
                    "category": "lakes_mountains",
                    "duration_category": "weekend",
                    "duration_days": 3,
                    "title": "Mazurskie Słoneczne Poranki",
                    "subtitle": "Odkryj krystaliczne jeziora i malownicze szlaki wśród natury, ciesząc się spokojem.",
                    "tags": ["Mazury", "relaks"],
                    "prompt": "Zaplanuj 3 dni...",
                    "badge": "Natura & Relaks",
                    "rag_matched": True,
                    "rag_reason": "Idealne połączenie naturalnych piękności z kempingiem.",
                }
            ]
        }

        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_choice = MagicMock()
        mock_choice.message.content = json.dumps(mock_leaked_json)
        mock_response.choices = [mock_choice]
        mock_client.chat.completions.create.return_value = mock_response

        with patch("tools.travel_suggestions.get_client", return_value=mock_client):
            results = generate_dynamic_suggestions(user_id=None, lang="de", count=1, duration="weekend")
            self.assertEqual(len(results), 1)
            card = results[0]
            # Must NOT be Polish Mazury, must be German fallback!
            self.assertNotEqual(card["title"], "Mazurskie Słoneczne Poranki")
            self.assertTrue(card["id"].startswith("curated-"))
            self.assertIn("de", card["id"])

    def test_generate_dynamic_suggestions_fallback_on_error(self):
        """Verify graceful fallback when LLM encounters an error with duration filter preserved."""
        mock_client = MagicMock()
        mock_client.chat.completions.create.side_effect = RuntimeError("OpenAI connection timed out")

        with patch("tools.travel_suggestions.get_client", return_value=mock_client):
            results = generate_dynamic_suggestions(user_id=None, lang="pl", count=2, duration="weekend")
            self.assertTrue(len(results) > 0)
            self.assertTrue(results[0]["id"].startswith("curated-"))
            self.assertEqual(results[0]["duration_category"], "weekend")

    def test_record_suggestion_choice_rag(self):
        """Verify recording a selected suggestion into user memories (RAG write path)."""
        mock_save = MagicMock(return_value={"id": "mem-123", "action": "created"})

        with patch("tools.travel_suggestions.save_user_memory", mock_save):
            card = {
                "title": "Toskański Szlak",
                "category": "wine_gastronomy",
                "inferred_preference": "Preferuje spokojne trasy przez winnice i kempingi premium",
            }
            res = record_suggestion_choice("user-456", card)

            self.assertIsNotNone(res)
            self.assertEqual(res["id"], "mem-123")
            mock_save.assert_called_once()
            _, kwargs = mock_save.call_args
            self.assertEqual(kwargs["user_id"], "user-456")
            self.assertEqual(kwargs["category"], "activities")
            self.assertEqual(kwargs["content"], "Preferuje spokojne trasy przez winnice i kempingi premium")

    def test_api_get_travel_suggestions(self):
        """Test GET /api/travel_suggestions endpoint with duration and location filter."""
        app.config["TESTING"] = True
        with app.test_client() as client:
            with patch("tools.server.generate_dynamic_suggestions") as mock_gen:
                mock_gen.return_value = get_curated_fallback_suggestions(lang="pl", duration="weekend")[:2]
                resp = client.get("/api/travel_suggestions?lang=pl&count=2&duration=weekend&location=Pozna%C5%84%2C%20Polska")

                self.assertEqual(resp.status_code, 200)
                data = resp.get_json()
                self.assertEqual(data["status"], "success")
                self.assertEqual(data["duration"], "weekend")
                self.assertEqual(data["user_location"], "Poznań, Polska")
                self.assertEqual(len(data["suggestions"]), 1)
                self.assertEqual(data["suggestions"][0]["duration_category"], "weekend")
                mock_gen.assert_called_once_with(user_id=None, lang="pl", count=2, duration="weekend", user_location="Poznań, Polska")

    def test_api_select_travel_suggestion(self):
        """Test POST /api/travel_suggestions/select endpoint."""
        app.config["TESTING"] = True
        with app.test_client() as client:
            with patch("tools.server.record_suggestion_choice") as mock_record:
                mock_record.return_value = {"id": "mem-999", "content": "Winnice"}

                payload = {
                    "suggestion": {
                        "title": "Szlak Winnic",
                        "category": "wine_gastronomy",
                        "prompt": "Zaplanuj mi 5 dni w winnicach",
                    }
                }
                with client.session_transaction() as sess:
                    sess["user_id"] = "test-user-id"

                resp = client.post("/api/travel_suggestions/select", json=payload)
                self.assertEqual(resp.status_code, 200)
                data = resp.get_json()
                self.assertEqual(data["status"], "success")
                self.assertEqual(data["prompt"], "Zaplanuj mi 5 dni w winnicach")
                self.assertTrue(data["rag_memory_recorded"])

    def test_travel_suggestions_modal_tablet_html_structure(self):
        """Verify HTML contains header-wrap and scrollable body to prevent tablet clipping."""
        html_path = os.path.join(ROOT, "frontend", "index.html")
        with open(html_path, "r", encoding="utf-8") as f:
            html = f.read()

        self.assertIn('class="travel-suggestions-header-wrap"', html)
        self.assertIn('class="travel-suggestions-body"', html)
        self.assertIn('id="travel-suggestions-close"', html)
        self.assertIn('class="travel-suggestions-footer"', html)

    def test_travel_suggestions_modal_tablet_css(self):
        """Verify CSS defines 100dvh, flex-start overflow, and max-height 820px media queries."""
        css_path = os.path.join(ROOT, "frontend", "styles.css")
        with open(css_path, "r", encoding="utf-8") as f:
            css = f.read()

        self.assertIn("height: 100dvh;", css)
        self.assertIn(".travel-suggestions-header-wrap", css)
        self.assertIn(".travel-suggestions-body", css)
        self.assertIn("@media (max-height: 820px)", css)
        self.assertIn(".suggestion-card-image-wrap", css)


if __name__ == "__main__":
    unittest.main()

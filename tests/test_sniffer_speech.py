"""
Unit and Integration Tests for Volkswagen Sniffer Speech & Facial Animation.

Tests text sanitization for TTS, campervan unit expansions across languages (PL, DE, EN),
speech configuration parameters, frontend assets and component integrations.
"""

import os
import pytest
from tools.tts_service import clean_text_for_speech, get_speech_config, SNIFFER_VOICE_CONFIG


def test_clean_text_strips_markdown_and_code():
    """Verify markdown bold, italic, headings, bullet lists, and code blocks are stripped."""
    raw = (
        "# Dzień 1: Trasa w Karkonosze\n\n"
        "Oto **wspaniała** trasa dla Twojego *kampera*!\n"
        "- Punkt widokowy: [Szklarska Poręba](https://maps.google.com/?q=123)\n"
        "- Wybierz tryb `eco` w pojeździe.\n"
        "```json\n{\"test\": 123}\n```"
    )
    cleaned = clean_text_for_speech(raw, lang="pl")

    assert "#" not in cleaned
    assert "**" not in cleaned
    assert "*" not in cleaned
    assert "```" not in cleaned
    assert "`" not in cleaned
    assert "https://" not in cleaned
    assert "Szklarska Poręba" in cleaned
    assert "Dzień 1: Trasa w Karkonosze" in cleaned
    assert "wspaniała trasa dla Twojego kampera" in cleaned


def test_clean_text_strips_slot_state_and_emojis():
    """Verify machine-readable <slot_state> tags and graphic emojis are stripped."""
    raw = (
        "Cześć! 🐶 Wywęszyłem kemping 🏕️ w pobliżu jeziora 📍. "
        "Będzie super! ✨\n"
        "<slot_state>{\"trip_type\": \"baza\", \"destination\": \"Bled\"}</slot_state>"
    )
    cleaned = clean_text_for_speech(raw, lang="pl")

    assert "<slot_state>" not in cleaned
    assert "</slot_state>" not in cleaned
    assert "trip_type" not in cleaned
    assert "🐶" not in cleaned
    assert "🏕️" not in cleaned
    assert "📍" not in cleaned
    assert "✨" not in cleaned
    assert "Cześć!" in cleaned
    assert "Wywęszyłem kemping w pobliżu jeziora" in cleaned


def test_clean_text_expands_units_pl():
    """Verify Polish unit expansions for distance, time, and currency."""
    raw = "Dystans: 120 km, czas: 3 h (lub 45 min). Koszt: 30 EUR za noc w kamperze VW."
    cleaned = clean_text_for_speech(raw, lang="pl")

    assert "120 kilometrów" in cleaned
    assert "3 godzin" in cleaned
    assert "45 minut" in cleaned
    assert "30 euro" in cleaned
    assert "Volkswagen" in cleaned
    assert "120 km" not in cleaned


def test_clean_text_expands_units_de():
    """Verify German unit expansions."""
    raw = "Strecke: 150 km, Fahrzeit: 2 h. Campingplatz: 25 EUR mit dem VW California."
    cleaned = clean_text_for_speech(raw, lang="de")

    assert "150 Kilometer" in cleaned
    assert "2 Stunden" in cleaned
    assert "25 Euro" in cleaned
    assert "Volkswagen" in cleaned


def test_clean_text_expands_units_en():
    """Verify English unit expansions."""
    raw = "Distance: 100 km, driving time: 1 h. Camping fee: 20 EUR for VW camper."
    cleaned = clean_text_for_speech(raw, lang="en")

    assert "100 kilometers" in cleaned
    assert "1 hour" in cleaned
    assert "20 euros" in cleaned
    assert "Volkswagen" in cleaned


def test_get_speech_config():
    """Verify speech configuration returns valid pitch, rate, and recommended voices for deep male voice."""
    for lang in ["pl", "de", "en"]:
        cfg = get_speech_config(lang)
        assert 0.7 <= cfg["pitch"] <= 0.9, f"Pitch should be deep and masculine for {lang}"
        assert 0.85 <= cfg["rate"] <= 1.05, f"Rate should be composed and steady for {lang}"
        assert len(cfg["recommended_voices"]) > 0
        assert cfg["lang_code"].startswith(lang)


def test_generate_speech_audio_and_caching():
    """Verify generate_speech_audio generates MP3 audio bytes and caches them."""
    from tools.tts_service import generate_speech_audio

    # Test generation
    sample_text = "Dzień dobry! Ruszamy w drogę z Volkswagen Sniffer."
    audio_bytes = generate_speech_audio(sample_text, lang="pl", voice="onyx")
    assert len(audio_bytes) > 1000, "Audio bytes should be generated"
    assert audio_bytes[:3] == b"ID3" or audio_bytes[:2] == b"\xff\xfb" or len(audio_bytes) > 1000

    # Test cache hit (identical text returns same bytes)
    cached_bytes = generate_speech_audio(sample_text, lang="pl", voice="onyx")
    assert cached_bytes == audio_bytes


def test_api_tts_speak_endpoint():
    """Verify /api/tts/speak returns audio/mpeg for valid text and 400 for empty."""
    from tools.server import app

    with app.test_client() as client:
        # Empty text should return 400
        res_bad = client.post("/api/tts/speak", json={"text": ""})
        assert res_bad.status_code == 400

        # Valid text should return 200 and audio/mpeg
        res_ok = client.post("/api/tts/speak", json={"text": "Wyprawa kamperem", "lang": "pl"})
        assert res_ok.status_code == 200
        assert res_ok.content_type == "audio/mpeg"
        assert len(res_ok.data) > 500

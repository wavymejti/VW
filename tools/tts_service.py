"""
Volkswagen Sniffer Text-to-Speech and Speech Configuration Service.

Provides text sanitization for speech synthesis, voice parameter configurations
(pitch, rate, language-specific voice candidates), and campervan unit expansion
for the Volkswagen Sniffer companion.
"""

import os
import re
import hashlib
from typing import Dict, Any, List, Optional
from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()


# Recommended voice parameters for Sniffer persona (Deep male voice)
SNIFFER_VOICE_CONFIG = {
    "pitch": 0.80,  # Deep, resonant masculine tone for warm campervan captain
    "rate": 0.95,   # Composed, steady pace
    "volume": 1.0,
    "languages": {
        "pl": {
            "code": "pl-PL",
            "recommended_voices": [
                "Marek", "Krzysztof", "Jan", "Jacek",
                "Microsoft Marek Online (Natural) - Polish (Poland)",
                "Google polski",
            ],
            "units": {
                r"\b(\d+)\s*km\b": r"\1 kilometrów",
                r"\b1\s*km\b": "1 kilometr",
                r"\b(\d+)\s*h\b": r"\1 godzin",
                r"\b1\s*h\b": "1 godzina",
                r"\b(\d+)\s*godz\b": r"\1 godzin",
                r"\b(\d+)\s*min\b": r"\1 minut",
                r"\b(\d+)\s*(?:EUR|eur|€)\b": r"\1 euro",
                r"\bVW\b": "Volkswagen",
            },
        },
        "de": {
            "code": "de-DE",
            "recommended_voices": [
                "Conrad", "Stefan", "Markus", "Florian",
                "Microsoft Conrad Online (Natural) - German (Germany)",
                "Google Deutsch",
            ],
            "units": {
                r"\b(\d+)\s*km\b": r"\1 Kilometer",
                r"\b1\s*km\b": "1 Kilometer",
                r"\b(\d+)\s*h\b": r"\1 Stunden",
                r"\b1\s*h\b": "1 Stunde",
                r"\b(\d+)\s*min\b": r"\1 Minuten",
                r"\b(\d+)\s*(?:EUR|eur|€)\b": r"\1 Euro",
                r"\bVW\b": "Volkswagen",
            },
        },
        "en": {
            "code": "en-US",
            "recommended_voices": [
                "Guy", "Christopher", "George", "David",
                "Microsoft Guy Online (Natural) - English (United States)",
                "Google US English",
            ],
            "units": {
                r"\b(\d+)\s*km\b": r"\1 kilometers",
                r"\b1\s*km\b": "1 kilometer",
                r"\b(\d+)\s*h\b": r"\1 hours",
                r"\b1\s*h\b": "1 hour",
                r"\b(\d+)\s*min\b": r"\1 minutes",
                r"\b(\d+)\s*(?:EUR|eur|€)\b": r"\1 euros",
                r"\bVW\b": "Volkswagen",
            },
        },
    },
}


def clean_text_for_speech(text: str, lang: str = "pl") -> str:
    """
    Sanitize raw assistant chat text for natural speech synthesis.

    Strips markdown formatting, technical slot XML blocks, emojis, links,
    and converts campervan abbreviations (km, h, EUR) into spoken forms.

    Args:
        text: Raw text string from assistant message.
        lang: Target language code ('pl', 'de', 'en').

    Returns:
        str: Clean, speakable text ready for TTS.
    """
    if not text:
        return ""

    sanitized = text

    # 1. Remove machine-readable <slot_state> tags and other XML/HTML tags
    sanitized = re.sub(r"<slot_state>[\s\S]*?</slot_state>", "", sanitized, flags=re.IGNORECASE)
    sanitized = re.sub(r"<[^>]+>", "", sanitized)

    # 2. Remove code blocks and inline code
    sanitized = re.sub(r"```[\s\S]*?```", "", sanitized)
    sanitized = re.sub(r"`([^`]+)`", r"\1", sanitized)

    # 3. Strip Markdown images and links [text](url) -> text
    sanitized = re.sub(r"!\[.*?\]\(.*?\)", "", sanitized)
    sanitized = re.sub(r"\[(.*?)\]\(.*?\)", r"\1", sanitized)

    # 4. Strip Markdown headers (#, ##, ###)
    sanitized = re.sub(r"^#{1,6}\s+", "", sanitized, flags=re.MULTILINE)

    # 5. Strip Markdown bold/italic (***text***, **text**, *text*, __text__, _text_)
    sanitized = re.sub(r"\*{1,3}(.*?)\*{1,3}", r"\1", sanitized)
    sanitized = re.sub(r"_{1,3}(.*?)_{1,3}", r"\1", sanitized)

    # 6. Clean bullet list markers (*, -, +, •) at start of lines
    sanitized = re.sub(r"^\s*[-*+•]\s+", "", sanitized, flags=re.MULTILINE)

    # 7. Convert campervan abbreviations to spoken words
    lang_key = lang.lower() if lang in SNIFFER_VOICE_CONFIG["languages"] else "pl"
    unit_map = SNIFFER_VOICE_CONFIG["languages"][lang_key]["units"]
    for pattern, replacement in unit_map.items():
        sanitized = re.sub(pattern, replacement, sanitized, flags=re.IGNORECASE)

    # 8. Strip common emojis and special non-speech symbols
    # Covers emoticons, transport/map symbols, flags, dingbats
    emoji_pattern = re.compile(
        "[\U00010000-\U0010ffff"
        "\u2600-\u26FF"
        "\u2700-\u27BF"
        "\u2300-\u23FF"
        "\u2B50-\u2B55"
        "\u200D"
        "\uFE0F"
        "]+",
        flags=re.UNICODE,
    )
    sanitized = emoji_pattern.sub("", sanitized)

    # 9. Clean up multiple spaces, empty lines, and excessive punctuation
    sanitized = re.sub(r"\s+", " ", sanitized)
    sanitized = re.sub(r"\s*([.,?!;:])\s*", r"\1 ", sanitized)
    sanitized = sanitized.strip()

    return sanitized


def get_speech_config(lang: str = "pl") -> Dict[str, Any]:
    """
    Get speech configuration and parameters for the specified language.

    Args:
        lang: Target language code ('pl', 'de', 'en').

    Returns:
        Dict[str, Any]: Configuration dictionary with pitch, rate, and voice candidates.
    """
    lang_key = lang.lower() if lang in SNIFFER_VOICE_CONFIG["languages"] else "pl"
    lang_data = SNIFFER_VOICE_CONFIG["languages"][lang_key]

    return {
        "lang_code": lang_data["code"],
        "pitch": SNIFFER_VOICE_CONFIG["pitch"],
        "rate": SNIFFER_VOICE_CONFIG["rate"],
        "volume": SNIFFER_VOICE_CONFIG["volume"],
        "recommended_voices": lang_data["recommended_voices"],
    }


# ElevenLabs Voice Configuration
DEFAULT_ELEVENLABS_VOICE_ID = "nPczCjzI2devNBz1zQrb"  # Brian - Deep, Resonant and Comforting
DEFAULT_ELEVENLABS_MODEL_ID = "eleven_multilingual_v2"
ELEVENLABS_API_URL = "https://api.elevenlabs.io/v1/text-to-speech"


def generate_speech_audio(
    text: str,
    lang: str = "pl",
    voice: str = "onyx",
    model: str = "tts-1",
    eleven_voice_id: Optional[str] = None,
    prefer_elevenlabs: bool = True,
) -> bytes:
    """
    Generate natural human neural speech audio.
    Prioritizes ElevenLabs ultra-realistic neural speech (Brian voice, deep masculine),
    falling back to OpenAI TTS ('onyx'), with disk caching.

    Args:
        text: Raw or formatted chat text.
        lang: Language code ('pl', 'de', 'en').
        voice: OpenAI Voice identifier ('onyx' for deep, warm male voice).
        model: OpenAI TTS model name ('tts-1').
        eleven_voice_id: Optional ElevenLabs voice ID (defaults to Brian: 'nPczCjzI2devNBz1zQrb').
        prefer_elevenlabs: Whether to try ElevenLabs first if key is available.

    Returns:
        bytes: MP3 audio bytes.
    """
    cleaned = clean_text_for_speech(text, lang)
    if not cleaned:
        return b""

    cache_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), ".tmp", "audio_cache")
    os.makedirs(cache_dir, exist_ok=True)

    eleven_key = os.getenv("ELEVENLABS_API_KEY")

    # 1. Try ElevenLabs first if preferred and API key is present
    if prefer_voice := (prefer_elevenlabs and eleven_key):
        voice_id = eleven_voice_id or DEFAULT_ELEVENLABS_VOICE_ID
        cache_hash = hashlib.sha256(
            f"elevenlabs|{cleaned}|{lang}|{voice_id}|{DEFAULT_ELEVENLABS_MODEL_ID}".encode("utf-8")
        ).hexdigest()
        cache_path = os.path.join(cache_dir, f"tts_eleven_{cache_hash}.mp3")

        if os.path.exists(cache_path) and os.path.getsize(cache_path) > 0:
            with open(cache_path, "rb") as f:
                return f.read()

        try:
            import requests

            url = f"{ELEVENLABS_API_URL}/{voice_id}"
            headers = {
                "xi-api-key": eleven_key,
                "Content-Type": "application/json",
                "Accept": "audio/mpeg",
            }
            payload = {
                "text": cleaned,
                "model_id": DEFAULT_ELEVENLABS_MODEL_ID,
                "voice_settings": {
                    "stability": 0.50,
                    "similarity_boost": 0.75,
                    "style": 0.0,
                    "use_speaker_boost": True,
                },
            }

            resp = requests.post(url, json=payload, headers=headers, timeout=25)
            if resp.status_code == 200 and len(resp.content) > 0:
                with open(cache_path, "wb") as f:
                    f.write(resp.content)
                return resp.content
            else:
                print(f"[TTS] ElevenLabs API error {resp.status_code}: {resp.text}. Falling back to OpenAI.")
        except Exception as e:
            print(f"[TTS] ElevenLabs request failed: {e}. Falling back to OpenAI.")

    # 2. Fallback to OpenAI TTS
    cache_hash = hashlib.sha256(f"openai|{cleaned}|{lang}|{voice}|{model}".encode("utf-8")).hexdigest()
    cache_path = os.path.join(cache_dir, f"tts_openai_{cache_hash}.mp3")

    if os.path.exists(cache_path) and os.path.getsize(cache_path) > 0:
        with open(cache_path, "rb") as f:
            return f.read()

    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise ValueError("Neither ELEVENLABS_API_KEY nor OPENAI_API_KEY is available for TTS.")

    client = OpenAI(api_key=api_key)
    response = client.audio.speech.create(
        model=model,
        voice=voice,
        input=cleaned,
        response_format="mp3",
    )

    audio_bytes = response.content
    with open(cache_path, "wb") as f:
        f.write(audio_bytes)

    return audio_bytes

"""
What the 3D Sniffer says out loud after a chat reply.

Sniffer reads the chat reply word for word (decision 2026-11-17), in English, because his voice
and lip-sync are English-only:
- reply in English: the reply itself, made speakable (no markdown, emoji, list markers;
  units spelled out) — deterministic, no LLM needed for the words;
- reply in Polish/German: a faithful English translation of the whole reply (not a summary).
One small LLM call picks his mood and reaction (and translates when needed).

A failure here never breaks the chat: the caller gets None and Sniffer stays quiet; for an
English reply he still reads the text with a neutral face.
"""

import json
import os
import re

from tools.openai_client import get_client, MODEL_NAME, chat_kwargs
from tools.tts_service import clean_text_for_speech

# Separate setting so this call can use a faster/cheaper model than the planner.
SNIFFER_LINE_MODEL = os.getenv("SNIFFER_LINE_MODEL", MODEL_NAME)

MOODS = ["neutral", "happy", "angry", "sad", "fear", "disgust", "love", "sleep"]
REACTIONS = ["none", "surprise", "ears_up", "ears_back", "petted"]

INSTRUCTIONS = """\
You are Sniffer, a friendly cartoon dog and the mascot of Volkswagen California camper vans.
You get the user's message and the reply the trip planner just showed on screen; you will read
that reply out loud. Return:

- mood: mostly "neutral" or "happy"; "sad" when the reply apologizes or brings bad news; the
  others only when they clearly fit.
- reaction: "surprise" for something exciting, "ears_up" when the reply asks the user something
  or shows interest, "ears_back" for an apology or a problem, "petted" when the user praises you
  or calls you a good dog, otherwise "none".
- english: the reply in English, word for word as it should be read aloud. If the reply is
  already in English, return an empty string. Otherwise translate the WHOLE reply faithfully,
  sentence by sentence: do not summarize, shorten or add anything. Plain speakable text: no
  markdown, emoji or URLs; list items become separate sentences; write numbers and units the way
  they are said ("about 420 kilometers").
"""

RESPONSE_FORMAT = {
    "type": "json_schema",
    "json_schema": {
        "name": "sniffer_line",
        "strict": True,
        "schema": {
            "type": "object",
            "properties": {
                "mood": {"type": "string", "enum": MOODS},
                "reaction": {"type": "string", "enum": REACTIONS},
                "english": {"type": "string"},
            },
            "required": ["mood", "reaction", "english"],
            "additionalProperties": False,
        },
    },
}


def speakable(text, lang="en"):
    """Chat text (markdown) -> plain sentences for TTS, keeping the wording."""
    if not text:
        return ""
    lines = []
    for raw in text.splitlines():
        line = raw.strip()
        if not line:
            continue
        line = re.sub(r"^\d+[.)]\s+", "", line)  # "1. Where..." -> "Where..."
        line = re.sub(r"^[-*+•]\s+", "", line)
        # A list item or heading without end punctuation would run into the next line.
        if not re.search(r"[.!?:;…]$", re.sub(r"[*_`)\]\"']+$", "", line)):
            line += "."
        lines.append(line)
    out = clean_text_for_speech("\n".join(lines), lang=lang)
    out = re.sub(r"(\d)\. (\d)", r"\1.\2", out)  # undo "4. 5" from punctuation spacing
    out = re.sub(r"\.\s*\.", ".", out)
    return out.strip()


def make_sniffer_line(user_message, reply_text, lang="en", client=None):
    """
    Returns {"spoken", "mood", "reaction"} for the 3D Sniffer, or None.

    Args:
        user_message (str): What the user wrote.
        reply_text (str): The planner's reply shown in the chat.
        lang (str): Language of the chat ('en', 'pl', 'de').
        client: Optional OpenAI client (tests).
    """
    if not reply_text or not reply_text.strip():
        return None
    is_english = (lang or "en").lower().startswith("en")
    english_text = speakable(reply_text, "en") if is_english else ""

    line = {}
    try:
        client = client or get_client()
        response = client.chat.completions.create(
            model=SNIFFER_LINE_MODEL,
            messages=[
                {"role": "system", "content": INSTRUCTIONS},
                {
                    "role": "user",
                    "content": f"User message:\n{user_message[:1500]}\n\nPlanner reply on screen:\n{reply_text[:6000]}",
                },
            ],
            response_format=RESPONSE_FORMAT,
            timeout=30,
            **chat_kwargs(max_tokens=200 if is_english else 1500, temperature=0.3,
                          model=SNIFFER_LINE_MODEL),
        )
        line = json.loads(response.choices[0].message.content)
    except Exception as e:  # noqa: BLE001 — Sniffer must never break the chat
        print(f"[sniffer_line] LLM part skipped: {e}")

    if not is_english:
        english_text = speakable(str(line.get("english", "")), "en")
    if not english_text:
        return None
    return {
        "spoken": english_text,
        "mood": line.get("mood") if line.get("mood") in MOODS else "neutral",
        "reaction": line.get("reaction") if line.get("reaction") in REACTIONS else "none",
    }

"""
What the 3D Sniffer says out loud after a chat reply.

The chat reply in VW is long (markdown, lists of campsites, the user's language). The 3D Sniffer
(AVW module, see architecture/sniffer_speech_sop.md) speaks short English lines with a mood, so
after each reply we ask the model for one: {"spoken", "mood", "reaction"}.

A failure here never breaks the chat: the caller gets None and Sniffer simply stays quiet.
"""

import json
import os

from tools.openai_client import get_client, MODEL_NAME

# Separate setting so the line can use a faster/cheaper model than the planner.
SNIFFER_LINE_MODEL = os.getenv("SNIFFER_LINE_MODEL", MODEL_NAME)
MAX_SPOKEN_WORDS = 45

MOODS = ["neutral", "happy", "angry", "sad", "fear", "disgust", "love", "sleep"]
REACTIONS = ["none", "surprise", "ears_up", "ears_back", "petted"]

INSTRUCTIONS = f"""\
You are Sniffer, a friendly cartoon dog and the mascot of Volkswagen California camper vans: a
curious, warm vanlife co-pilot who loves campsites, mountain passes and the open road.

You get the user's message and the full written reply that the trip planner just showed on
screen (it may be in Polish, German or English, with markdown and lists). Write what you say
out loud next to that reply, in English only, whatever the language of the conversation:

- spoken: one or two short sentences, under {MAX_SPOKEN_WORDS} words. Sum up the key point or ask
  the reply's main question in your own words; the details stay on screen, so don't read lists,
  addresses or many numbers. Plain spoken English: no markdown, emoji or URLs; write numbers the
  way they are said ("about 420 kilometers"). Warm, a little playful, an occasional dog joke at most.
- mood: mostly "neutral" or "happy"; "sad" when apologizing or for bad news; others only when
  they clearly fit.
- reaction: "surprise" for something exciting, "ears_up" for interest or a question to the
  user, "ears_back" for an apology or a problem, "petted" when the user praises you or calls
  you a good dog, otherwise "none".
"""

RESPONSE_FORMAT = {
    "type": "json_schema",
    "json_schema": {
        "name": "sniffer_line",
        "strict": True,
        "schema": {
            "type": "object",
            "properties": {
                "spoken": {"type": "string"},
                "mood": {"type": "string", "enum": MOODS},
                "reaction": {"type": "string", "enum": REACTIONS},
            },
            "required": ["spoken", "mood", "reaction"],
            "additionalProperties": False,
        },
    },
}


def make_sniffer_line(user_message, reply_text, client=None):
    """
    Returns {"spoken", "mood", "reaction"} for the 3D Sniffer, or None on any failure.

    Args:
        user_message (str): What the user wrote.
        reply_text (str): The planner's full reply shown in the chat.
        client: Optional OpenAI client (tests).
    """
    if not reply_text or not reply_text.strip():
        return None
    try:
        client = client or get_client()
        response = client.chat.completions.create(
            model=SNIFFER_LINE_MODEL,
            messages=[
                {"role": "system", "content": INSTRUCTIONS},
                {
                    "role": "user",
                    "content": f"User message:\n{user_message[:1500]}\n\nPlanner reply on screen:\n{reply_text[:4000]}",
                },
            ],
            response_format=RESPONSE_FORMAT,
            max_tokens=200,
            temperature=0.7,
            timeout=15,
        )
        line = json.loads(response.choices[0].message.content)
    except Exception as e:  # noqa: BLE001 — Sniffer must never break the chat
        print(f"[sniffer_line] skipped: {e}")
        return None

    spoken = " ".join(str(line.get("spoken", "")).split())
    if not spoken:
        return None
    return {
        "spoken": spoken,
        "mood": line.get("mood") if line.get("mood") in MOODS else "neutral",
        "reaction": line.get("reaction") if line.get("reaction") in REACTIONS else "none",
    }

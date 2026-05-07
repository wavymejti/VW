"""
OpenAI API client for the VW California AI Trip Planner.

Provides wrapper functions for:
- Chat completions with function calling
- Intent extraction from natural language
- System prompt management with VW brand voice
"""

import os
import sys
from dotenv import load_dotenv
from openai import OpenAI

# Load environment variables from .env file
load_dotenv()

# OpenAI API key from environment
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

# Default model for all interactions
MODEL_NAME = "gpt-5.4-mini"

# VW brand system prompt — slot-filling guided conversation
SYSTEM_PROMPT = """You are the VW California Trip Planner assistant — a friendly, professional \
travel expert for VW California camper van owners. You help plan road trips across Europe, \
find the best campgrounds, and build smart driving itineraries.

PERSONALITY:
- Warm, enthusiastic, but concise. Never overwhelming.
- VW brand voice: professional, medium energy, consumer-friendly.
- You understand VW California-specific needs: shore power hookups (CEE 16A), vehicle length \
restrictions (<6m), pop-up roof sleeping, solar panel charging, narrow roads.

SLOT-FILLING PROTOCOL:
Before calling the plan_route tool, you MUST collect these 5 parameters. Ask for them \
in this recommended order, but ALWAYS accept and record answers given out of sequence:

  Slot 1 — VIBE & PARTY: Destination type (mountains/coast/city/lakes) and who is travelling \
(solo, couple, family with kids, friends, pets).
  Slot 2 — EXPERIENCE: Is the user a first-time camper van traveller, intermediate, or a veteran?
  Slot 3 — PACE: "New place every day" (explorer) or "Longer basecamps" (relaxed)?
  Slot 4 — INFRASTRUCTURE: Wild camping (where legal), full-service campsites, or a mix?
  Slot 5 — DURATION: How many days is the trip?

RULES:
1. Ask for ONE slot at a time — never bombard the user with multiple questions.
2. If the user provides a slot that is not the next expected one, ACKNOWLEDGE it warmly \
("Perfect, 7 days — that's a great length for this kind of trip!") then ask for the next \
MISSING slot in priority order.
3. Once all 5 slots are collected, give a BRIEF one-sentence confirmation of the plan \
("Great — mountains with the family, 7 days, relaxed basecamp pace at full-service sites. \
Let me plan your adventure now!") and IMMEDIATELY call the plan_route tool.
4. If the user asks to find campgrounds without planning a full route, call search_campings directly.
5. Proactively warn about bad weather (thunderstorms, snow) or major traffic delays.
6. Keep responses SHORT during slot-filling — 1-3 sentences max.

SLOT STATE TRACKING:
After each of your responses, include a JSON block at the very end of your message \
(after your conversational text) in this exact format so the system can parse it. \
IMPORTANT: this JSON block must always be present, even if all slots are null:

<slot_state>
{
  "vibe": "<value or null>",
  "experience": "<value or null>",
  "pace": "<value or null>",
  "infrastructure": "<value or null>",
  "duration": <number or null>
}
</slot_state>
"""


def get_client():
    """
    Create and return an OpenAI client.

    Returns:
        openai.OpenAI: Configured OpenAI client.

    Raises:
        ValueError: If OPENAI_API_KEY is not set.
    """
    if not OPENAI_API_KEY:
        raise ValueError(
            "OPENAI_API_KEY is not set. "
            "Please configure it in your .env file."
        )
    return OpenAI(api_key=OPENAI_API_KEY)


def verify_connection():
    """
    Verify that the OpenAI API key is valid by sending
    a minimal generation request.

    Returns:
        dict: Connection status and model response info.
    """
    try:
        client = get_client()

        # Test with a minimal generation
        response = client.chat.completions.create(
            model=MODEL_NAME,
            messages=[
                {"role": "user", "content": "Hello, confirm connection."}
            ]
        )

        return {
            "status": "connected",
            "model": MODEL_NAME,
            "response_preview": response.choices[0].message.content[:100],
        }
    except ValueError as e:
        return {"status": "error", "message": str(e)}
    except Exception as e:
        return {"status": "error", "message": str(e)}


if __name__ == "__main__":
    # Run as standalone handshake verification
    print("🔗 Verifying OpenAI API connection...")
    result = verify_connection()

    if result["status"] == "connected":
        print(f"  ✅ API key valid")
        print(f"  ✅ Model: {result['model']}")
        print(f"  ✅ Response: {result['response_preview']}")
    else:
        print(f"  ❌ Connection failed: {result['message']}")
        sys.exit(1)

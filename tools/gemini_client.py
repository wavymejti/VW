"""
Google Gemini API client for the VW California AI Trip Planner.

Provides wrapper functions for:
- Chat completions with function calling
- Intent extraction from natural language
- System prompt management with VW brand voice
"""

import os
import sys
from dotenv import load_dotenv
from google import genai

# Load environment variables from .env file
load_dotenv()

# Gemini API key from environment
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

# Default model for all interactions
MODEL_NAME = "gemini-2.5-flash"

# VW brand system prompt for all chat interactions
SYSTEM_PROMPT = (
    "You are the VW California Trip Planner assistant. "
    "You help VW California camper van owners plan road trips, "
    "find campgrounds, and build driving itineraries. "
    "You are professional, friendly, and knowledgeable about "
    "camper van travel in Europe. "
    "When users describe their travel needs, extract structured "
    "information using the available tools. "
    "Always consider VW California-specific needs like shore power "
    "hookups and vehicle length restrictions."
)


def get_client():
    """
    Create and return a Google GenAI client.

    Returns:
        google.genai.Client: Configured Gemini client.

    Raises:
        ValueError: If GEMINI_API_KEY is not set.
    """
    if not GEMINI_API_KEY:
        raise ValueError(
            "GEMINI_API_KEY is not set. "
            "Please configure it in your .env file."
        )
    return genai.Client(api_key=GEMINI_API_KEY)


def verify_connection():
    """
    Verify that the Gemini API key is valid by sending
    a minimal generation request.

    Returns:
        dict: Connection status and model response info.
    """
    try:
        client = get_client()

        # Test with a minimal generation
        response = client.models.generate_content(
            model=MODEL_NAME,
            contents="Hello, confirm connection.",
        )

        return {
            "status": "connected",
            "model": MODEL_NAME,
            "response_preview": response.text[:100],
        }
    except ValueError as e:
        return {"status": "error", "message": str(e)}
    except Exception as e:
        return {"status": "error", "message": str(e)}


if __name__ == "__main__":
    # Run as standalone handshake verification
    print("🔗 Verifying Gemini API connection...")
    result = verify_connection()

    if result["status"] == "connected":
        print(f"  ✅ API key valid")
        print(f"  ✅ Model: {result['model']}")
        print(f"  ✅ Response: {result['response_preview']}")
    else:
        print(f"  ❌ Connection failed: {result['message']}")
        sys.exit(1)

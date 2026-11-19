"""Shared test setup."""
import os

# Tests mock the Google Maps clients and expect every feature to be callable; the app's
# default cost switch (GOOGLE_MAPS_MODE=lite) would short-circuit Places before the mocks.
os.environ["GOOGLE_MAPS_MODE"] = "full"

# Keep test chats out of the real logs/chat.jsonl.
import tempfile
os.environ["VW_CHAT_LOG_DIR"] = tempfile.mkdtemp(prefix="vw_chat_log_")

# The app runs English-only (APP_ENGLISH_ONLY); the multilingual tests keep checking PL/DE.
os.environ.setdefault("APP_ENGLISH_ONLY", "0")

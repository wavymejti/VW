"""
Unit tests for German (de) and Polish (pl) internationalization (i18n).
"""

import os
import json
import pytest
from unittest.mock import patch, MagicMock

from tools.openai_client import SYSTEM_PROMPT
from navigation.chat_handler import create_chat_session, send_message


def test_system_prompt_contains_multilingual_instructions():
    """Verify system prompt includes German and Polish language rules."""
    assert "Wielojęzyczność" in SYSTEM_PROMPT
    assert "de" in SYSTEM_PROMPT
    assert "pl" in SYSTEM_PROMPT


def test_chat_session_creation_with_language():
    """Verify chat session accepts and stores language code."""
    session_pl = create_chat_session(lang="pl")
    assert session_pl["lang"] == "pl"

    session_de = create_chat_session(lang="de")
    assert session_de["lang"] == "de"


@patch("navigation.chat_handler.get_client")
def test_send_message_injects_german_system_note(mock_get_client):
    """Verify send_message injects German language instruction system prompt."""
    mock_client = MagicMock()
    mock_completion = MagicMock()
    mock_completion.choices = [
        MagicMock(message=MagicMock(content="Hallo! Ich helfe dir beim Planen.", tool_calls=None))
    ]
    mock_client.chat.completions.create.return_value = mock_completion
    mock_get_client.return_value = mock_client

    session = create_chat_session(lang="de")
    response = send_message(session, "Hallo, ich möchte nach Bayern fahren.")

    # Check the call arguments passed to OpenAI completions
    calls = mock_client.chat.completions.create.call_args_list
    assert len(calls) > 0
    messages_sent = calls[0].kwargs.get("messages", [])
    
    # Ensure a system note with German instructions was included
    german_injection = any(
        m.get("role") == "system" and "German" in m.get("content", "")
        for m in messages_sent
    )
    assert german_injection, "German system note injection missing from messages"


def test_frontend_i18n_dictionary_file():
    """Verify frontend/i18n.js file exists and contains valid JS translation keys."""
    i18n_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "frontend", "i18n.js")
    assert os.path.exists(i18n_path), "frontend/i18n.js does not exist"
    
    with open(i18n_path, "r", encoding="utf-8") as f:
        content = f.read()

    assert "pl:" in content
    assert "de:" in content
    assert "nav_plan" in content
    assert "nav_map" in content

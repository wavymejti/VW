"""
Unit tests for German (de), Polish (pl), and English (en) internationalization (i18n).
"""

import os
import json
from unittest.mock import patch, MagicMock

from tools.openai_client import SYSTEM_PROMPT
from navigation.chat_handler import create_chat_session, send_message


def test_system_prompt_contains_multilingual_instructions():
    """Verify system prompt includes German, Polish, and English language rules."""
    assert "Wielojęzyczność" in SYSTEM_PROMPT
    assert "de" in SYSTEM_PROMPT
    assert "pl" in SYSTEM_PROMPT
    assert "en" in SYSTEM_PROMPT


def test_chat_session_creation_with_language():
    """Verify chat session accepts and stores language code."""
    session_pl = create_chat_session(lang="pl")
    assert session_pl["lang"] == "pl"

    session_de = create_chat_session(lang="de")
    assert session_de["lang"] == "de"

    session_en = create_chat_session(lang="en")
    assert session_en["lang"] == "en"


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


@patch("navigation.chat_handler.get_client")
def test_send_message_injects_english_system_note(mock_get_client):
    """Verify send_message injects English language instruction system prompt."""
    mock_client = MagicMock()
    mock_completion = MagicMock()
    mock_completion.choices = [
        MagicMock(message=MagicMock(content="Hello! I can help you plan your road trip.", tool_calls=None))
    ]
    mock_client.chat.completions.create.return_value = mock_completion
    mock_get_client.return_value = mock_client

    session = create_chat_session(lang="en")
    response = send_message(session, "Hello, I want to travel to Norway.")

    # Check the call arguments passed to OpenAI completions
    calls = mock_client.chat.completions.create.call_args_list
    assert len(calls) > 0
    messages_sent = calls[0].kwargs.get("messages", [])
    
    # Ensure a system note with English instructions was included
    english_injection = any(
        m.get("role") == "system" and "English" in m.get("content", "")
        for m in messages_sent
    )
    assert english_injection, "English system note injection missing from messages"


def test_frontend_i18n_dictionary_file():
    """Verify frontend/i18n.js file exists and contains valid JS translation keys."""
    i18n_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "frontend", "i18n.js")
    assert os.path.exists(i18n_path), "frontend/i18n.js does not exist"
    
    with open(i18n_path, "r", encoding="utf-8") as f:
        content = f.read()

    assert "pl:" in content
    assert "de:" in content
    assert "en:" in content
    assert "nav_plan" in content
    assert "nav_map" in content
    assert "lang_name_en" in content
    assert "welcome_user_greeting" in content
    assert "welcome_subtitle" in content
    assert "Wohin soll die Reise heute gehen?" in content
    assert "chat_welcome_heading" in content
    assert "hero_inspiration_badge" in content
    assert "hero_inspiration_title" in content
    assert "hero_inspiration_btn" in content


def test_language_switchers_in_html():
    """Verify both sidebar and chat header language switchers exist with pl/de/en options."""
    html_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "frontend", "index.html")
    assert os.path.exists(html_path)

    with open(html_path, "r", encoding="utf-8") as f:
        html = f.read()

    # Sidebar language trigger and flyout
    assert 'id="nav-lang-trigger"' in html
    assert 'id="nav-lang-flyout"' in html
    assert 'id="nav-current-lang-flag"' in html
    assert 'id="nav-current-lang-code"' in html

    # Header language dropdown
    assert 'id="chat-lang-dropdown"' in html
    assert 'id="btn-header-lang"' in html
    assert 'id="header-lang-menu"' in html
    assert 'id="header-lang-flag"' in html
    assert 'id="header-lang-code"' in html

    # All three language codes present in both menus
    for lang in ["pl", "de", "en"]:
        assert f'data-lang="{lang}"' in html


def test_tablet_chat_layout_constraints_in_css():
    """Verify CSS has constraints preventing chat input from being pushed offscreen on tablets."""
    css_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "frontend", "styles.css")
    assert os.path.exists(css_path)

    with open(css_path, "r", encoding="utf-8") as f:
        css = f.read()

    # Dynamic viewport height
    assert "height: 100dvh;" in css

    # #view-chat must NOT have unbounded scroll
    assert "#view-chat" in css
    assert "overflow: hidden !important;" in css

    # .chat-messages must allow shrinking and have its own scroll
    assert "min-height: 0 !important;" in css
    assert "overflow-y: auto !important;" in css

    # .chat-input-wrapper must never shrink or get pushed off
    assert "flex-shrink: 0 !important;" in css

    # #view-nav must NOT clip flyout popover
    assert "overflow: visible !important;" in css

    # Responsive height queries for landscape tablets & on-screen keyboards
    assert "@media (max-height: 820px)" in css
    assert "@media (max-height: 650px)" in css


def test_i18n_manager_updates_triggers():
    """Verify I18nManager updateStaticUI updates both nav and header triggers."""
    i18n_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "frontend", "i18n.js")
    with open(i18n_path, "r", encoding="utf-8") as f:
        content = f.read()

    assert "nav-current-lang-flag" in content
    assert "nav-current-lang-code" in content
    assert "header-lang-flag" in content
    assert "header-lang-code" in content

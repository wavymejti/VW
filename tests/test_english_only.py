"""English-only mode (Nov 2026): UI, chat replies and Sniffer in English."""

import tools.server as server


def test_lang_is_forced_to_english(monkeypatch):
    monkeypatch.setattr(server, "ENGLISH_ONLY", True)
    assert server._lang("pl") == "en" and server._lang(None) == "en"
    monkeypatch.setattr(server, "ENGLISH_ONLY", False)
    assert server._lang("de") == "de" and server._lang(None) == "pl"


def test_chat_sends_english_to_the_model(monkeypatch):
    monkeypatch.setattr(server, "ENGLISH_ONLY", True)
    seen = {}

    def fake_send(chat, message, trip_id=None, user_location=None):
        seen["lang"] = chat["lang"]
        return {"status": "success", "text": "Hi!", "tool_calls": []}

    monkeypatch.setattr(server, "create_chat_session",
                        lambda **k: {"history": [], "lang": k.get("lang"), "active_trip_id": None})
    monkeypatch.setattr(server, "send_message", fake_send)
    monkeypatch.setattr(server, "make_sniffer_line", lambda *a, **k: None)
    server._CHAT_SESSIONS.clear()
    with server.app.test_client() as c:
        c.post("/api/chat", json={"message": "Cześć", "lang": "pl", "conversation_id": "x"})
    assert seen["lang"] == "en"


def test_frontend_is_english_only():
    js = open("frontend/i18n.js", encoding="utf-8").read()
    assert "const ENGLISH_ONLY = true;" in js
    assert '<html lang="en">' in open("frontend/index.html", encoding="utf-8").read()


def test_english_note_insists_on_english():
    src = open("navigation/chat_handler.py", encoding="utf-8").read()
    assert "Always respond in English" in src

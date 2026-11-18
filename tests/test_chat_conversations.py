"""
A new chat on every page load (Nov 2026).

The frontend sends a conversation_id generated per page load; the server keeps
one in-memory session per id, so a reload starts fresh (no DB history, no active
trip from the cookie), and anonymous visitors no longer share one session.
"""

import pytest

import tools.server as server


@pytest.fixture
def client(monkeypatch):
    created = []

    def fake_create(user_id=None, trip_id=None, lang="pl", load_history=True):
        sess = {"history": [{"role": "system", "content": "P"}], "user_id": user_id,
                "trip_id": trip_id, "lang": lang, "active_trip_id": trip_id,
                "load_history": load_history}
        created.append(sess)
        return sess

    def fake_send(chat, message, trip_id=None, user_location=None):
        chat["history"].append({"role": "user", "content": message})
        if message.startswith("plan"):
            chat["active_trip_id"] = "trip-" + message.split()[-1]
        return {"status": "success", "text": "ok", "tool_calls": [],
                "seen": len(chat["history"]) - 1, "trip_id_arg": trip_id}

    monkeypatch.setattr(server, "create_chat_session", fake_create)
    monkeypatch.setattr(server, "send_message", fake_send)
    monkeypatch.setattr(server, "make_sniffer_line", lambda *a, **k: None)
    server._CHAT_SESSIONS.clear()
    server.app.config["TESTING"] = True
    with server.app.test_client() as c:
        c.created = created
        yield c
    server._CHAT_SESSIONS.clear()


def _chat(c, msg, conv=None):
    body = {"message": msg, "lang": "en"}
    if conv:
        body["conversation_id"] = conv
    return c.post("/api/chat", json=body).get_json()


def test_same_page_load_keeps_the_conversation(client):
    assert _chat(client, "hello", "page-1")["seen"] == 1
    assert _chat(client, "again", "page-1")["seen"] == 2


def test_reload_starts_a_fresh_chat_without_history_or_trip(client):
    _chat(client, "plan A", "page-1")          # active trip stored in the cookie
    r = _chat(client, "hello", "page-2")        # page reloaded
    assert r["seen"] == 1
    assert r["trip_id_arg"] is None
    fresh = client.created[-1]
    assert fresh["load_history"] is False and fresh["active_trip_id"] is None


def test_trip_planned_in_a_conversation_stays_in_it(client):
    _chat(client, "plan B", "page-1")
    assert _chat(client, "change it", "page-1")["trip_id_arg"] == "trip-B"


def test_anonymous_pages_do_not_share_a_session(client):
    _chat(client, "secret", "visitor-1")
    assert _chat(client, "hi", "visitor-2")["seen"] == 1


def test_old_clients_without_id_keep_one_session(client):
    _chat(client, "one")
    assert _chat(client, "two")["seen"] == 2


def test_session_count_is_capped(client, monkeypatch):
    monkeypatch.setattr(server, "_MAX_CHAT_SESSIONS", 3)
    for i in range(5):
        _chat(client, "hi", f"p{i}")
    assert len(server._CHAT_SESSIONS) == 3


def test_frontend_sends_a_per_load_conversation_id():
    js = open("frontend/app.js", encoding="utf-8").read()
    assert "const CHAT_CONVERSATION_ID" in js
    assert "conversation_id: CHAT_CONVERSATION_ID" in js

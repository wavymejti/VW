"""The van is kept in long-term memory (RAG) and used for stops (Nov 2026); DB mocked."""

import json
from types import SimpleNamespace

import pytest

from tools import user_memory as um


@pytest.mark.parametrize("text,key", [
    ("Podróżuje VW ID. Buzz (elektryczny)", "ev"),
    ("Drives an ID Buzz", "ev"),
    ("Fährt einen elektrischen Bus", "ev"),
    ("Has a California eHybrid", "phev"),
    ("Podróżuje VW California eHybrid (hybryda plug-in)", "phev"),
    ("Jeździ Californią T6.1", "diesel"),
    ("Drives a VW California Ocean", "diesel"),
    ("Ma markizę i bagażnik rowerowy", None),
    ("Travels with a dog", None),
])
def test_vehicle_key_from_text(text, key):
    assert um.vehicle_key_from_text(text) == key


def _store(monkeypatch, memories):
    """memories: newest first, like list_user_memories."""
    store = {"rows": list(memories), "saved": [], "deleted": []}
    monkeypatch.setattr(um, "list_user_memories", lambda uid, category=None: [
        m for m in store["rows"] if category in (None, m["category"])])

    def delete(uid, mid):
        store["deleted"].append(mid)
        store["rows"] = [m for m in store["rows"] if m["id"] != mid]
        return True

    def save(uid, content, category="general", polarity="like", confidence=1.0, embedding=None):
        store["saved"].append((content, category))
        store["rows"].insert(0, {"id": f"n{len(store['saved'])}", "category": category, "content": content})
        return {}

    monkeypatch.setattr(um, "delete_user_memory", delete)
    monkeypatch.setattr(um, "save_user_memory", save)
    return store


def test_newest_vehicle_memory_naming_a_model_wins(monkeypatch):
    _store(monkeypatch, [
        {"id": "1", "category": "vehicle", "content": "Ma markizę"},
        {"id": "2", "category": "vehicle", "content": "Teraz jeździ ID. Buzz"},
        {"id": "3", "category": "vehicle", "content": "Jeździ California T6.1"},
    ])
    assert um.remembered_vehicle("u") == "ev"
    assert um.remembered_vehicle(None) is None


def test_remember_vehicle_replaces_the_other_model_keeps_equipment(monkeypatch):
    store = _store(monkeypatch, [
        {"id": "1", "category": "vehicle", "content": "Ma markizę"},
        {"id": "2", "category": "vehicle", "content": "Jeździ California T6.1"},
    ])
    assert um.remember_vehicle("u", "ev") is True
    assert store["deleted"] == ["2"]
    assert store["saved"] == [("Podróżuje VW ID. Buzz (elektryczny)", "vehicle")]
    assert um.remembered_vehicle("u") == "ev"
    assert um.remember_vehicle("u", "ev") is True and len(store["saved"]) == 1  # already remembered
    assert um.remember_vehicle(None, "ev") is False and um.remember_vehicle("u", "truck") is False


def _call(name, args):
    return SimpleNamespace(id="c", function=SimpleNamespace(name=name, arguments=json.dumps(args)))


def test_chat_stops_use_the_remembered_van(monkeypatch):
    from navigation import chat_handler as ch
    seen = []
    monkeypatch.setattr(ch, "dispatch", lambda name, args: seen.append(dict(args)) or {"status": "success"})
    monkeypatch.setattr(um, "remembered_vehicle", lambda uid: "ev" if uid == "u1" else None)

    ch._run_tool({"history": [], "user_id": "u1"}, _call("find_route_stops", {"kind": "ev_charging"}), [])
    assert seen[-1]["vehicle"] == "ev"
    ch._run_tool({"history": [], "user_id": "u1"}, _call("find_route_stops", {"kind": "fuel", "vehicle": "phev"}), [])
    assert seen[-1]["vehicle"] == "phev"                    # named in the chat: kept
    ch._run_tool({"history": [], "user_id": "anon"}, _call("find_route_stops", {"kind": "fuel"}), [])
    assert "vehicle" not in seen[-1]                         # anonymous: planner default

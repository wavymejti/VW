"""
Tool calls in a follow-up reply are run, not dropped (Nov 2026).

"I'd like to sleep near Wolfgangsee": the model searched campsites, then wanted to call
set_overnight in its second reply. Only the first reply's tools were run, the reply had no
text, and the user got "Here's your planned route!" although nothing had changed.
"""

import json
from types import SimpleNamespace

import pytest

import navigation.chat_handler as ch


def _call(i, name, args):
    return SimpleNamespace(id=f"call_{i}", type="function",
                           function=SimpleNamespace(name=name, arguments=json.dumps(args)))


def _message(content=None, tool_calls=None):
    calls = tool_calls or None

    def dump(exclude_unset=True):
        d = {"role": "assistant", "content": content}
        if calls:
            d["tool_calls"] = [{"id": c.id, "type": "function",
                                "function": {"name": c.function.name,
                                             "arguments": c.function.arguments}} for c in calls]
        return d
    return SimpleNamespace(content=content, tool_calls=calls, model_dump=dump)


def _response(msg):
    return SimpleNamespace(choices=[SimpleNamespace(message=msg)])


class FakeClient:
    def __init__(self, replies):
        self.replies = list(replies)
        self.calls = []
        self.chat = SimpleNamespace(completions=SimpleNamespace(create=self.create))

    def create(self, **kwargs):
        self.calls.append(kwargs)
        return _response(self.replies.pop(0))


@pytest.fixture
def run(monkeypatch):
    dispatched = []

    def fake_dispatch(name, args):
        dispatched.append((name, args))
        if name == "search_campings":
            return {"status": "success", "results_count": 2,
                    "results": [{"name": "Camping Wolfgangblick", "lat": 47.75, "lng": 13.45}]}
        if name == "set_overnight":
            return {"status": "success", "message": "Night after day 2 is now at Camping Wolfgangblick."}
        return {"status": "error", "message": "nope"}

    monkeypatch.setattr(ch, "dispatch", fake_dispatch)
    monkeypatch.setattr(ch, "_store_message", lambda *a, **k: None)
    monkeypatch.setattr(ch, "_stored_trip", lambda *a, **k: False)

    def _run(replies):
        client = FakeClient(replies)
        session = {"client": client, "tools": [], "history": [{"role": "system", "content": "P"}],
                   "lang": "en", "active_trip_id": "trip-1", "user_id": None}
        first = client.create()
        result = ch._process_response(session, first, "trip-1")
        return result, dispatched, client
    return _run


def test_second_round_tool_calls_are_run(run):
    result, dispatched, client = run([
        _message(tool_calls=[_call(1, "search_campings", {"lat": 47.74, "lng": 13.44})]),
        _message(tool_calls=[_call(2, "set_overnight", {"day_number": 2, "name": "Camping Wolfgangblick",
                                                        "lat": 47.75, "lng": 13.45})]),
        _message(content="Day 2 now ends at Camping Wolfgangblick by the lake."),
    ])
    assert [d[0] for d in dispatched] == ["search_campings", "set_overnight"]
    assert dispatched[1][1]["trip_id"] == "trip-1"
    assert [t["function_name"] for t in result["tool_calls"]] == ["search_campings", "set_overnight"]
    assert result["text"].startswith("Day 2 now ends")


def test_rounds_are_capped_and_the_last_one_is_text_only(run):
    loop = [_message(tool_calls=[_call(i, "search_campings", {"lat": 1, "lng": 1})])
            for i in range(ch.MAX_TOOL_ROUNDS + 1)]
    result, dispatched, client = run(loop)
    assert len(dispatched) == ch.MAX_TOOL_ROUNDS
    assert client.calls[-1].get("tool_choice") == "none"
    assert result["status"] == "success" and result["text"]


def test_no_fake_route_message_after_a_search(run):
    result, _, _ = run([
        _message(tool_calls=[_call(1, "search_campings", {"lat": 47.74, "lng": 13.44})]),
        _message(content=None),
    ])
    assert "route" not in result["text"].lower()
    assert "found 2 places" in result["text"]


@pytest.mark.parametrize("tool_calls, expected", [
    ([{"function_name": "plan_route", "result": {"status": "success"}}], "route is updated"),
    ([{"function_name": "set_overnight", "result": {"status": "success", "message": "Night moved."}}], "Night moved."),
    ([{"function_name": "modify_route", "result": {"status": "error", "message": "Could not locate X."}}],
     "That didn't work: Could not locate X."),
    ([], "Done."),
])
def test_fallback_text_says_what_happened(tool_calls, expected):
    assert expected in ch._fallback_text(tool_calls, "en")

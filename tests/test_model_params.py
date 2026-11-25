"""GPT-6 Luna rejected max_tokens / temperature (400 Invalid request) in the side calls."""

from unittest.mock import MagicMock

import tools.openai_client as oc


def test_reasoning_model_gets_reasoning_parameters(monkeypatch):
    monkeypatch.setattr(oc, "REASONING_SUPPORTED", True)
    kw = oc.chat_kwargs(max_tokens=200, temperature=0.3)
    assert kw == {"reasoning_effort": "none", "max_completion_tokens": 200}


def test_classic_model_keeps_classic_parameters():
    kw = oc.chat_kwargs(max_tokens=200, temperature=0.3, model="gpt-4o-mini")
    assert kw == {"max_tokens": 200, "temperature": 0.3}


def test_sniffer_line_sends_no_classic_params_to_luna(monkeypatch):
    import tools.sniffer_line as sl
    monkeypatch.setattr(sl, "SNIFFER_LINE_MODEL", "gpt-6-luna")
    client = MagicMock()
    client.chat.completions.create.return_value.choices = [
        MagicMock(message=MagicMock(content='{"english": "Hi there!", "mood": "happy", "reaction": "none"}'))]
    line = sl.make_sniffer_line("Cześć", "Cześć! W czym pomóc?", lang="pl", client=client)
    kwargs = client.chat.completions.create.call_args.kwargs
    assert "max_tokens" not in kwargs and "temperature" not in kwargs
    assert kwargs["max_completion_tokens"] == 1500
    assert line and line["spoken"] and line["mood"] == "happy"


def test_memory_extraction_and_suggestions_use_chat_kwargs():
    for path in ("tools/user_memory.py", "tools/travel_suggestions.py"):
        src = open(path, encoding="utf-8").read()
        assert "**chat_kwargs(" in src and "temperature=0." not in src.replace("chat_kwargs(temperature=0.", "")

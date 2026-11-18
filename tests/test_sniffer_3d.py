"""
Tests for the 3D Sniffer integration (AVW module): spoken line, HeadTTS proxy, page wiring.
See architecture/sniffer_speech_sop.md.
"""

import json
import os
from types import SimpleNamespace

from tools.sniffer_line import make_sniffer_line

BASE_DIR = os.path.dirname(os.path.dirname(__file__))


class _FakeClient:
    """Minimal stand-in for openai.OpenAI returning a fixed JSON reply."""

    def __init__(self, content=None, error=None):
        self.calls = []
        self._content = content
        self._error = error
        self.chat = SimpleNamespace(completions=SimpleNamespace(create=self._create))

    def _create(self, **kwargs):
        self.calls.append(kwargs)
        if self._error:
            raise self._error
        return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content=self._content))])


def test_english_reply_is_read_word_for_word():
    client = _FakeClient(json.dumps({"mood": "happy", "reaction": "ears_up", "english": ""}))
    reply = "Great idea! Tell me:\n\n1. **Where** do you start?\n2. How many days"
    line = make_sniffer_line("Plan a trip", reply, lang="en", client=client)
    assert line == {
        "spoken": "Great idea! Tell me: Where do you start? How many days.",
        "mood": "happy",
        "reaction": "ears_up",
    }
    assert client.calls[0]["response_format"]["json_schema"]["strict"] is True


def test_polish_reply_is_read_as_full_english_translation():
    client = _FakeClient(json.dumps({"mood": "neutral", "reaction": "none", "english": "Where do we start? About 420 km."}))
    line = make_sniffer_line("Zaplanuj trasę", "Skąd startujemy? Około 420 km.", lang="pl", client=client)
    assert line["spoken"] == "Where do we start? About 420 kilometers."
    assert "do not summarize" in client.calls[0]["messages"][0]["content"]


def test_sniffer_line_never_raises():
    # English: the text is still read, with a neutral face.
    line = make_sniffer_line("hi", "Hello there.", lang="en", client=_FakeClient(error=RuntimeError("down")))
    assert line == {"spoken": "Hello there.", "mood": "neutral", "reaction": "none"}
    # Other languages need the translation, so Sniffer stays quiet.
    assert make_sniffer_line("cześć", "Cześć.", lang="pl", client=_FakeClient(error=RuntimeError("down"))) is None
    assert make_sniffer_line("hi", "", client=_FakeClient("{}")) is None


def test_sniffer_line_sanitizes_unknown_values():
    client = _FakeClient(json.dumps({"mood": "ecstatic", "reaction": "wag", "english": ""}))
    line = make_sniffer_line("hi", "Woof.", lang="en", client=client)
    assert line["mood"] == "neutral" and line["reaction"] == "none"


def test_tts_proxy_reports_unreachable_headtts(monkeypatch):
    import tools.server as server

    monkeypatch.setattr(server, "HEADTTS_URL", "http://127.0.0.1:9")  # nothing listens here
    with server.app.test_client() as client:
        res = client.post("/tts/v1/synthesize", json={"input": "Hello", "voice": "am_echo"})
    assert res.status_code == 502
    assert "HeadTTS" in res.get_json()["error"]


def test_page_mounts_3d_sniffer_and_drops_2d_avatar():
    with open(os.path.join(BASE_DIR, "frontend", "index.html"), encoding="utf-8") as f:
        html = f.read()
    assert "/static/sniffer-avw/sniffer-avw.js" in html
    assert "mountSnifferWidget" in html
    assert "sniffer_avatar.js" not in html and "sniffer_voice.js" not in html

    with open(os.path.join(BASE_DIR, "frontend", "app.js"), encoding="utf-8") as f:
        app_js = f.read()
    assert "window.snifferAVW" in app_js
    assert "snifferVoice" not in app_js and "SnifferAvatar" not in app_js


def test_exported_module_and_model_are_present():
    root = os.path.join(BASE_DIR, "frontend", "sniffer-avw")
    for rel in ("sniffer-avw.js", "VERSION", "models/sniffer_avatar_v15_lite.glb", "models/sniffer_lids_v3.json"):
        assert os.path.isfile(os.path.join(root, rel)), f"missing {rel} — run 'npm run export:vw' in AVW"


def test_google_maps_cost_switch(monkeypatch):
    import tools.maps_client as mc

    monkeypatch.setattr(mc, "GOOGLE_MAPS_MODE", "basic")
    assert all(mc.maps_allows(f) for f in ("routing", "map", "static", "places"))
    assert not mc.maps_allows("places_rich")
    monkeypatch.setattr(mc, "GOOGLE_MAPS_MODE", "lite")
    assert mc.maps_allows("routing") and not mc.maps_allows("places")
    monkeypatch.setattr(mc, "GOOGLE_MAPS_MODE", "off")
    assert not mc.maps_allows("routing")
    monkeypatch.setattr(mc, "GOOGLE_MAPS_MODE", "full")
    assert mc.maps_allows("places_rich")


def test_places_basic_requests_no_paid_fields(monkeypatch):
    import requests
    import tools.maps_client as mc

    sent = {}

    class _Resp:
        status_code = 200
        content = b"x"

        def json(self):
            return {"places": [{
                "id": "abc", "displayName": {"text": "Lake Malta"},
                "location": {"latitude": 52.4, "longitude": 16.97},
                "types": ["tourist_attraction"], "shortFormattedAddress": "Poznan",
            }]}

    def fake_post(url, json=None, headers=None, timeout=None):
        sent.update(url=url, body=json, mask=headers["X-Goog-FieldMask"])
        return _Resp()

    monkeypatch.setattr(requests, "post", fake_post)
    res = mc.places_nearby_basic(52.4, 16.9, 30000, "viewpoint")
    assert res["results"][0] == {
        "place_id": "abc", "name": "Lake Malta",
        "geometry": {"location": {"lat": 52.4, "lng": 16.97}},
        "types": ["tourist_attraction"], "vicinity": "Poznan", "formatted_address": "", "url": None,
    }
    for paid in ("photos", "rating", "userRatingCount", "PhoneNumber", "websiteUri", "OpeningHours", "reviews"):
        assert paid not in sent["mask"]
    assert sent["body"]["includedTypes"] == ["tourist_attraction"]  # legacy-only type mapped


def test_paid_photo_urls_are_stripped_from_json_unless_full(monkeypatch):
    import tools.maps_client as mc
    import tools.server as server

    photo = "https://maps.googleapis.com/maps/api/place/photo?maxwidth=600&photoreference=X&key=K"
    payload = {"a": {"photo_url": photo, "name": "Park"}, "photos": [photo, "/static/x.png"]}

    def run():
        with server.app.test_request_context("/api/attractions/t1"):
            return server._strip_paid_google_photos(server.jsonify(payload)).get_json()

    monkeypatch.setattr(mc, "GOOGLE_MAPS_MODE", "basic")
    assert run() == {"a": {"photo_url": None, "name": "Park"}, "photos": ["/static/x.png"]}
    monkeypatch.setattr(mc, "GOOGLE_MAPS_MODE", "full")
    assert run()["a"]["photo_url"] == photo

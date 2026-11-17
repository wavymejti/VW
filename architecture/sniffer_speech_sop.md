# Sniffer Speech & 3D Avatar SOP

> Standard Operating Procedure for the Volkswagen Sniffer avatar in the VW AI Trip Planner.
> **Golden Rule**: Update this SOP before changing `tools/sniffer_line.py`, the `/tts` proxy in
> `tools/server.py`, the Sniffer hooks in `frontend/app.js` or the module script in `frontend/index.html`.
> The avatar itself is developed in the separate **AVW** repo (`wavymejti/AVW`); never edit
> `frontend/sniffer-avw/` by hand.

---

## 1. Purpose

Sniffer is the trip planner's main conversational character: a 3D dog in a floating window who
reacts while the user types, thinks while the planner works and says a short line out loud next
to every chat reply. (Replaces the 2D photo/video avatar and the ElevenLabs/OpenAI voice, Nov 2026.)

## 2. Architecture

```
user message ─► POST /api/chat ─► chat_handler (planner, tools, slot_state)
                                    └─► tools/sniffer_line.py ─► {spoken, mood, reaction} (English)
response {text, ..., sniffer} ─► app.js: chat bubble (text) + window.snifferAVW.say(spoken, mood, reaction)
window.snifferAVW (AVW module) ─► POST /tts/v1/synthesize (Flask proxy) ─► HeadTTS :8882 (Kokoro am_echo)
                               ─► audio + word/viseme timings ─► TalkingHead lip-sync in the browser
```

| Part | Where | Owner |
|---|---|---|
| 3D model, eyes, behaviour, lip-sync, TTS client, floating window | AVW repo, exported to `frontend/sniffer-avw/` | AVW |
| Spoken line (`spoken`, `mood`, `reaction`) | `tools/sniffer_line.py`, called in `/api/chat` | VW |
| TTS proxy `/tts/v1/synthesize` → `HEADTTS_URL` | `tools/server.py` | VW |
| Hooks: thinking, listening, say, stop | `frontend/app.js` (`showTyping`, `sendMessage`, `speakSnifferLine`, `notifySnifferTyping`) | VW |
| Mounting the widget | module script at the end of `frontend/index.html` | VW |

## 3. Behaviour

- **Floating window**, bottom-right by default; drag by the title bar, resize from the bottom-right
  corner. Position and size are remembered (`localStorage['sniffer.widget']`). Always visible, on
  every view.
- **Start**: the model loads with the page. Browsers block sound until a user gesture, so the
  window shows **"Talk to Sniffer"**; the click unlocks audio and plays the greeting. Any later
  click (e.g. sending a message) also unlocks audio, so replies are spoken from then on.
- **Listening**: typing in the main chat input perks the ears (`snifferAVW.listening()`).
- **Thinking**: from sending a message until the reply arrives (`snifferAVW.thinking(true/false)`).
- **Speaking**: `snifferAVW.say(spoken, {mood, reaction})` after each successful reply. A new
  message interrupts him (`snifferAVW.stop()`).
- **Language**: Sniffer always speaks **English**, also when the UI is Polish or German. The chat
  text stays in the UI language.
- **No WebGL / model fails to load**: a still image (`sniffer_fallback.webp`) is shown instead.
- **TTS down**: the chat still works; Sniffer only moves (warning in the console).

## 4. Spoken line rules (`tools/sniffer_line.py`)

- One or two sentences, under 45 words, English, plain spoken text (no markdown/emoji/URLs,
  numbers written as said). Sums up the reply or asks its main question; details stay on screen.
- Vanlife persona: friendly VW California co-pilot dog, playful but not silly.
- `mood` ∈ neutral, happy, angry, sad, fear, disgust, love, sleep (mostly neutral/happy).
- `reaction` ∈ none, surprise, ears_up, ears_back, petted.
- Strict JSON schema; any failure returns `None` and the chat reply is sent without `sniffer`.
- Model: `SNIFFER_LINE_MODEL` (default: the planner's `MODEL_NAME`). Adds one short LLM call per
  reply (~1 s). Open question for the POC: try other ways (e.g. the planner writing the line
  itself) on real scenarios and keep what works best.

## 5. Updating the avatar

In the AVW repo: `cd web && npm run export:vw` (optionally `-- /path/to/VW`). It builds
`sniffer-avw.js`, copies it with the model, eyelid data and fallback image into
`frontend/sniffer-avw/` and writes `VERSION` (AVW commit). Commit the result in VW. If the model
file name changes, update the paths in `frontend/index.html`.

## 6. Running locally

Three processes: HeadTTS (`<AVW>/tts/start.sh`, port 8882), Flask (`python tools/server.py`,
port 5050), PostgreSQL (docker compose). `HEADTTS_URL` overrides the HeadTTS address.

## 7. Legacy

`tools/tts_service.py` and `POST /api/tts/speak` (ElevenLabs → OpenAI onyx) are no longer used by
the page; they remain for `main.py`'s demo and their unit tests. A future TTS provider with word
timings (ElevenLabs, Cartesia, Azure…) is meant to plug into the AVW module's TTS adapter instead.

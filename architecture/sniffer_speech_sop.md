# Sniffer Speech & Facial Animation SOP

> Standard Operating Procedure for the Volkswagen Sniffer Mascot Speech & Facial Animation Layer.
> **Golden Rule**: Update this SOP before updating code in `frontend/components/sniffer_avatar.js`, `frontend/components/sniffer_voice.js`, or `tools/tts_service.py`.

---

## 1. Purpose

Bring the **Volkswagen Sniffer** AI mascot to life inside the web application's chat panel by providing:
1. Natural, expressive facial animation (lip-sync mouth opening, eyebrow elevation, natural blinking, idle breathing, and inquisitive sniffing).
2. Spoken voice feedback (Text-to-Speech) that reads assistant responses aloud to the user in their active language (Polish, German, English).
3. Intuitive user controls: single-click voice mute/unmute, auto-speech preferences, and per-message playback buttons.

---

## 2. Mascot Character & Tone

- **Persona**: Volkswagen Sniffer — friendly, competent canine travel navigator for VW California camper vans.
- **Voice Character**: Deep, resonant, friendly masculine voice (`pitch: 0.75–0.82`, `rate: 0.92–1.00`), authoritative yet warm and relaxed campervan captain. Prioritizes masculine voice profiles (`Marek`, `Krzysztof`, `Conrad`, `Stefan`, `Guy`, `Christopher`).
- **Visual Identity**: White fluffy coat, iconic blue leather nose, navy collar with polished silver VW medallion, expressive canine eyes and articulated fluffy eyebrows.

---

## 3. Facial Animation & Emotional Expression Specifications

The facial rig is implemented in `frontend/components/sniffer_avatar.js` supporting both **Cinematic 3D Video Avatar Mode** (`sniffer_talking.mp4`) and **2.5D Spring-Damper Photographic Rig**:

### 3.1 Cinematic 3D Video Avatar Mode (Primary)
- **Asset**: High-definition 3D rendered cinematic animation (`/static/assets/video/sniffer_talking.mp4`, 480x480 H.264 loop) with instant resting poster (`sniffer_idle_poster.jpg` captured from Frame 50).
- **Kinematics & Audio-Coupled Lip-Sync**:
  - Full 3D facial muscle deformation, lifelike eye darting/blinking, genuine canine lip curl, and authentic fur dynamics.
  - **Frame Aperture Indexing**: Pre-computed 240-frame aperture lookup table (`FRAME_APERTURES`) mapping every 1/24th second of the video (0.0 = completely closed, 1.0 = wide open).
  - **Idle / Resting State**: Video pauses at Frame 50 (`currentTime: 2.083s`, aperture 0.00) where the dog displays a warm, friendly, closed-mouth resting smile looking directly forward.
  - **Audio-Reactive Energy Pacing (`pulseSpeech`)**:
    - **Active Speech (`open >= 0.10`)**: Video advances with dynamic speed modulation (`playbackRate = 0.85 + open * 0.70`), scaling between 0.85x (quiet consonants) and 1.55x (loud vowels) proportional to real-time voice amplitude.
    - **Speech Pauses / Silence (`open < 0.10`)**: When the speaker pauses for commas, periods, breathing, or word boundaries:
      - If the current frame aperture is `<= 0.22` (mouth closed), the video freezes immediately (`playbackRate = 0`).
      - If the mouth is still open (`aperture > 0.22`), the video advances briskly (`playbackRate = 1.35`) for 2-3 frames (~60ms) until reaching the nearest closed-mouth frame, then freezes. This guarantees lips *never* flap during silent pauses and *never* freeze with mouth wide open.
    - **Speech Completion (`setSpeaking(false)`)**: Video pauses cleanly and resets to Frame 50 (`currentTime = 2.083s`).
  - **Emotional states**: Seeks to expressive timestamps (`curious`: 1.8s head tilt, `happy`: 8.8s beaming smile, `calm`: 2.083s resting smile).
  - **Click / Hover interaction**: Triggers a responsive micro-playback burst starting and returning to Frame 50.
- **Fallback Mode**: 2.5D Spring-Damper Photographic Rig with independent layer kinematics.

### 3.2 Articulated Facial Elements & Physics Rig (Photographic Fallback)
1. **Mouth / Jaw & Dynamic Phonemes (`mouthOpen`: 0.0 – 1.0, `mouthWidth`: 0.85 – 1.15)**:
   - Closed (0.0): warm resting smile line under the blue nose.
   - Speaking (0.2 – 1.0): jaw lowers with spring elasticity (`translateY(open * 36px)`), mouth cavity scales in height (`scaleY(open * 1.5)`), revealing pink tongue and canine teeth.
   - Phoneme Variance: low audio frequencies expand vertical aperture (`scaleY: 1.4, scaleX: 0.95`), while high frequencies expand lateral smile width (`scaleX: 1.10, scaleY: 0.85`).
2. **Asymmetric Eyebrows (`browLeftLift`, `browRightLift`, `browTilt`: -10deg – +15deg)**:
   - Driven independently with spring physics (`stiffness: 140, damping: 14`).
   - Curious / Question (`?`): left eyebrow arches high (0.85), right eyebrow stays inquisitive (0.25) with outward tilt.
   - Happy / Excited: both eyebrows lift symmetrically in curved arches (0.75 – 0.90).
3. **Canine Head Tilt & Anatomical Neck Pivot (`headAngle`: -7deg – +5deg, `headY`: -8px – +8px)**:
   - Rotates around neck pivot (`cx: 512, cy: 820`).
   - Curious: classic canine head tilt to the left (`-5.5deg`) with subtle lateral shift.
   - Happy: cheerful slight tilt (`+3.0deg`) with gentle rhythmic bobbing.
   - Speaking: natural speech cadenced nodding with organic spring inertia.
4. **Eyes & Warm Duchenne Squints (`eyeBlink`: 0.0 – 1.0, `eyeSquint`: 0.0 – 1.0)**:
   - Natural blinking every 3.5 to 6.5 seconds (including occasional double blinks).
   - Smiling Eyes (Duchenne Squint): lower eyelid arcs rise upward during `HAPPY` and `EXCITED` states, giving warm, beaming puppy eyes.
5. **Floppy Ears (`earLeftAngle`, `earRightAngle`)**:
   - Secondary spring motion trailing head movements by 50ms, adding natural soft ear inertia.
   - Curious / Alert: ears perk upward (`-3deg` / `+3deg`).

### 3.2 Emotional States (FSM & Sentiment)
- `CALM` / `NEUTRAL` (Default idle): Gentle breathing float (`±1.5px`), relaxed smile, soft natural blinking.
- `HAPPY` / `ENTHUSIASTIC` (Recommendations, exclamation marks `!`, greetings): Cheerful head tilt (`+3deg`), warm smiling eye squints, arched eyebrows, buoyant speech cadence.
- `CURIOUS` / `THOUGHTFUL` (Questions `?`, route calculation, planning): Iconic canine head tilt (`-5.5deg`), asymmetric brows (left 0.85, right 0.25), perked ears, slight nose sniff.
- `TALKING` / `EXPLAINING` (Active speech): Audio-reactive mouth shapes, spring-damped head nodding, eyebrow emphasis on stressed syllables.

---

## 4. Text-to-Speech (TTS) & Text Sanitization

### 4.1 Speech Engine Architecture
- **Primary Engine**: ElevenLabs Neural Speech Synthesis (`POST /api/tts/speak` via ElevenLabs API, `model_id="eleven_multilingual_v2"`, voice: `Brian` - `nPczCjzI2devNBz1zQrb`):
  - Ultra-realistic, state-of-the-art human voice actor quality with deep, resonant, and comforting masculine tone.
  - Native emotional cadence, natural human breathing, and impeccable pronunciation across Polish (`pl-PL`), German (`de-DE`), and English (`en-US`).
  - Tuned voice parameters: `stability: 0.50`, `similarity_boost: 0.75`, `style: 0.0`, `use_speaker_boost: true`.
  - Server-side disk caching (`.tmp/audio_cache/`) keyed by SHA-256 of `(cleaned_text, lang, engine, voice_id)` for instant response and quota preservation.
  - Web Audio API (`AudioContext` + `AnalyserNode`) real-time frequency analysis driving Sniffer's mouth aperture and eyebrow lift synchronously to actual audio volume.
- **Secondary Fallback**: OpenAI Neural TTS (`model="tts-1"`, `voice="onyx"`):
  - Used automatically if ElevenLabs quota is exceeded, rate-limited, or fails.
- **Tertiary / Offline Fallback**: Web Speech API (`window.speechSynthesis`):
  - Used seamlessly if offline or if backend endpoints are unreachable.
- **Language Support**:
  - Polish: `pl-PL`
  - German: `de-DE`
  - English: `en-US` / `en-GB`

### 4.2 Text Sanitization Rules (`cleanTextForSpeech`)
Before sending text to the speech synthesizer, raw assistant responses must be sanitized:
1. **Markdown Stripping**:
   - Strip bold/italic formatting (`**bold**` -> `bold`, `*italic*` -> `italic`).
   - Strip Markdown headings (`# `, `## `), blockquotes (`> `), and list bullets (`* `, `- `, `• `).
   - Strip Markdown links (`[text](url)` -> `text`).
   - Strip code fences and inline backticks.
2. **Technical & Metadata Removal**:
   - Completely strip `<slot_state>...</slot_state>` and any XML/HTML tags.
   - Remove emojis (e.g. 🐶, 📍, 🏕️, ✨) so the synthesizer does not pronounce emoji descriptions.
3. **Campervan Spoken Unit Expansions**:
   - `km` -> `kilometrów` (PL) / `Kilometer` (DE) / `kilometers` (EN).
   - `h` / `godz.` -> `godzin` (PL) / `Stunden` (DE) / `hours` (EN).
   - `EUR` / `€` -> `euro`.
   - `min` -> `minut` (PL) / `Minuten` (DE) / `minutes` (EN).

---

## 5. UI Integration & User Experience

1. **Header Talking Sniffer Widget (`#sniffer-speech-widget`)**:
   - Located in the chat panel header.
   - Shows live mini animated avatar with speech soundwave badge.
   - Mute/Unmute toggle button (`#btn-toggle-sniffer-voice`) with persistent `localStorage` storage.
2. **Message-Level Playback**:
   - Each assistant message includes a listen button (`.btn-message-speak`) allowing on-demand replay or stopping.
3. **Graceful Interruptions**:
   - User typing or sending a message immediately calls `stop()`.
   - Switching views stops speech.
   - Accessibility: honors `prefers-reduced-motion`.

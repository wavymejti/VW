# 🚐 VW California AI Trip Planner — Project Map (gemini.md)

> **Source of Truth** for the B.L.A.S.T. protocol.
> Last updated: 2026-04-22

---

## 1. North Star

**Build an "AI Trip Planner with Travel Memory"** — an intelligent web application for VW California owners that combines:
- AI-driven route & camping planning via a conversational chat interface.
- A "Travel Memory" feature that auto-links user photos (EXIF/GPS) to map locations.
- Designed as a module that can integrate into the main VW California app.

---

## 2. Integrations & API Status

| Service | Purpose | Status |
|---|---|---|
| **Google Gemini API** | NLP intent extraction, conversational planning, function/tool calling | ✅ Ready |
| **Google Maps Platform** | Routes API, Places API (campground POIs), Maps JavaScript SDK, Geocoding | ✅ Ready |
| **PostgreSQL + PostGIS** | Primary data store — users, trips, campings, photos, EXIF/GPS | ✅ Ready |
| **File Storage** | User-uploaded photos (local filesystem or cloud bucket — TBD) | ⏳ To confirm |

---

## 3. Source of Truth

**PostgreSQL (PostGIS)** stores all persistent data:
- User profiles & preferences
- Generated daily driving schedules
- Camping metadata (amenities, cost, VW-specific hookups)
- Photo EXIF/GPS data and file references

---

## 4. Delivery Payload

An **intuitive web UI dashboard** featuring:
1. **Map View** — interactive routes, camping markers, photo pins (Google Maps JS SDK).
2. **Planning Mode** — conversational AI chat to build itineraries.
3. **Travel Memory Mode** — photo gallery linked to map locations.
4. **Trip Summary Generator** — visual summary export (video/animation with map, photos, music).
5. **VW Brand Styling** — all UI follows VW California brand guidelines.

---

## 5. Behavioral Rules

| Rule | Detail |
|---|---|
| **Natural Language** | Chat understands intuitive inputs (e.g., "Find camping with power and showers 3h away") |
| **Camping Filters** | Filter by cost, amenities (power, water, Wi-Fi), and VW California hookup needs |
| **Routing Logic** | Stops, attractions, overnights must be logical, consistent, and respect daily drive limits |
| **Self-Healing** | API failure → graceful fallback, ask user to adjust parameters |
| **Tone** | Professional, friendly, VW brand voice |

---

## 6. Brand Guidelines (from `brandguidelines/`)

| Token | Value |
|---|---|
| Primary Color | `#001E50` |
| Secondary Color | `#000E26` |
| Accent / Link | `#0000EE` |
| Background | `#FFFFFF` |
| Text Primary | `#000000` |
| Body Font | `vw-text`, fallback: Helvetica, Arial |
| Heading Font | `vw-head` |
| H1 Size | 51.936px |
| H2 Size | 38.048px |
| Body Size | 20px |
| Spacing Unit | 4px |
| Border Radius | 8px |
| Tone | Professional, medium energy, consumer audience |

---

## 7. JSON Data Schemas

> **Coding only begins once these payload shapes are approved.**

### 7.1 User

```json
{
  "User": {
    "id": "uuid",
    "email": "string",
    "display_name": "string",
    "vehicle_model": "string (e.g., 'VW California Ocean 6.1')",
    "preferences": {
      "max_daily_drive_hours": "number (default: 6)",
      "preferred_amenities": ["string (e.g., 'power', 'water', 'wifi', 'showers')"],
      "budget_per_night_eur": "number | null",
      "hookup_type": "string | null (e.g., 'shore_power', 'full_hookup')"
    },
    "created_at": "ISO 8601 timestamp",
    "updated_at": "ISO 8601 timestamp"
  }
}
```

### 7.2 Trip

```json
{
  "Trip": {
    "id": "uuid",
    "user_id": "uuid (FK → User)",
    "title": "string",
    "description": "string | null",
    "origin": {
      "label": "string",
      "lat": "number",
      "lng": "number"
    },
    "destination": {
      "label": "string",
      "lat": "number",
      "lng": "number"
    },
    "start_date": "YYYY-MM-DD",
    "end_date": "YYYY-MM-DD",
    "status": "string (draft | planned | active | completed)",
    "created_at": "ISO 8601 timestamp",
    "updated_at": "ISO 8601 timestamp"
  }
}
```

### 7.3 DailySchedule (one per trip day)

```json
{
  "DailySchedule": {
    "id": "uuid",
    "trip_id": "uuid (FK → Trip)",
    "day_number": "integer (1-indexed)",
    "date": "YYYY-MM-DD",
    "driving_hours": "number",
    "driving_km": "number",
    "waypoints": [
      {
        "order": "integer",
        "type": "string (start | attraction | rest_stop | camping | end)",
        "label": "string",
        "lat": "number",
        "lng": "number",
        "place_id": "string | null (Google Maps place_id)",
        "arrival_time": "HH:MM | null",
        "departure_time": "HH:MM | null",
        "notes": "string | null"
      }
    ],
    "overnight_camping_id": "uuid | null (FK → Camping)",
    "route_polyline": "string (encoded polyline from Routes API)"
  }
}
```

### 7.4 Camping

```json
{
  "Camping": {
    "id": "uuid",
    "name": "string",
    "location": "GEOGRAPHY(POINT, 4326)",
    "lat": "number",
    "lng": "number",
    "place_id": "string | null (Google Maps place_id)",
    "address": "string | null",
    "country": "string (ISO 3166-1 alpha-2)",
    "cost_per_night_eur": "number | null",
    "amenities": {
      "power": "boolean",
      "water": "boolean",
      "wifi": "boolean",
      "showers": "boolean",
      "toilets": "boolean",
      "waste_disposal": "boolean"
    },
    "vw_california_compatible": {
      "shore_power_hookup": "boolean",
      "max_vehicle_length_m": "number | null",
      "level_ground": "boolean | null"
    },
    "rating": "number | null (0–5)",
    "review_count": "integer",
    "photos": ["string (URL)"],
    "source": "string (google_maps | user_submitted | partner_db)",
    "created_at": "ISO 8601 timestamp",
    "updated_at": "ISO 8601 timestamp"
  }
}
```

### 7.5 Photo (Travel Memory)

```json
{
  "Photo": {
    "id": "uuid",
    "user_id": "uuid (FK → User)",
    "trip_id": "uuid | null (FK → Trip)",
    "file_url": "string (path or cloud URL)",
    "thumbnail_url": "string | null",
    "location": "GEOGRAPHY(POINT, 4326)",
    "lat": "number",
    "lng": "number",
    "captured_at": "ISO 8601 timestamp (from EXIF)",
    "exif_metadata": {
      "camera_make": "string | null",
      "camera_model": "string | null",
      "orientation": "integer | null",
      "original_filename": "string"
    },
    "caption": "string | null (user or AI-generated)",
    "tagged_day_schedule_id": "uuid | null (FK → DailySchedule)",
    "created_at": "ISO 8601 timestamp"
  }
}
```

### 7.6 ChatMessage (AI Conversation)

```json
{
  "ChatMessage": {
    "id": "uuid",
    "trip_id": "uuid (FK → Trip)",
    "role": "string (user | assistant | system)",
    "content": "string",
    "tool_calls": [
      {
        "function_name": "string",
        "arguments": "object (JSON)"
      }
    ],
    "created_at": "ISO 8601 timestamp"
  }
}
```

### 7.7 TripSummary (Shareable Export)

```json
{
  "TripSummary": {
    "id": "uuid",
    "trip_id": "uuid (FK → Trip)",
    "user_id": "uuid (FK → User)",
    "format": "string (video | image_slideshow | pdf)",
    "file_url": "string",
    "music_track": "string | null",
    "include_map_animation": "boolean",
    "include_photos": "boolean",
    "generated_at": "ISO 8601 timestamp"
  }
}
```

---

## 8. Gemini Tool Definitions (Intent Extraction)

The AI chat layer will use Gemini's **Function Calling** to extract structured intents from natural language. Key tools:

| Tool Name | Purpose | Trigger Example |
|---|---|---|
| `search_campings` | Find campings matching filters near a location/route | "Find a camping with power and showers 3h away" |
| `plan_route` | Generate a multi-day route with waypoints | "Plan a 5-day trip from Munich to Croatia" |
| `add_waypoint` | Add a stop/attraction to an existing day | "Add a stop at Lake Bled on day 2" |
| `adjust_schedule` | Modify driving hours, swap days, rearrange | "Move the rest day to Wednesday" |
| `get_trip_summary` | Retrieve the current trip overview | "Show me the full itinerary" |
| `upload_photos` | Process uploaded photos with EXIF extraction | (triggered by file upload action) |

---

## 9. Architecture Overview (A.N.T. 3-Layer)

```
┌──────────────────────────────────────────────────┐
│  Layer 1: Architecture (architecture/)           │
│  - Technical SOPs in Markdown                    │
│  - routing_sop.md, camping_search_sop.md, etc.   │
│  - Golden Rule: update SOP before code           │
├──────────────────────────────────────────────────┤
│  Layer 2: Navigation (Decision / Orchestration)  │
│  - Routes data between SOPs and Tools            │
│  - Handles Gemini function call dispatching        │
│  - Error routing & self-healing logic            │
├──────────────────────────────────────────────────┤
│  Layer 3: Tools (tools/)                         │
│  - Deterministic, atomic Python scripts          │
│  - tools/search_campings.py                      │
│  - tools/plan_route.py                           │
│  - tools/extract_exif.py                         │
│  - tools/generate_summary.py                     │
│  - Uses .tmp/ for intermediate files             │
└──────────────────────────────────────────────────┘
```

---

## 10. Project Directory Structure (Proposed)

```
VW/
├── gemini.md                    # This file — project map & source of truth
├── .env                         # API keys (GEMINI_API_KEY, GOOGLE_MAPS_KEY, DB_URL)
├── main.py                      # Entry point
├── brandguidelines/             # VW brand assets & styling guide
├── architecture/                # Layer 1: SOPs
│   ├── routing_sop.md
│   ├── camping_search_sop.md
│   ├── travel_memory_sop.md
│   ├── chat_orchestration_sop.md
│   ├── user_memory_rag_sop.md
│   └── summary_export_sop.md
├── tools/                       # Layer 3: Atomic scripts
│   ├── search_campings.py
│   ├── plan_route.py
│   ├── extract_exif.py
│   ├── generate_summary.py
│   ├── user_memory.py           # Personalized Long-Term Memory (RAG)
│   ├── db.py                    # Database connection & queries
│   └── maps_client.py           # Google Maps API wrapper

├── navigation/                  # Layer 2: Orchestration
│   ├── dispatcher.py            # Routes intents → tools
│   └── chat_handler.py          # Gemini conversation manager
├── frontend/                    # Web UI (HTML/CSS/JS)
│   ├── index.html
│   ├── styles.css
│   ├── app.js
│   ├── components/
│   └── assets/
├── db/                          # Database migrations & seed
│   ├── migrations/
│   └── seed.sql
├── .tmp/                        # Intermediate processing files
├── tests/                       # Unit & integration tests
└── requirements.txt
```

---

## 11. Research Notes

### Google Maps Integration
- Use **Places API (New)** with `searchNearby` for campground POI discovery. Filter by types: `campground`, `rv_park`.
- Use **Routes API** (`ComputeRoutes`) for multi-stop routing with waypoints.
- Use **Maps JavaScript SDK** for frontend map rendering and route polylines.
- Always use `place_id` for stable location references and `FieldMask` to control billing.

### PostGIS Photo Storage
- Store photos on filesystem/cloud storage, metadata in PostgreSQL.
- Use `GEOGRAPHY(POINT, 4326)` column type for GPS coordinates.
- Use `ST_DWithin()` for proximity queries (e.g., photos near a route segment).
- Always create GiST spatial indexes.
- Extract EXIF in Python using `Pillow` or `exifread`, convert DMS → Decimal Degrees.

### Gemini Function Calling
- Define structured tools via `tools` parameter in `GenerativeModel`.
- Use Pydantic models for schema validation.
- Keep tools modular (one tool per action).
- Use `system_instruction` to set VW brand tone and behavioral constraints.

---

## 12. Handoff Log

| Date | Context |
|---|---|
| 2026-04-22 | Protocol 0 initialized. Discovery questions answered. Data schemas defined. Blueprint approved. |
| 2026-04-22 | Phase 2 (Link) complete. All 3 API handshakes passing (Gemini, Google Maps, PostgreSQL+PostGIS). Migrated from OpenAI to Gemini API. |
| 2026-04-25 | Phase 3 (Architect) complete. Database schema deployed (7 tables). 5 SOPs written. 3 atomic tools built (search_campings, plan_route, extract_exif). Navigation layer wired (dispatcher + chat_handler). Camping search verified with live DB + Google Maps fallback. |
| 2026-04-27 | Phase 4 (Build) complete. Implemented Real-Time Enhancements (Weather & Traffic). Upgraded Trip Summary Export with camping details and photos. Integrated User Authentication and Travel Memory pipeline. Verified all features in browser with 100% test pass rate. |
| 2026-09-07 | Personalized User Memory RAG deployed. Added migration 005_user_memories (JSONB vectors), user_memory_rag_sop.md, tools/user_memory.py, /api/user_memories API endpoints, semantic memory injection in chat_handler.py, and example_user_memory_rag in main.py. Verified with 100% test pass rate without database reinstallation. |
| 2026-09-08 | Suggestive Travel Inspirations (Variant B + RAG) deployed. Added travel_suggestions_sop.md, tools/travel_suggestions.py, REST API endpoints (/api/travel_suggestions, /api/travel_suggestions/select), centered visual modal with skeleton loading in frontend/ (index.html, styles.css, app.js, i18n.js), example_travel_suggestions() in main.py, and unit/integration tests in tests/test_travel_suggestions.py. 100% test pass rate. |
| 2026-09-08 | Real-Time Chat Geolocation & UI Privacy Toggle deployed. Added tools/location_service.py, POST /api/location/reverse, system location prompt injection in navigation/chat_handler.py, updated SYSTEM_PROMPT in tools/openai_client.py, chat header toggle button and input status indicator in frontend/ (index.html, styles.css, app.js, i18n.js), example_user_location() in main.py, and test_location_service.py. 100% test pass rate. |
| 2026-09-08 | Travel Inspirations Enhancements: Trip Duration Filter Pills & RAG Transparency ("Dlaczego to polecamy"). Updated travel_suggestions_sop.md, tools/travel_suggestions.py, tools/server.py (/api/travel_suggestions?duration=...), frontend/ (index.html, styles.css, app.js, i18n.js) with duration pills ([Wszystkie], [Weekend 2–4 dni], [Tydzień 5–8 dni], [Wyprawa 9–14 dni]), card duration badges, and RAG reason callouts. 100% test pass rate. |
| 2026-09-08 | Travel Inspirations Realism: Injected campervan driving range limits and user GPS origin. Weekend trips capped at 200–350 km (2–3.5h) radius with strict prohibition of 1000+ km long-distance routes. Updated travel_suggestions_sop.md, tools/travel_suggestions.py, tools/server.py, and frontend/app.js. 100% test pass rate. |
| 2026-09-08 | Travel Inspirations Prompt Enrichment: Single-turn intent fulfillment. Clicking cards generates enriched prompts with explicit trip duration (X dni), user starting origin (GPS), destination, and VW California highlights. Updated travel_suggestions_sop.md, tools/travel_suggestions.py, tools/server.py, frontend/app.js, and tests/test_travel_suggestions.py. 100% test pass rate. |
| 2026-09-08 | Travel Inspirations Multilingual Generation (DE/EN/PL): Strict language adherence in backend prompts, cache invalidation on language switch in frontend, dynamic badge localization, tag cleanup, and automatic Polish leak protection fallback. Updated architecture/travel_suggestions_sop.md, tools/travel_suggestions.py, frontend/app.js, and tests/test_travel_suggestions.py. 100% test pass rate. |
| 2026-09-08 | Welcome Overlay & Language Switch Reload: Added automatic page reload on language change click, added i18n keys for welcome overlay badge, title, personalized greeting, and subtitle in PL, DE ("Willkommen, {name}!", "Wohin soll die Reise heute gehen?"), and EN. Updated frontend/index.html, frontend/app.js, frontend/i18n.js, and tests/test_i18n.py. 100% test pass rate. |
| 2026-09-08 | Chat Welcome Redesign (Option 4 - Modern AI Hero Card): Replaced 4 legacy quick-action buttons with a minimalist, brand-aligned Hero Inspiration Showcase Card (`#hero-inspiration-card`). Features dynamic personalized greeting ("Dokąd dzisiaj zmierzamy, Mateusz?"), AI badge, and 1-click modal trigger. Updated frontend/index.html, frontend/styles.css, frontend/app.js, frontend/i18n.js, and tests/test_i18n.py. 100% test pass rate. |
| 2026-09-08 | Interactive Tutorial Focus Cutout (Spotlight Clarity): Replaced global full-screen blur with dynamic SVG/polygon cutout on `#tutorial-backdrop`. Target elements inside the blue frame remain 100% sharp and unblurred with zero dark tint, while surroundings receive dark navy blur (`backdrop-filter: blur(6px)`). Removed obsolete 9999px box-shadow. Updated `index.html`, `styles.css`, `app.js`, and `tests/test_view_tutorials.py`. 100% test pass rate. |
| 2026-09-08 | Tutorial Step 2 Retargeting: Re-targeted Step 2 from obsolete `#quick-actions` container to the header button `#btn-open-suggestions` (`[ ✨ Inspiracje ]`). Cleaned up obsolete empty container and orphan tags from `#chat-welcome` in `frontend/index.html`. Updated step title and description across PL, DE, and EN in `frontend/i18n.js` and `frontend/app.js`. Updated `tests/test_view_tutorials.py` assertions. All tests passing 100%. |
| 2026-09-08 | Travel Suggestions Duration Filter Pill Fix: Fixed `ReferenceError: Cannot access 'currentLang' before initialization` in `openTravelSuggestionsModal` by hoisting `getAppLanguage()` before the cache check. Added `currentSuggestionsFilter` tracking, and enriched `CLIENT_FALLBACK_SUGGESTIONS` across PL, DE, and EN with dedicated weekend, week, and expedition cards. 100% test pass rate. |
| 2026-09-08 | Volkswagen Sniffer Mascot Integration & Rebranding: Renamed project to Volkswagen Sniffer, generated transparent mascot PNG assets (avatar, sitting, standing), integrated Sniffer in nav rail, chat assistant bubbles, chat welcome hero, typing/planning indicators, and modal badges. Updated SYSTEM_PROMPT persona, i18n (PL/DE/EN), tools/sniffer_mascot.py, and tests. 100% test pass rate. |
| 2026-09-08 | Chat Bubbles Redesign & Message Styling: Fixed missing `msgDiv.className` in `app.js`, implemented premium speech bubble styling (VW Navy gradient for user messages aligned right, pure white elevated cards with header tag and Sniffer avatar for assistant), added rich formatting for markdown bold, bullet items, and paragraph gaps. Updated styles.css and tests. 100% test pass rate. |
| 2026-09-08 | Attractions 8-Item Limit & Review-Count Ranking: Changed default attraction suggestion limit from 5 to 8 to fill exactly 2 full rows (4 columns x 2 rows) evenly without dangling cards. Switched attraction ranking from raw rating to review count (`user_ratings_total`) descending with rating as tiebreaker, eliminating obscure 1-review spots in favor of top-tier landmarks and museums. Added review counts display on cards, updated Top 8 modal, and verified live with 100% test pass rate. |
| 2026-09-08 | Cinematic California Recap (Travel Memories & Video Generation Upgrade): Upgraded trip summary engine to cinematic standards (Relive / Apple Memories style). Replaced blank navy background with real Google Static Maps terrain imagery via Web Mercator projection and offline vector fallback. Replaced yellow dot with rotated VW California campervan sprite with pop-up roof following route azimuth. Added live Digital Cockpit HUD (real-time odometer, day badge, cyan glow route). Replaced static slide pacing with differential FFmpeg timing (25 FPS smooth route motion + full-screen photo highlights). Added 14 unit/integration tests with 100% pass rate. |
| 2026-09-08 | Trip Video Recap Photo Inclusion & Map Pin Integration: Removed hardcoded `[:2]` photo cap in `_generate_video()`. Added intelligent multi-upload photo deduplication by `file_url`, geographic schedule partitioning (`_partition_photos_by_schedule`), and adaptive pacing (`_get_photo_slide_duration`). Rendered cyan photo pins directly onto animated map frames at photo coordinates. Ensured all photos with map pins are rendered in high-resolution slides with matching intro/outro counts. Verified with video re-generation for trip `a759e3a6` (all 18 unique pinned photos included) and 100% test pass rate. |
| 2026-09-08 | Travel Memory Persistence & Miniature Photo Pins on Map and Film: Enabled trip photo persistence across page reloads by returning saved photos in `_get_trip_data()` (`tools/server.py`). Implemented `_createPhotoMarker()` in `frontend/app.js` using HTML canvas to render rounded miniature photo pins with needle pointer, radial fan-out for overlapping coordinates, drag-and-drop coordinate update (`/api/pin_photo`), and rich InfoWindow preview. Implemented `renderTravelMemoryGrid()` with GPS status badges and click-to-pan. In `tools/generate_summary.py`, added `_get_cached_photo_pin()` rendering miniature photo thumbnail pins with pointer needles and `+N` cluster badges on video map frames. Verified with live video re-generation for trip `a759e3a6` and 100% pytest pass rate. |
| 2026-09-08 | Procedural Soundtrack Engine & Studio-Quality Multi-Track Generation: Replaced primitive mono beep audio with a modular procedural audio synthesizer (`tools/audio_generator.py`). Implemented Karplus-Strong physical string modeling for acoustic & folk guitars, FM synthesis for warm Fender Rhodes, upright/dub/warm electric bass, procedural drum synthesis (kick, snare, hi-hat, reggae one-drop rimshot, timpani), stereo track mixing, ping-pong delay, Schroeder reverb, and analog tape saturation. Generated all 9 category-matched 38-second stereo 320 kbps MP3 & 16-bit 44.1kHz WAV tracks across Relaks, Jazz, Folk, and Klimat. Added 7 unit tests (100% pass rate) and integrated into main.py and video summary. |
| 2026-09-08 | Audius Streaming API Integration (Darmowy Serwis Muzyczny): Zintegrowano darmowy, otwarty protokół Audius API (ponad 1 mln utworów indie) dla ścieżek dźwiękowych w filmach z podróży VW California. Utworzono `tools/audius_service.py` z dynamicznym failoverem węzłów Discovery, nastrojami (Vanlife, Lo-Fi Sunset, Acoustic Folk, Alpine Nature, Summer, Smooth Jazz), wyszukiwarką na żywo oraz pobieraniem i buforowaniem MP3 do `.tmp/audio_cache/`. Rozbudowano `tools/server.py` o trasy `/api/music/moods`, `/api/music/search`, `/api/music/stream/<id>`. W `tools/generate_summary.py` dodano miksowanie strumieni Audius w FFmpeg (volume=0.25). W UI zaimplementowano interaktywny selektor muzyczny z odsłuchem, okładkami, wyszukiwarką i pigułkami nastrojów. Zachowano dotychczasowe utwory proceduralne jako tryb offline. Dodano 10 testów jednostkowych/integracyjnych (100% pass rate). |
| 2026-09-08 | Route Modification & Waypoints Integration (Gardelegen / Via-Stops Fix): Fixed AI conversational route modifications when requesting specific intermediate towns or points (e.g. "chce koniecznie przejechac przez Gardelegen"). Fixed `dispatcher.py` (`_handle_modify_route`) to parse `waypoints` and `via_places`, preserve existing attractions and round-trip status, and added `_handle_add_waypoint`. In `tools/plan_route.py`, added Haversine-based optimal day assignment for waypoints, passed daily waypoints to Google Directions API for realistic polyline bending and driving metrics, and added intermediate waypoints to schedule items. In `frontend/app.js`, updated `sendMessage` to trigger `displayTripOnMap` on tool execution and updated day cards. Added unit & integration tests (`tests/test_modify_route_waypoints.py`) and verified with 100% pass rate. |
| 2026-09-09 | Persistent PostgreSQL/PostGIS Attractions & POI Cache (Cost Optimization): Deployed migration 006_attractions_cache.sql creating `cached_attractions` (spatial PostGIS GIST index) and `trip_attractions_cache`. Created `tools/attractions_cache.py` implementing 2-tier caching: spatial proximity lookup via `ST_DWithin` and trip-level aggregated payload caching. Updated `tools/suggest_attractions.py` and `tools/server.py` (`/api/attractions/<trip_id>`) to check DB cache before Google Places API, eliminating redundant external API queries. Added `example_attractions_cache()` in `main.py` and comprehensive test suite (`tests/test_attractions_cache.py`). 100% test pass rate with full fail-safe error handling. |
| 2026-09-09 | Tablet Layout & Language Selector Overhaul: Fixed chat input being pushed offscreen on tablets by enforcing dynamic viewport height (100dvh), setting overflow: hidden on #view-chat, min-height: 0 with internal scroll on .chat-messages, and flex-shrink: 0 on .chat-input-wrapper. Added responsive queries for max-height 820px/650px. Fixed language switcher disappearing/clipping in sidebar by replacing 3 stacked buttons with a compact trigger + flyout menu, and added a prominent language switcher dropdown in the chat header actions. Fixed sidebar flyout clipping by setting overflow: visible !important and z-index: 1000 on #view-nav with pointer-events protection. Verified 100% test pass rate. |
| 2026-09-09 | Camping & Attractions Modal Sticky Footer & Responsive Tablet Fix: Restructured modal layout into .camping-selection-header-wrap (fixed top), .camping-selection-body (inner flex-1 scroll), and .camping-modal-footer (sticky bottom with Gotowe button). Resolved flex centering viewport clipping where header was pushed above top:0 and footer below bottom on short landscape tablet screens. Set modal card height to calc(100dvh - 32px) with compact max-height 750px media query. Verified 100% test pass rate. |
| 2026-09-09 | Tablet Photo Pins Loading & Interactive Map Pinning: Fixed photo pins failing to load on tablets. (1) Switched `_createPhotoMarker` and Travel Memory gallery from loading uncompressed 15MB photos to lightweight thumbnails (~30-60KB). (2) Added high-DPI scaling (`window.devicePixelRatio`) to HTML5 canvas for crisp rendering on Retina/AMOLED tablet displays. (3) Added OPTIONS preflight, CORS (`Access-Control-Allow-Origin: *`), and on-demand thumbnail generation in `tools/server.py` `/photos/file/` endpoint. (4) Enabled interactive manual map pinning (`startPinningPhotoOnMap`, `#pin-photo-overlay` with z-index: 100) allowing photos without GPS (standard for mobile/tablet browser uploads) to be easily pinned with a single tap on the map. All 18 unit/integration tests passing 100%. |
| 2026-09-09 | Travel Inspirations Tablet Modal & Comprehensive Tablet Usability Audit: Fixed clipping of modal header and footer on Android/iOS tablets in landscape orientation (~1280x800, viewport height ~600px). Restructured `#travel-suggestions-modal` into a 3-layer architecture (.travel-suggestions-header-wrap with flex-shrink:0, .travel-suggestions-body with flex:1 min-height:0 overflow-y:auto, and .travel-suggestions-footer with flex-shrink:0). Replaced flex centering clipping defect (align-items: center causing top/header and close button to disappear above top:0) with 100dvh, align-items: flex-start, and margin: auto 0. Added @media (max-height: 820px) compact card layout. Audited and reinforced other modals (.top-attractions-overlay, .modal-card, .modal-header fixed close button 44x44px touch targets). Added 2 new tests in tests/test_travel_suggestions.py. 100% test pass rate across all suites. |
| 2026-09-09 | Map Controls Cleanup (Removed Redundant Campsites Button): Removed the `#btn-toggle-campings` floating control from the right-hand map toolbar (`#map-overlay`) in `frontend/index.html`. Campsite selection is now cleanly handled per day on itinerary cards via `#camping-selection-modal`, and overnight campsites are already rendered on the route map. Guarded event listeners in `frontend/app.js` and updated e2e specifications (`e2e/map_route.spec.ts`, `e2e/ui.spec.ts`). All tests pass 100%. |
| 2026-09-09 | Interactive Campervan Photo Stops & Pop-Up Zoom Animations: Upgraded video recap engine (`tools/generate_summary.py`) to feature interactive stops along the route. When the campervan reaches or approaches a photo pin location, it halts. A glowing cyan pulse expands from the pin (4 frames), the photo memory card smoothly blooms outward with dark glass vignette (pop-up zoom, 8 frames), holds full-res slide presentation for ~2.0-2.5s, then gracefully shrinks back into the pin (6 frames), allowing the campervan to resume driving towards the next stop. Added `_project_photo_to_route`, `_render_pin_pulse_frame`, `_render_photo_popup_frame`, unit tests (`tests/test_photo_stop_animation.py`), and `example_photo_stop_animation()` in `main.py`. Re-generated full video summary (`summary_b00afbac.mp4`) with 100% test pass rate (24/24). |

---

## 13. Maintenance Log

_To be populated during Phase 5 (Trigger/Deployment)._

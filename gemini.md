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
│   └── summary_export_sop.md
├── tools/                       # Layer 3: Atomic scripts
│   ├── search_campings.py
│   ├── plan_route.py
│   ├── extract_exif.py
│   ├── generate_summary.py
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

---

## 13. Maintenance Log

_To be populated during Phase 5 (Trigger/Deployment)._

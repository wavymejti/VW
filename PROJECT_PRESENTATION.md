# 🚐 VW California AI Trip Planner — Project Presentation & Architecture Guide

Welcome to the official technical documentation and presentation guide for the **VW California AI Trip Planner with Travel Memory**. This system has been designed specifically for VW California owners to easily plan multi-day road trips across Europe, select optimal campgrounds compatible with camper van dimensions, track travel memories by auto-linking photo locations to route paths, and export shareable visual summaries.

---

## 1. Executive Summary & Product Vision

### 1.1 The "North Star"
VW California owners form a passionate global community that values freedom, spontaneous exploration, and outdoor living. The **AI Trip Planner** is a specialized module designed to integrate into the core VW California companion application. Its goals are:
*   **Conversational Planning**: Demystify road trip planning through a chat interface that understands natural language.
*   **Contextual Camping Integration**: Suggest places to stay that cater directly to VW California dimensions, shore power needs, and camper preferences.
*   **Travel Memory Integration**: Auto-correlate uploaded pictures to route segments and map locations.
*   **Visual Storytelling**: Provide a shareable highlight reel (video, slideshow, or PDF report) of completed journeys.

```mermaid
graph TD
    A[VW California Owner] -->|Conversational Chat| B[Gemini AI Planning Layer]
    B -->|Automatic Mapping| C[Google Maps JS Engine]
    C -->|Photo Uploads| D[Travel Memory GPS Sync]
    D -->|PostGIS Matcher| E[Shareable Highlight Summary]
    E -->|Slideshow/MP4/PDF| F[Social Share & Preservation]
```

### 1.2 UI Dashboard Design Mockup

Here is the premium user interface concept mockup for the in-car VW California Dashboard integration:

![VW California AI Trip Planner Dashboard UI Mockup](dashboard_mockup.png)

### 1.3 Brand Voice & Product Tone
The product styling and textual interactions adhere strictly to the VW brand:
*   **Professional**: Reliable, clean, precise.
*   **Medium Energy**: Friendly, encouraging, but concise. Avoids fluff.
*   **Customer-centric**: Emphasizes safety, compatibility, and the joy of traveling.

---

## 2. Core Feature Breakdown

### 2.1 AI Planning Mode & Slot-Filling Orchestrator
Instead of forcing users to fill out long, rigid HTML forms, the system uses a **conversational slot-filling architecture**. The AI agent guides the user in collecting five core parameters:

| Slot | Parameter | Description |
| :--- | :--- | :--- |
| **Slot 1** | `vibe` | Trip environment (e.g. mountains, coast, city) and travel party (solo, couple, kids). |
| **Slot 2** | `experience` | User experience level (first-time camper, intermediate, veteran). |
| **Slot 3** | `pace` | Daily movement rate (new place every day vs. basecamp focus). |
| **Slot 4** | `infrastructure` | Lodging style (wild camping, full-service campsites, mixed). |
| **Slot 5** | `duration` | Length of the journey in days. |

> [!NOTE]
> **Holistic Parameter Gathering**: The AI extracts these slots implicitly from the user's description. If some slots are missing, it asks one unified, natural question rather than five individual questions.

### 2.2 Interactive Route Map
The frontend renders an interactive map powered by the **Google Maps JavaScript SDK**.
*   **Routes API Integration**: Computes real-time directions between waypoints.
*   **Dynamic Itinerary Cards**: Visualizes daily schedules, driving distance, driving hours, and weather warnings.
*   **Geospatial Pins**: Displays overnight campgrounds with custom markers and compatibility badges.

### 2.3 Travel Memory Pipeline
Users can upload photos taken during their journey.
1.  **EXIF Processing**: The backend extracts GPS coordinates (converted from DMS to Decimal Degrees) and timestamp data.
2.  **PostGIS Spatial Lookup**: Auto-correlates photo coordinates to the closest route segment within a **5km spatial boundary** using PostGIS `ST_DWithin()`.
3.  **Map Tagging**: Auto-places pins on the interactive map representing photo locations.

### 2.4 Shareable Trip Summary Generator
Generates a downloadable file of the trip history in multiple formats:
*   **Slideshow (PNGs)**: Generates a beautiful title slide, daily highlight slides, and a final summary slide complete with overlayed camping photos and a VW watermark.
*   **Video (.mp4)**: Stitches generated slideshow images together with background music using **FFmpeg**.
*   **PDF Report**: Creates a clean, tall visual infographic report detailing total distances, times, and routes.

---

## 3. Architecture Overview (A.N.T. 3-Layer)

The project utilizes the **A.N.T. (Architecture, Navigation, Tools)** design pattern:

```mermaid
graph TD
    subgraph Layer 1: Architecture
        A1[routing_sop.md]
        A2[camping_search_sop.md]
        A3[travel_memory_sop.md]
        A4[chat_orchestration_sop.md]
        A5[summary_export_sop.md]
    end

    subgraph Layer 2: Navigation
        B1[dispatcher.py]
        B2[chat_handler.py]
        B3[Flask API Server]
    end

    subgraph Layer 3: Tools
        C1[plan_route.py]
        C2[search_campings.py]
        C3[extract_exif.py]
        C4[generate_summary.py]
        C5[get_weather.py]
        C6[db.py]
    end

    Layer 1 -->|Reference Guide| Layer 2
    Layer 2 -->|Dispatches Intents| Layer 3
    Layer 3 -->|Saves and Fetches| D[(PostgreSQL + PostGIS)]
```

*   **Layer 1: Architecture (`architecture/` SOPs)**: Defines developer requirements, schemas, and rule boundaries in Markdown files.
*   **Layer 2: Navigation (`navigation/` and `server.py`)**: Directs data flows, manages conversational chat histories, handles user registration and authentication, and dispatches extracted JSON parameters to Layer 3 tools.
*   **Layer 3: Tools (`tools/` modules)**: Atomic, deterministic scripts responsible for calling external APIs, executing database migrations, and performing mathematical calculations.

---

## 4. PostgreSQL + PostGIS Database Schema

The database relies on **PostgreSQL** with the **PostGIS extension** enabled to allow GIST-indexed spatial operations (e.g. searching campgrounds or matching images along a route).

### 4.1 Schema ER Diagram
```mermaid
erDiagram
    USERS ||--o{ TRIPS : creates
    USERS ||--o{ PHOTOS : uploads
    TRIPS ||--o{ DAILY_SCHEDULES : has
    TRIPS ||--o{ CHAT_MESSAGES : records
    TRIPS ||--o{ TRIP_SUMMARIES : exports
    DAILY_SCHEDULES }|--o| CAMPINGS : selects_overnight
    PHOTOS }|--o| TRIPS : auto_linked_to
    PHOTOS }|--o| DAILY_SCHEDULES : tagged_to_day
    TRIP_SUMMARIES }|--|| USERS : generates
```

### 4.2 Database Tables

#### Table: `users`
Stores explorer credentials, configurations, and vehicle details.
```sql
CREATE TABLE users (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    email VARCHAR(255) UNIQUE NOT NULL,
    display_name VARCHAR(100) NOT NULL,
    password_hash VARCHAR(255),
    vehicle_model VARCHAR(100) DEFAULT 'VW California',
    max_daily_drive_hours NUMERIC(3, 1) DEFAULT 6.0,
    preferred_amenities TEXT[] DEFAULT '{}',
    budget_per_night_eur NUMERIC(8, 2),
    hookup_type VARCHAR(50),
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);
```

#### Table: `trips`
Tracks the global itinerary metadata.
```sql
CREATE TABLE trips (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    title VARCHAR(255) NOT NULL,
    description TEXT,
    origin_label VARCHAR(255),
    origin_lat NUMERIC(10, 7),
    origin_lng NUMERIC(10, 7),
    destination_label VARCHAR(255),
    destination_lat NUMERIC(10, 7),
    destination_lng NUMERIC(10, 7),
    start_date DATE,
    end_date DATE,
    status VARCHAR(20) DEFAULT 'draft' CHECK (status IN ('draft', 'planned', 'active', 'completed')),
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);
```

#### Table: `campings`
Stores campground properties and PostGIS spatial locations.
```sql
CREATE TABLE campings (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name VARCHAR(255) NOT NULL,
    location GEOGRAPHY(POINT, 4326),
    lat NUMERIC(10, 7) NOT NULL,
    lng NUMERIC(10, 7) NOT NULL,
    place_id VARCHAR(255),
    address TEXT,
    country CHAR(2),
    cost_per_night_eur NUMERIC(8, 2),
    has_power BOOLEAN DEFAULT FALSE,
    has_water BOOLEAN DEFAULT FALSE,
    has_wifi BOOLEAN DEFAULT FALSE,
    has_showers BOOLEAN DEFAULT FALSE,
    has_toilets BOOLEAN DEFAULT FALSE,
    has_waste_disposal BOOLEAN DEFAULT FALSE,
    shore_power_hookup BOOLEAN DEFAULT FALSE,
    max_vehicle_length_m NUMERIC(4, 1),
    level_ground BOOLEAN,
    rating NUMERIC(2, 1) CHECK (rating >= 0 AND rating <= 5),
    review_count INTEGER DEFAULT 0,
    photos TEXT[] DEFAULT '{}',
    source VARCHAR(50) DEFAULT 'google_maps',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX idx_campings_location ON campings USING GIST(location);
```

#### Table: `daily_schedules`
Represents segments of a trip per calendar day.
```sql
CREATE TABLE daily_schedules (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    trip_id UUID NOT NULL REFERENCES trips(id) ON DELETE CASCADE,
    day_number INTEGER NOT NULL CHECK (day_number > 0),
    schedule_date DATE,
    driving_hours NUMERIC(4, 1),
    driving_km NUMERIC(7, 1),
    waypoints JSONB DEFAULT '[]',
    overnight_camping_id UUID REFERENCES campings(id),
    route_polyline TEXT,
    UNIQUE(trip_id, day_number)
);
```

#### Table: `photos`
Manages user-uploaded images and their spatial coordinates.
```sql
CREATE TABLE photos (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    trip_id UUID REFERENCES trips(id) ON DELETE SET NULL,
    file_url TEXT NOT NULL,
    thumbnail_url TEXT,
    location GEOGRAPHY(POINT, 4326),
    lat NUMERIC(10, 7),
    lng NUMERIC(10, 7),
    captured_at TIMESTAMPTZ,
    camera_make VARCHAR(100),
    camera_model VARCHAR(100),
    orientation INTEGER,
    original_filename VARCHAR(255),
    caption TEXT,
    tagged_day_schedule_id UUID REFERENCES daily_schedules(id) ON DELETE SET NULL,
    created_at TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX idx_photos_location ON photos USING GIST(location);
```

#### Table: `chat_messages`
Logs full conversation flows to resume planner sessions.
```sql
CREATE TABLE chat_messages (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    trip_id UUID NOT NULL REFERENCES trips(id) ON DELETE CASCADE,
    role VARCHAR(20) NOT NULL CHECK (role IN ('user', 'assistant', 'system')),
    content TEXT NOT NULL,
    tool_calls JSONB DEFAULT '[]',
    created_at TIMESTAMPTZ DEFAULT NOW()
);
```

#### Table: `trip_summaries`
Persists exported visual highlight parameters.
```sql
CREATE TABLE trip_summaries (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    trip_id UUID NOT NULL REFERENCES trips(id) ON DELETE CASCADE,
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    format VARCHAR(30) NOT NULL CHECK (format IN ('video', 'image_slideshow', 'pdf')),
    file_url TEXT NOT NULL,
    music_track VARCHAR(255),
    include_map_animation BOOLEAN DEFAULT TRUE,
    include_photos BOOLEAN DEFAULT TRUE,
    generated_at TIMESTAMPTZ DEFAULT NOW()
);
```

#### Table: `interaction_logs`
Logs conversational exchanges for security auditing and ML performance diagnostics.
```sql
CREATE TABLE interaction_logs (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_message TEXT NOT NULL,
    model_response TEXT NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW()
);
```

---

## 5. API Endpoint Specifications

The Flask backend exposes REST API endpoints for user authentication, planner utilities, and client services.

| Endpoint | Method | Authentication | Description |
| :--- | :--- | :--- | :--- |
| `/api/register` | `POST` | Public | Registers a new user, hashes password, starts session. |
| `/api/login` | `POST` | Public | Validates user password, initializes session. |
| `/api/logout` | `POST` | Session | Terminated session variables. |
| `/api/me` | `GET` | Session | Fetches profile metrics and preferences of the logged-in user. |
| `/api/trips` | `GET` | Session | Lists all historical trips generated by the user. |
| `/api/trip/<trip_id>`| `GET` | Session | Details structural waypoints and logs of a single trip. |
| `/api/chat` | `POST` | Session | Submits message to the OpenAI-guided conversational thread. |
| `/api/search_campings` | `POST` | Public | Core campground search near a specified coordinate. |
| `/api/plan_route` | `POST` | Session | Orchestrates Multi-day planning calculations. |
| `/api/upload_photo` | `POST` | Session | Receives binary image files, extracts EXIF, and auto-links. |
| `/api/generate_summary` | `POST` | Session | Stitches assets together into slideshows, videos, or PDFs. |

---

## 6. Frontend Brand Guidelines & Design Tokens

All UI styling parameters are configured to follow standard Volkswagen camper design layouts:

| Design Token | CSS Config | Description |
| :--- | :--- | :--- |
| **Primary Color** | `#001E50` | Deep VW Corporate Blue, used for headers, buttons, and logos. |
| **Secondary Color** | `#000E26` | Dark background contrast for navigation rails and modals. |
| **Accent Color** | `#0000EE` | High visibility links and active indicators. |
| **Font Family** | `vw-text`, Helvetica, Arial | Clean, rounded modern typography. |
| **Border Radius** | `8px` | Subtle corner softening on all containers, inputs, and cards. |
| **Spacing Unit** | `4px` | Consistent grid layouts. |

> [!TIP]
> **Dynamic Progress Bar**: The top of the planning chat contains a horizontal step tracker mapping out Slot collection progress. The dots light up dynamically as the conversational parameters are extracted.

---

## 7. Quality Assurance & System Verification

The system includes a complete automated test suite to ensure stability across database operations, API integration handshakes, and EXIF processing:

1.  **Auth Tests (`tests/test_auth.py`)**: Tests secure login, invalid input handling, and session validation.
2.  **EXIF Extractors (`tests/test_extract_exif.py`)**: Processes test images and compares DMS-to-decimal coordinate math.
3.  **Camping Proximity (`tests/test_search_campings.py`)**: Exercises PostGIS `ST_DWithin` database operations.
4.  **Route Planners (`tests/test_plan_route.py`)**: Simulates Routes API requests and ensures daily driving ranges are obeyed.
5.  **Exporter Tests (`tests/test_generate_summary.py`)**: Verifies PNG slide drawings and FFmpeg concatenations.

```bash
# To run the automated test suite locally:
pytest tests/
```

---

## 8. Setup & Onboarding Guide

To run the complete VW California AI Trip Planner workspace on a local development machine, execute the following steps:

### Step 8.1: Initialize Environment
Ensure Python 3.9+ is installed. Create and activate a clean virtual environment:
```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### Step 8.2: Configure Environment Variables
Create a local `.env` file from the example blueprint:
```bash
cp .env.example .env
```
Open `.env` and enter your valid API keys:
*   `OPENAI_API_KEY`: API key for model completion & intent classification.
*   `GOOGLE_MAPS_API_KEY`: Key with Places API, Routes API, Maps JavaScript SDK, and Geocoding enabled.
*   `DATABASE_URL`: PostgreSQL connection string (e.g. `postgresql://postgres:postgres@localhost:5432/vw_trip_planner`).

### Step 8.3: Apply Database Migrations & Seeds
Run migrations to build all tables with PostGIS extensions and seed data:
```bash
python3 db/run_migrations.py
python3 apply_migration.py
```

### Step 8.4: Verify External API Connections
Run the unified verification utility to check OpenAI, Google Maps, and PostGIS connection statuses:
```bash
python3 tools/verify_connections.py
```

### Step 8.5: Run the Web Server
Launch the Flask development server:
```bash
python3 -m tools.server
```
Open a browser and navigate to **`http://localhost:5050`** to access the dashboard.

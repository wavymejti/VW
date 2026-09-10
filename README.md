# 🚐 Volkswagen Sniffer — AI Trip Planner with Travel Memory

[![Python](https://img.shields.io/badge/Python-3.11+-001E50.svg?logo=python&logoColor=white)](https://www.python.org/)
[![Flask](https://img.shields.io/badge/Flask-3.0+-001E50.svg?logo=flask&logoColor=white)](https://flask.palletsprojects.com/)
[![PostgreSQL](https://img.shields.io/badge/PostgreSQL-PostGIS-001E50.svg?logo=postgresql&logoColor=white)](https://postgis.net/)
[![Google Maps](https://img.shields.io/badge/Google_Maps-Routes_&_Places-001E50.svg?logo=googlemaps&logoColor=white)](https://developers.google.com/maps)
[![Audius](https://img.shields.io/badge/Audius-Music_API-001E50.svg?logo=audius&logoColor=white)](https://audius.co/)
[![License](https://img.shields.io/badge/License-MIT-001E50.svg)](LICENSE)

An intelligent, conversational web application designed specifically for **Volkswagen California** campervan owners and road-trip enthusiasts. Combining **conversational AI planning**, **camper-compatible campground recommendations**, **spatial photo linking (Travel Memory)**, **curated travel inspirations**, and **cinematic video recap generation with Audius streaming music**.

Meet **Sniffer** — your AI-powered camper companion dog, always ready to sniff out the best spots, scenic passes, and tranquil campgrounds! 🐾

---

## 📸 Interface Preview

![VW California AI Trip Planner Dashboard](dashboard-mockup.png)

---

## ✨ Key Features

### 🐶 Volkswagen Sniffer Mascot & AI Companion
- **Friendly Vanlife Persona**: Sniffer assists with conversational itinerary building, shares tips for campervan packing, shore power, and camping etiquette.
- **Dynamic Mascot States**: Visual mascot integration throughout the navigation rail, chat bubbles, thinking/planning indicators, and modal headers.

### 🧠 Personalized Long-Term Memory (RAG)
- **Camper Preference Learning**: Automatic extraction and vectorization of user preferences (travel pace, wild vs. luxury camping, hookup needs, preferred road types).
- **Semantic Cosine Search**: Stored in PostgreSQL with JSONB vector representations for context injection into future trip planning turns.

### 💡 Suggestive Travel Inspirations
- **Trip Duration Filters**: Quick filter pills ([Weekend 2–4 days], [Week 5–8 days], [Expedition 9–14 days]) tailored to realistic campervan driving limitations.
- **Origin-Aware Suggestions**: Automatically calculates routes within comfortable daily driving range based on the user's current GPS location.
- **RAG Transparency ("Why we recommend this")**: Direct explanation of why a destination matches the user's stored preferences.

### 🗣️ Conversational AI Planning Mode
- **Holistic Slot-Filling**: Natural language interaction that gathers trip parameters (vibe, experience level, driving pace, infrastructure preferences, duration) without rigid forms.
- **Context-Aware Intent Extraction**: Converts user requests (*"Plan a 4-day scenic trip to the Bavarian Alps with shore power campgrounds"*) into structured itinerary data.
- **Dynamic Route Modification**: Modify active trips through chat — add specific waypoints (*"I want to drive via Gardelegen"*), swap days, or change overnight stays.

### 🗺️ Interactive Maps & Campground Discovery
- **Google Maps JS SDK + Routes API**: Exact polyline directions with daily driving distance and time estimates.
- **VW California Compatibility Filters**: Filter campgrounds by shore power (`230V`), fresh water supply, maximum vehicle clearance, and level terrain.
- **Curated Top 8 Attractions**: Places API discovery ranked by review volume and ratings, cached locally in PostgreSQL.
- **Live Weather Alerts**: Displays forecast warnings along route waypoints.

### 📸 Travel Memory (Spatial EXIF Photo Sync)
- **Automatic EXIF GPS Extraction**: Extracts latitude, longitude, and capture timestamps from uploaded photos.
- **PostGIS Spatial Matching**: Auto-links photos to route segments within a 5 km boundary using PostGIS `ST_DWithin()`.
- **Interactive Miniature Photo Pins**: Renders canvas photo pins directly on the map with fan-out clustering for overlapping coordinates and drag-and-drop location adjustments.

### 🎬 Cinematic California Recap & Audio Studio
- **Relive / Apple Memories Style Recap**: Video export (`.mp4`) with smooth camera transitions over real Google Static Maps terrain imagery.
- **Digital Cockpit HUD**: Real-time odometer counter, day badges, and an animated VW campervan sprite with pop-up roof following route bearing.
- **Dual Soundtrack Engine**:
  - 🎵 **Audius Streaming Integration**: Access over 1,000,000 indie tracks categorized by mood (*Vanlife Chill, Lo-Fi Sunset, Acoustic Folk, Alpine Nature, Smooth Jazz*).
  - 🎛️ **Procedural Audio Synthesizer**: 100% offline, studio-grade synthesizer using Karplus-Strong physical modeling, FM synthesis, and analog tape saturation.

### 🌍 Multilingual Support (i18n)
- Seamless real-time language switching between **English (EN)**, **Polish (PL)**, and **German (DE)** with localized prompts and UI.

---

## 🏗️ System Architecture (A.N.T. 3-Layer Pattern)

The project adheres to the **A.N.T. (Architecture, Navigation, Tools)** software engineering pattern:

```
┌──────────────────────────────────────────────────────────┐
│  Layer 1: Architecture (architecture/ & SOPs)            │
│  - Standard Operating Procedures (SOPs in Markdown)      │
│  - routing_sop.md, camping_search_sop.md                 │
│  - user_memory_rag_sop.md, travel_suggestions_sop.md     │
│  - summary_export_sop.md, travel_memory_sop.md           │
├──────────────────────────────────────────────────────────┤
│  Layer 2: Navigation (navigation/ & Flask Server)        │
│  - Dispatcher & Intent Orchestration (dispatcher.py)    │
│  - Chat Conversation Handler (chat_handler.py)          │
│  - REST API Routes & Web UI Server (tools/server.py)    │
├──────────────────────────────────────────────────────────┤
│  Layer 3: Tools (tools/ & Atomic Python Scripts)         │
│  - plan_route.py, search_campings.py, extract_exif.py    │
│  - user_memory.py, travel_suggestions.py                 │
│  - audius_service.py, audio_generator.py                 │
│  - generate_summary.py, location_service.py              │
│  - PostgreSQL + PostGIS Data Store                     │
└──────────────────────────────────────────────────────────┘
```

---

## 🛠️ Tech Stack & Technologies

| Layer | Technology |
| :--- | :--- |
| **Frontend** | Vanilla HTML5, CSS3 (VW Brand System), JavaScript (ES6+), Google Maps JS SDK |
| **Backend API** | Python 3.11+, Flask REST API, SQLAlchemy |
| **AI / NLP** | OpenAI GPT API / Google Gemini API (intent extraction & RAG embeddings) |
| **Database** | PostgreSQL 16 + PostGIS Spatial Extension (Docker container) |
| **Geospatial & Maps** | Google Maps Routes API, Places API, Geocoding API |
| **Music & Sound** | Audius Discovery API + Custom Procedural Karplus-Strong Synth |
| **Media Processing** | Pillow (PIL), EXIFRead, FFmpeg (cinematic video compilation) |
| **Testing & Quality** | Pytest, Playwright (End-to-End browser automation) |

---

## 🚀 Quick Start Guide

### Prerequisites
- Python 3.11 or higher
- Docker & Docker Compose (for PostgreSQL + PostGIS)
- FFmpeg (for video recap generation, optional)
- Node.js & npm (for Playwright E2E tests, optional)

### 1. Clone & Set Up Virtual Environment

```bash
git clone https://github.com/wavymejti/VW.git
cd VW
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### 2. Start PostgreSQL + PostGIS with Docker

```bash
docker compose up -d
```

This starts a PostgreSQL 16 instance with PostGIS enabled on `localhost:5432`.

### 3. Configure Environment Variables

Copy `.env.example` to `.env` and fill in your API credentials:

```bash
cp .env.example .env
```

Edit `.env`:

```ini
# AI Model API Keys (OpenAI or Gemini)
OPENAI_API_KEY=your_openai_api_key
GEMINI_API_KEY=your_gemini_api_key

# Google Maps Platform API Key
GOOGLE_MAPS_API_KEY=your_google_maps_api_key

# Database Connection (matches docker-compose.yml)
DATABASE_URL=postgresql://postgres:DupaBlada2137%3F@localhost:5432/postgres

# Flask Secret Key
SECRET_KEY=dev_secret_key_vw_planner
```

### 4. Apply Database Migrations

```bash
python apply_migration.py
```

### 5. Start the Application

```bash
python main.py
```

Open your browser and navigate to `http://localhost:5000`.

---

## 🧪 Testing

### Run Backend Unit & Integration Tests

```bash
pytest
```

### Run End-to-End (E2E) Browser Tests

```bash
npx playwright test
```

---

## 📚 Project Documentation

Detailed architectural, security, and onboarding guides are available in the repository:

- 📖 **[Project Presentation & Architecture Guide](docs/PROJECT_PRESENTATION.md)** — Comprehensive presentation guide & diagram breakdown.
- 💻 **[Poradnik instalacji na Windows (PL)](INSTRUKCJA_WINDOWS.md)** — Dokładna instrukcja uruchomienia krok po kroku dla systemu Windows.
- 📐 **[System Architecture Documentation](docs/DOKUMENTACJA_ARCHITEKTONICZNA.md)** — Database schema, PostGIS spatial queries, and API specifications.
- 🔒 **[Security & Audit Documentation](docs/DOKUMENTACJA_BEZPIECZENSTWA.md)** — Security policies, OWASP compliance, and authentication mechanics.
- 📋 **[Project Blueprint Documentation](docs/DOKUMENTACJA_PROJEKTOWA.md)** — Functional specifications, requirements, and user flows.
- 🧪 **[Test Plan & QA Audit](docs/TEST_PLAN.md)** — Automated and manual testing matrix.

---

## 🎨 Brand Guidelines (Volkswagen California)

| Design Token | Value | Usage |
| :--- | :--- | :--- |
| **Primary Color** | `#001E50` | Headers, primary buttons, branding elements |
| **Secondary Color** | `#000E26` | Dark mode accents, footers, card backgrounds |
| **Accent / Link Color** | `#0000EE` | Interactive links, highlight indicators |
| **Background Color** | `#FFFFFF` | Page backgrounds, modal cards |
| **Text Primary** | `#000000` | Main readable body text |
| **Typography** | `vw-text`, `vw-head` | Official VW typography family |
| **Border Radius** | `8px` | Cards, buttons, and input fields |

---

## 📄 License

This project is released under the [MIT License](LICENSE).


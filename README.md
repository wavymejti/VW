# 🚐 VW California AI Trip Planner with Travel Memory

[![Python](https://img.shields.io/badge/Python-3.11+-001E50.svg?logo=python&logoColor=white)](https://www.python.org/)
[![Flask](https://img.shields.io/badge/Flask-3.0+-001E50.svg?logo=flask&logoColor=white)](https://flask.palletsprojects.com/)
[![PostgreSQL](https://img.shields.io/badge/PostgreSQL-PostGIS-001E50.svg?logo=postgresql&logoColor=white)](https://postgis.net/)
[![OpenAI](https://img.shields.io/badge/OpenAI-API-001E50.svg?logo=openai&logoColor=white)](https://openai.com/)
[![Google Maps](https://img.shields.io/badge/Google_Maps-Routes_&_Places-001E50.svg?logo=googlemaps&logoColor=white)](https://developers.google.com/maps)
[![License](https://img.shields.io/badge/License-MIT-001E50.svg)](LICENSE)

An intelligent, conversational web application designed specifically for Volkswagen California camper van owners. It combines **AI-driven route planning**, **camper-compatible campground recommendations**, **real-time spatial photo linking (Travel Memory)**, and **shareable trip summary generation**.

---

## 📸 Interface Preview

![VW California AI Trip Planner Dashboard](dashboard_mockup.png)

---

## ✨ Key Features

### 🗣️ Conversational AI Planning Mode
- **Holistic Slot-Filling**: Natural language interaction that gathers trip parameters (vibe, experience level, driving pace, infrastructure preferences, duration) without rigid forms.
- **Context-Aware Intent Extraction**: Converts user requests (e.g. *"Plan a 4-day scenic trip from Munich to the Alps with campgrounds that have shore power"*) into structured itinerary data.
- **Active Trip Modification**: Post-planning mode allowing users to add mid-trip attractions, swap days, or adjust overnight stays dynamically.

### 🗺️ Interactive Maps & Camping Integration
- **Google Maps JS SDK + Routes API**: Renders smooth, exact polyline directions for multi-day itineraries with daily distance/time estimates.
- **VW California Camping Compatibility**: Filters campgrounds by shore power hookups (`230V`), water access, max vehicle dimensions, and level ground.
- **Real-Time Weather Warnings**: Displays live forecast alerts along route waypoints.

### 📸 Travel Memory (Spatial EXIF Photo Sync)
- **Automatic EXIF GPS Extraction**: Reads latitude, longitude, and timestamps from uploaded user photos.
- **PostGIS Spatial Matching**: Auto-links photos to route segments within a 5 km boundary using PostGIS `ST_DWithin()`.
- **Interactive Photo Pins**: Displays photo thumbnails on the map exact locations where memories were captured.

### 🎬 Shareable Trip Summary Generator
- **Multi-Format Export**: Generates downloadable Video (`.mp4`), Image Slideshows (`.png`), and PDF Reports.
- **Background Soundtrack Integration**: Choose from customizable audio themes (*Acoustic Sunset, Vanlife Chill, Alpine Acoustic, etc.*).
- **Branded Design**: Formatted with Volkswagen California brand design guidelines.

### 🌍 Multilingual Support (i18n)
- Seamless real-time language switching between **English (EN)**, **Polish (PL)**, and **German (DE)**.

---

## 🏗️ System Architecture (A.N.T. 3-Layer Pattern)

The project adheres to the **A.N.T. (Architecture, Navigation, Tools)** software engineering pattern:

```
┌──────────────────────────────────────────────────────────┐
│  Layer 1: Architecture (architecture/ & SOPs)            │
│  - Standard Operating Procedures (SOPs in Markdown)      │
│  - routing_sop.md, camping_search_sop.md, etc.          │
├──────────────────────────────────────────────────────────┤
│  Layer 2: Navigation (navigation/ & Flask Server)        │
│  - Dispatcher & Intent Orchestration (dispatcher.py)    │
│  - Chat Conversation Handler (chat_handler.py)          │
│  - REST API Routes & Web UI Server (tools/server.py)    │
├──────────────────────────────────────────────────────────┤
│  Layer 3: Tools (tools/ & Atomic Python Scripts)         │
│  - plan_route.py, search_campings.py, extract_exif.py    │
│  - suggest_attractions.py, generate_summary.py           │
│  - PostgreSQL + PostGIS Data Store                     │
└──────────────────────────────────────────────────────────┘
```

---

## 🛠️ Tech Stack & Technologies

| Layer | Technology |
| :--- | :--- |
| **Frontend** | Vanilla HTML5, CSS3 (VW Brand System), JavaScript (ES6+), Google Maps JS SDK |
| **Backend API** | Python 3.11+, Flask REST API, SQLAlchemy |
| **AI / NLP** | OpenAI GPT API (with fallback support for Google Gemini) |
| **Database** | PostgreSQL 16 + PostGIS Extension |
| **Geospatial & Maps** | Google Maps Routes API, Places API, Geocoding API |
| **Media Processing** | Pillow (PIL), EXIFRead, FFmpeg (video compilation) |
| **Testing & Quality** | Pytest, Playwright (End-to-End browser automation), ESLint |

---

## 🚀 Quick Start Guide

### Prerequisites
- Python 3.11 or higher
- PostgreSQL with PostGIS extension enabled
- Node.js & npm (for Playwright E2E tests, optional)
- FFmpeg (for video summary exports, optional)

### 1. Clone & Set Up Virtual Environment

```bash
git clone https://github.com/wavymejti/VW.git
cd VW
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### 2. Configure Environment Variables

Create a `.env` file in the root directory:

```ini
# OpenAI & Gemini API Keys
OPENAI_API_KEY=your_openai_api_key
GEMINI_API_KEY=your_gemini_api_key

# Google Maps API Key
GOOGLE_MAPS_KEY=your_google_maps_api_key

# Database Connection String
DB_URL=postgresql://vw_user:vw_password@localhost:5432/vw_california_db

# Server Secret
SECRET_KEY=your_flask_secret_key
```

### 3. Initialize Database & Run Migrations

```bash
python apply_migration.py
```

### 4. Start the Application Server

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

Detailed architectural and technical documentation is available in the repository:

- 📖 **[Project Presentation & Architecture Guide](PROJECT_PRESENTATION.md)** — Comprehensive presentation guide & diagram breakdown.
- 📐 **[System Architecture Documentation](DOKUMENTACJA_ARCHITEKTONICZNA.md)** — Detailed database schema, PostGIS spatial queries, and API specs.
- 🔒 **[Security & Audit Documentation](DOKUMENTACJA_BEZPIECZENSTWA.md)** — Security policies, OWASP compliance, and authentication mechanics.
- 📋 **[Project Blueprint Documentation](DOKUMENTACJA_PROJEKTOWA.md)** — Core requirements, functional specifications, and user flows.
- 🧪 **[Test Plan & QA Audit](TEST_PLAN.md)** — Automated and manual testing matrix.

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

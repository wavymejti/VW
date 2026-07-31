# 🚐 VW California AI Trip Planner — Dogłębna Dokumentacja Projektowa

---

## 1. Wstęp i Wizja Projektu (North Star)

### 1.1 Cel Projektu
**VW California AI Trip Planner with Travel Memory** to zaawansowana aplikacja webowa przeznaczona dla właścicieli vanów kempingowych Volkswagen California. System wspiera użytkowników w pełnym cyklu podróży:
1. **Konwersacyjnym planowaniu tras** z wykorzystaniem sztucznej inteligencji (Gemini / OpenAI API) oraz logiki *slot-filling*.
2. **Wyszukiwaniu kempingów** dostosowanych do gabarytów pojazdu, wymogów podłączenia prądu (*shore power*) i preferowanych udogodnień.
3. **Automatycznym budowaniu pamięci podróży (*Travel Memory*)** poprzez przestrzenne wiązanie zdjęć użytkownika (z geolokalizacją EXIF GPS) z polilinią przejechanej trasy w bazie PostGIS.
4. **Generowaniu multimedialnych podsumowań wyjazdów** (pokaz slajdów, wideo MP4 z muzyką, raporty PDF) do udostępniania i archiwizacji.

```mermaid
graph TD
    A[Użytkownik VW California] -->|Interfejs Konwersacyjny / Głosowy| B[Moduł AI Gemini - Slot Filling]
    B -->|Wykrycie intencji i parametrów| C[Warstwa Nawigacji & Dispatcher]
    C -->|Obliczanie tras & atrakcji| D[Google Maps Routes API & Places API]
    C -->|Wyszukiwanie noclegów| E[Baza PostGIS + Google Maps Fallback]
    A -->|Upload Zdjęć| F[Travel Memory Pipeline - EXIF GPS]
    F -->|ST_DWithin 5km| G[Relacyjno-Przestrzenne Wiązanie w PostGIS]
    G -->|Generowanie Mediów| H[Export Podsumowań - MP4 / PDF / Slideshow]
```

---

### 1.2 Identyfikacja Wizualna i Brand Guidelines VW
Aplikacja została zaprojektowana zgodnie z oficjalnymi wytycznymi marki **Volkswagen California** (`brandguidelines/`):

| Token Stylu | Wartość | Zastosowanie w UI |
| :--- | :--- | :--- |
| **Primary Color** | `#001E50` | Główne nagłówki, paski nawigacyjne, akcenty branżowe |
| **Secondary Color** | `#000E26` | Tła trybu ciemnego, panele boczne, podkłady kart |
| **Accent / Link** | `#0000EE` | Przyciski akcji, odsyłacze, aktywne zakłady |
| **Background** | `#FFFFFF` / Ciemny motyw | Tło aplikacji i podglądu mapy |
| **Typografia** | `vw-head`, `vw-text` (fallback: Helvetica, Arial) | Krój pisma w całej aplikacji |
| **Nagłówek H1** | `51.936px` | Główny tytuł ekranu planowania |
| **Nagłówek H2** | `38.048px` | Tytuły sekcji i dni wycieczki |
| **Promień krawędzi**| `8px` | Karty atrakcji, przyciski, modale |

---

## 2. Architektura Systemu (Wzorzec A.N.T. 3-Layer)

Projekt wykorzystuje wzorzec architektoniczny **A.N.T. (Architecture, Navigation, Tools)** zapewniający pełną separację odpowiedzialności, modularność oraz łatwość testowania i rozbudowy.

```mermaid
graph TD
    subgraph Layer 1: Architecture - architecture/
        A1[routing_sop.md]
        A2[camping_search_sop.md]
        A3[travel_memory_sop.md]
        A4[chat_orchestration_sop.md]
        A5[summary_export_sop.md]
    end

    subgraph Layer 2: Navigation - navigation/ & server.py
        B1[server.py - Serwer REST Flask]
        B2[dispatcher.py - Routing narzędzi]
        B3[chat_handler.py - Orkiestracja rozmowy AI]
    end

    subgraph Layer 3: Tools - tools/
        C1[plan_route.py]
        C2[search_campings.py]
        C3[suggest_attractions.py]
        C4[extract_exif.py]
        C5[memory_logger.py]
        C6[generate_summary.py]
        C7[get_weather.py]
        C8[db.py]
    end

    Layer 1 -. Standardy i Kontrakty .-> Layer 2
    Layer 2 -->|Wydawanie poleceń| Layer 3
    Layer 3 -->|Persystencja danych| D[(PostgreSQL + PostGIS)]
```

### 2.1 Opis Warstw Architecture (SOP)
Warstwa 1 zawiera specyfikacje i standardy postępowania opisane w plikach Markdown:
- [routing_sop.md](file:///Users/mateuszszymkowiak/Documents/GitHub/VW/architecture/routing_sop.md): Zasady wyznaczania dziennych limitów jazdy (max 6h) i rozbijania trasy na etapy.
- [camping_search_sop.md](file:///Users/mateuszszymkowiak/Documents/GitHub/VW/architecture/camping_search_sop.md): Kryteria kompatybilności vanów (wymiary, zasilanie 230V, gospodarka wodna).
- [travel_memory_sop.md](file:///Users/mateuszszymkowiak/Documents/GitHub/VW/architecture/travel_memory_sop.md): Algorytmy ekstrakcji metadanych EXIF i przestrzennego dopasowywania zdjęć.
- [chat_orchestration_sop.md](file:///Users/mateuszszymkowiak/Documents/GitHub/VW/architecture/chat_orchestration_sop.md): Reguły konwersacyjne i mechanizm zbiorczego dopytywania o parametry (*holistic slot filling*).
- [summary_export_sop.md](file:///Users/mateuszszymkowiak/Documents/GitHub/VW/architecture/summary_export_sop.md): Formatowanie wyjściowe materiałów promocyjnych/pamiątkowych.

### 2.2 Warstwa Navigation (Orkiestracja)
- [server.py](file:///Users/mateuszszymkowiak/Documents/GitHub/VW/tools/server.py): Serwer HTTP Flask udostępniający REST API, obsługujący sesje, autoryzację JWT/Session oraz serwowanie aplikacji frontendowej.
- [chat_handler.py](file:///Users/mateuszszymkowiak/Documents/GitHub/VW/navigation/chat_handler.py): Zarządza historią konwersacji, konstruuje prompt systemowy marki VW oraz przekazuje wiadomości do modułu LLM.
- [dispatcher.py](file:///Users/mateuszszymkowiak/Documents/GitHub/VW/navigation/dispatcher.py): Parsuje odpowiedź AI, wyciąga intencje (*function calling*) i uruchamia odpowiednie narzędzia z Warstwy 3.

### 2.3 Warstwa Tools (Narzędzia Atomowe)
- [plan_route.py](file:///Users/mateuszszymkowiak/Documents/GitHub/VW/tools/plan_route.py): Integracja z Google Maps Routes API, kalkulacja dystansów, czasów przejazdu i podziału na dni.
- [search_campings.py](file:///Users/mateuszszymkowiak/Documents/GitHub/VW/tools/search_campings.py): Przeszukiwanie bazy PostGIS oraz Google Places API pod kątem kempingów.
- [suggest_attractions.py](file:///Users/mateuszszymkowiak/Documents/GitHub/VW/tools/suggest_attractions.py): Wyszukiwanie atrakcji turystycznych wzdłuż wyznaczonego odcinka trasy.
- [extract_exif.py](file:///Users/mateuszszymkowiak/Documents/GitHub/VW/tools/extract_exif.py): Odczyt nagłówków EXIF (współrzędne GPS, data wykonania, model aparatu).
- [memory_logger.py](file:///Users/mateuszszymkowiak/Documents/GitHub/VW/tools/memory_logger.py): Dopasowywanie zdjęć do trasy przy użyciu funkcji przestrzennych PostGIS (`ST_DWithin`).
- [generate_summary.py](file:///Users/mateuszszymkowiak/Documents/GitHub/VW/tools/generate_summary.py): Generowanie slajdów, wideo MP4 (poprzez FFmpeg) oraz dokumentów PDF.
- [get_weather.py](file:///Users/mateuszszymkowiak/Documents/GitHub/VW/tools/get_weather.py): Pobieranie prognozy pogody dla punktów docelowych.
- [db.py](file:///Users/mateuszszymkowiak/Documents/GitHub/VW/tools/db.py): Pula połączeń i metody dostępowe do bazy danych PostgreSQL.

---

## 3. Schemat Bazy Danych (PostgreSQL + PostGIS)

Baza danych wykorzystuje rozszerzenie przestrzenne **PostGIS**, pozwalając na przechowywanie punktów i polilinii w układzie współrzędnych **EPSG:4326** (WGS 84).

```mermaid
erDiagram
    users ||--o{ trips : "tworzy"
    users ||--o{ photos : "przesyła"
    trips ||--o{ daily_schedules : "zawiera"
    trips ||--o{ chat_messages : "rejestruje"
    trips ||--o{ trip_summaries : "generuje"
    daily_schedules }|--o| campings : "wybiera nocleg"
    photos }|--o| trips : "powiązane z"
    photos }|--o| daily_schedules : "przypisane do dnia"
    trip_summaries }|--|| users : "generuje dla"
```

### 3.1 Definicje Tabel SQL

#### Tabela `users`
Przechowuje konta użytkowników, preferencje podróży oraz parametry pojazdu.
```sql
CREATE TABLE users (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    email VARCHAR(255) UNIQUE NOT NULL,
    display_name VARCHAR(100) NOT NULL,
    password_hash VARCHAR(255),
    vehicle_model VARCHAR(100) DEFAULT 'VW California Ocean 6.1',
    max_daily_drive_hours NUMERIC(3, 1) DEFAULT 6.0,
    preferred_amenities TEXT[] DEFAULT '{}',
    budget_per_night_eur NUMERIC(8, 2),
    hookup_type VARCHAR(50) DEFAULT 'shore_power',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);
```

#### Tabela `trips`
Przechowuje skrótowe metadane całego wyjazdu.
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

#### Tabela `daily_schedules`
Przechowuje szczegółowy harmonogram dla każdego dnia wycieczki.
```sql
CREATE TABLE daily_schedules (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    trip_id UUID NOT NULL REFERENCES trips(id) ON DELETE CASCADE,
    day_number INTEGER NOT NULL,
    date DATE,
    driving_hours NUMERIC(4, 2),
    driving_km NUMERIC(6, 1),
    waypoints JSONB DEFAULT '[]'::jsonb,
    overnight_camping_id UUID REFERENCES campings(id) ON DELETE SET NULL,
    route_polyline TEXT,
    return_route_polyline TEXT,
    return_custom_color VARCHAR(30) DEFAULT '#FF5722',
    created_at TIMESTAMPTZ DEFAULT NOW()
);
```

#### Tabela `campings`
Baza kempingów ze współrzędnymi geograficznymi i wykazem przyłączy.
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
    level_ground BOOLEAN DEFAULT TRUE,
    rating NUMERIC(2, 1),
    review_count INTEGER DEFAULT 0,
    photos TEXT[] DEFAULT '{}',
    source VARCHAR(50) DEFAULT 'google_maps',
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Indeks przestrzenny GiST dla szybkiego wyszukiwania w promieniu
CREATE INDEX idx_campings_location ON campings USING GIST (location);
```

#### Tabela `photos` (Travel Memory)
Przechowuje wczytane zdjęcia oraz ich pozycje GPS.
```sql
CREATE TABLE photos (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    trip_id UUID REFERENCES trips(id) ON DELETE SET NULL,
    file_url VARCHAR(512) NOT NULL,
    thumbnail_url VARCHAR(512),
    location GEOGRAPHY(POINT, 4326),
    lat NUMERIC(10, 7),
    lng NUMERIC(10, 7),
    captured_at TIMESTAMPTZ,
    exif_metadata JSONB DEFAULT '{}'::jsonb,
    caption TEXT,
    tagged_day_schedule_id UUID REFERENCES daily_schedules(id) ON DELETE SET NULL,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_photos_location ON photos USING GIST (location);
```

---

## 4. Kluczowe Funkcjonalności i Moduły Systemu

### 4.1 Slot-Filling Engine & Orkiestracja AI
W przeciwieństwie do tradycyjnych formularzy webowych, czat AI buduje wycieczkę zbierając 5 wymiarów konfiguracyjnych:
1. **`vibe`**: Klimat podróży (góry, morze, natura, urokliwe miasteczka).
2. **`experience`**: Doświadczenie kierowcy kempingowego.
3. **`pace`**: Tempo jazdy (wolne/wypoczynkowe vs. intensywne zwiedzanie).
4. **`infrastructure`**: Wymagany poziom udogodnień (dziki kemping vs. pełne przyłącza 230V).
5. **`duration`**: Czas trwania wyjazdu w dniach.

> [!TIP]
> **Holistic Parameter Gathering**: Jeśli użytkownik podał niepełne informacje, moduł AI zadaje **jedno zwięzłe pytanie uzupełniające**, łącząc brakujące parametry w płynny sposób.

### 4.2 Personalizacja Trasy Powrotnej i Sugestia Atrakcji
- **Wielobarwne polilinie**: System wspiera osobne rysowanie trasy tam oraz trasy powrotnej (`return_route_polyline`) z możliwością zmiany koloru (domyślnie `#FF5722`).
- **Sugestie atrakcji (`suggest_attractions.py`)**: Automatycznie skanuje otoczenie trasy i proponuje punktowe atrakcje turystyczne (punkt widokowy, punkt gastronomiczny, zamki, jeziora) dostosowane do czasu trwania przejazdu.

### 4.3 Travel Memory Pipeline
Silnik pamięci podróży automatycznie porządkuje zdjęcia użytkownika:
1. Odczytuje metadane EXIF (w tym współrzędne GPS i czas wykonania).
2. Wykonuje zapytanie przestrzenne PostGIS:
   ```sql
   SELECT id FROM daily_schedules 
   WHERE trip_id = %s 
     AND ST_DWithin(
         ST_SetSRID(ST_MakePoint(%s, %s), 4326)::geography, 
         route_polyline_geog, 
         5000 -- bufor 5 km
     );
   ```
3. Przypisuje zdjęcie do odpowiedniego dnia wyprawy i umieszcza interaktywną pinezkę ze miniaturką na mapie.

### 4.4 Generator Podsumowań Multimedialnych (`generate_summary.py`)
Generuje pamiątkowe materiały po zakończeniu wyjazdu:
- **Slideshow (Slajdy)**: Zestaw grafik PNG ze statystykami, mapą i kartami dni.
- **Wideo MP4**: Generowane przy użyciu biblioteki Pillow i narzędzia `ffmpeg`, zawierające płynne przejścia i podkład muzyczny.
- **Dokument PDF**: Infograficzny raport podróżny w formacie PDF gotowy do druku.

### 4.5 Moduł Czatu Głosowego (Voice Control)
Aplikacja oferuje zintegrowany interfejs mowy na urządzeniach mobilnych oraz tabletach:
- **Speech-to-Text (STT)**: Rozpoznawanie poleceń głosowych w czasie rzeczywistym.
- **Text-to-Speech (TTS)**: Odczytywanie odpowiedzi asystenta AI oraz wskazówek dojazdu.

### 4.6 Wielojęzyczność (i18n)
Dzięki modułowi [i18n.js](file:///Users/mateuszszymkowiak/Documents/GitHub/VW/frontend/i18n.js), interfejs użytkownika dynamicznie przełącza się pomiędzy trzema językami:
- **Niemiecki (DE)** — domyślny język marki VW California.
- **Angielski (EN)** — język międzynarodowy.
- **Polski (PL)** — pełna lokalizacja interfejsu.

---

## 5. Podgląd Interfejsu i Frontend Dashboard

Interfejs użytkownika został zaprojektowany z myślą o konsolach nawigacyjnych w pojazdach oraz tabletach:

![VW California AI Trip Planner Dashboard UI Mockup](dashboard_mockup.png)

### Struktura Plików Frontendowych:
- [index.html](file:///Users/mateuszszymkowiak/Documents/GitHub/VW/frontend/index.html): Główny szablon aplikacji z podziałem na panele (Czat AI, Mapa Google, Harmonogram Dniowy, Galeria Memories, Ustawienia Profilu).
- [styles.css](file:///Users/mateuszszymkowiak/Documents/GitHub/VW/frontend/styles.css): Dedykowane style w czystym CSS3 wykorzystujące paletę VW, nawigację dotykową i panele typu glassmorphism.
- [app.js](file:///Users/mateuszszymkowiak/Documents/GitHub/VW/frontend/app.js): Główna logika aplikacji frontendowej, inicjalizacja mapy Google, obsługa mikrofonu, przesyłanie zdjęć i komunikacja z API.
- [i18n.js](file:///Users/mateuszszymkowiak/Documents/GitHub/VW/frontend/i18n.js): Słownik tłumaczeń i silnik podmiany tekstów UI.

---

## 6. Specyfikacja REST API (`server.py`)

Aplikacja udostępnia interfejs RESTful API do komunikacji z klientem:

| Metoda | Endpoint | Opis |
| :--- | :--- | :--- |
| `POST` | `/api/auth/register` | Rejestracja nowego użytkownika i profilu pojazdu |
| `POST` | `/api/auth/login` | Logowanie i ustanowienie sesji |
| `GET` | `/api/auth/me` | Pobranie danych aktualnie zalogowanego profilu |
| `POST` | `/api/chat` | Przesłanie wiadomości tekstowej/głosowej do asystenta AI |
| `GET` | `/api/trips` | Pobranie listy zapisanych wyjazdów użytkownika |
| `POST` | `/api/trips` | Utworzenie nowej trasy |
| `GET` | `/api/trips/<id>` | Szczegóły wycieczki wraz z rozpisem dniowym |
| `PUT` | `/api/trips/<id>/route-color` | Aktualizacja koloru trasy powrotnej |
| `POST` | `/api/photos/upload` | Upload zdjęcia, ekstrakcja EXIF i dopasowanie do trasy |
| `GET` | `/api/photos/trip/<id>` | Pobranie galerii zdjęć przypisanych do wyjazdu |
| `POST` | `/api/summaries/generate` | Inicjalizacja generowania podsumowania (MP4 / PDF / Slajdy) |

---

## 7. Instrukcja Uruchomienia i Wdrożenia

### 7.1 Wymagania Wstępne
- **Python**: 3.10 lub wyższy
- **Baza Danych**: PostgreSQL 14+ z rozszerzeniem **PostGIS**
- **Multimediów**: `ffmpeg` zainstalowane w systemie (do generowania wideo MP4)
- **Przeglądarki / Testy**: Node.js & Playwright

### 7.2 Konfiguracja Zmiennych Środowiskowych (`.env`)
Utwórz plik `.env` w głównym katalogu projektu:
```env
GEMINI_API_KEY=your_gemini_api_key_here
GOOGLE_MAPS_KEY=your_google_maps_api_key_here
DATABASE_URL=postgresql://postgres:postgres@localhost:5432/vw_california_db
SECRET_KEY=your_random_flask_secret_key
FLASK_PORT=5000
```

### 7.3 Inicjalizacja Bazy Danych
Zainstaluj zależności Python i uruchom migrację:
```bash
pip install -r requirements.txt
python apply_migration.py
```

### 7.4 Uruchomienie Serwera i Testów
Uruchomienie serwera aplikacji backendowej:
```bash
python tools/server.py
```
Aplikacja będzie dostępna pod adresem: `http://localhost:5000`

Uruchomienie pakietu testów jednostkowych:
```bash
pytest tests/
```

Uruchomienie testów End-to-End (Playwright):
```bash
npx playwright test
```

---
*Dokumentacja wygenerowana dla projektu VW California AI Trip Planner — Zgodna z protokołem B.L.A.S.T. i wzorcem A.N.T.*

# Travel Suggestions SOP (Visual Inspirations & RAG Integration)

> Standard Operating Procedure for the Suggestive Travel Inspirations layer.
> **Golden Rule**: Update this SOP before updating code in `tools/travel_suggestions.py` or frontend suggestion handlers.

---

## 1. Purpose & Target Persona

Enable the VW California AI Trip Planner to proactively propose captivating, highly relevant travel concepts to users **before** they type their first message in the chat.

### Target Audience: Middle-Aged Travelers (40–60 years)
Travelers in this demographic seeking VW California adventures prioritize:
* **Comfort & Infrastructure**: Reliable campsites with 230V shore power hookups, level ground, clean sanitary facilities, and peaceful surroundings.
* **Slow Travel & Scenic Routes**: Scenic panoramic drives (max 3–4 hours driving per day) instead of congested highways; curated stops for vistas, local coffee, and artisanal food.
* **Culture, Wine & Gastronomy**: Historic towns, castles, valley vineyards, agritourism, regional slow food, and wine tastings.
* **Nature & Gentle Recreation**: Crystal-clear lakes, pine-fringed coastal walks, gentle hiking trails, and e-bike paths.
* **Low Friction**: Eliminates the "cold start" blank chat box fatigue by presenting immediate visual options.

---

## 2. Architecture & Data Flow

```text
                                 READ PATH (Modal Presentation)
Session Start / Fresh Chat ───► GET /api/travel_suggestions?lang=pl
                                         │
                                         ▼
                          [tools/travel_suggestions.py: generate_dynamic_suggestions]
                                         │
               ┌─────────────────────────┴─────────────────────────┐
               ▼                                                   ▼
      User has active RAG memories?                       No memories / Anonymous
               │                                                   │
               ▼                                                   ▼
      Fetch top memories from user_memories                Apply Curated 40-60 Persona Archetypes
      (e.g., "Podróżuje z psem", "Lubi jeziora")           (Vineyards, Lakes & Alps, Castles, Coast)
               │                                                   │
               └─────────────────────────┬─────────────────────────┘
                                         │
                                         ▼
                            LLM Structured Generation
                            (gpt-4o-mini / Gemini fallback)
                                         │
                                         ▼
                            Scenic Imagery & Tag Pairing
                                         │
                                         ▼
                            JSON Response with Suggestions
                                         │
                                         ▼
                       Frontend: Centered Visual Modal Display

───────────────────────────────────────────────────────────────────────────────────

                                 WRITE PATH (User Selection)
User clicks Suggestion Card ───► POST /api/travel_suggestions/select
                                         │
                                         ▼
                          [tools/travel_suggestions.py: record_suggestion_choice]
                                         │
                                         ▼
                          [tools/user_memory.py: save_user_memory]
                          Stores new durable preference (category, polarity, content)
                                         │
                                         ▼
                          Modal Closes ──► chat_handler: send_message(suggestion.prompt)
```

---

## 3. Data Contract (Suggestion Card JSON)

Each suggestion card served to the client adheres to this structure:

```json
{
  "id": "string (unique identifier)",
  "title": "string (e.g. 'Szlak Toskańskich Winnic')",
  "subtitle": "string (short evocative description of vibe, driving pace, and landscape)",
  "category": "wine_gastronomy | lakes_mountains | castles_culture | coastal_calm | scenic_nature",
  "duration_category": "weekend | week | expedition | all",
  "duration_days": 3,
  "image_url": "string (high quality photographic CDN or local asset)",
  "tags": ["string (e.g. 'Slow Travel', 'Winnice', 'Prąd 230V', 'Spokój')"],
  "prompt": "string (pre-crafted natural language trip query dispatched to chat)",
  "badge": "string | null (e.g. 'Dopasowane do Ciebie ✨' if matched via RAG)",
  "rag_matched": "boolean",
  "rag_reason": "string | null (e.g. 'Polecane, ponieważ wspomniałeś o zamiłowaniu do winnic i kempingów z prądem 230V')",
  "vw_highlights": ["string (e.g. 'Parcele z przyłączem CEE', 'Panoramiczne punkty widokowe')"]
}
```

---

## 4. RAG Synergy & Transparency Rules

1. **Read Personalization & Transparency**: If the user has saved preferences in `user_memories` (e.g., dog owner, quiet campings, preference for lakes, avoidance of toll highways), the LLM prompt incorporates these facts to skew suggestions toward those preferences. Cards reflecting these memories receive `rag_matched: true`, badge `"Dopasowane do Ciebie ✨"`, and a specific, natural-language `rag_reason` explaining why the suggestion matches their saved preferences (e.g., *"Polecane, ponieważ wspomniałeś o podróży z psem i unikaniu autostrad"*).
2. **Write Reinforcement**: Selecting a card is an explicit declaration of travel intent. The system extracts the persistent travel preference implied by the card and records it in `user_memories` under the appropriate category (`camping_style`, `activities`, `driving_pace`), ensuring future assistant responses respect this inclination.
3. **Trip Duration Filters (*Duration Pills*) & Realistyczny Zasięg Geograficzny**:
   - `weekend` (2–4 dni, **ZASIĘG BLISKI: max 200–350 km / 2–3.5h jazdy od punktu startowego**):
     KATEGORYCZNY ZAKAZ proponowania odległych rejonów Europy (np. Prowansja, Dolomity, Toskania, Norwegia, Chorwacja dla osób startujących z Polski). Podróż camperem na weekend ma być relaksem, a nie maratonem autostradowym. Dla użytkownika z Polski sugerowane są urokliwe regiony lokalne i przygraniczne: Mazury, Kaszuby, Pojezierze Drawskie, Bory Tucholskie, Jura Krakowsko-Częstochowska, Dolina Baryczy, Lubuskie winnice, Karkonosze, Kotlina Kłodzka, Morawy.
   - `week` (5–8 dni, **ZASIĘG ŚREDNI: do 600–900 km** z 1–2 bazami noclegowymi, np. Morawy, Alpy Austriackie/Karyntia, Słowacja, Saksonia, polskie wybrzeże Bałtyku).
   - `expedition` (9–14 dni, **ZASIĘG DALEKI: 1000+ km rozłożony etapami**, np. Prowansja, Toskania, Dolomity, fiordy Norwegii, Bretania, Chorwacja).
   - `all` (zrównoważony wachlarz, gdzie każda propozycja ściśle przestrzega relacji czasu do odległości od punktu startowego).
4. **Resilience & Fallback**: Jeśli zapytanie do LLM przekroczy 9.0s lub nastąpi błąd sieci, `get_curated_fallback_suggestions()` zwraca estetyczne, zrotowane karty awaryjne z zachowaniem ograniczeń zasięgu.
5. **Świadomość lokalizacji użytkownika (`origin` / `user_location`)**: Parametr lokalizacji (`location`, `city`, `country`) przekazywany z geolokalizacji przeglądarki jest wstrzykiwany do promptu generatora, by precyzyjnie wyliczyć realny promień dojazdu dla weekendu.
6. **Frequency & User Agency**: Modal pojawia się na czystym ekranie czatu (0 wiadomości). Trwały przycisk `"✨ Inspiracje"` w nagłówku czatu pozwala otworzyć go w dowolnej chwili.
7. **Ścisła wielojęzyczność (Strict Multilingual Generation & Cache Invalidation)**:
   - Cały system prompt dla LLM (instrukcje, wytyczne zasięgu geograficznego, kontekst RAG, schemat JSON oraz prompt użytkownika) jest formułowany w 100% w języku docelowym (`de`, `en`, `pl`), co eliminuje mieszanie języków w wygenerowanych kartach (tytuły, opisy, tagi, uzasadnienia RAG).
   - Frontendowa pamięć podręczna propozycji (`currentSuggestionsList`) rejestruje aktywny język (`currentSuggestionsLang`). Zmiana języka w aplikacji unieważnia cache i pobiera karty w wybranym języku.

---

## 5. Prompt Enrichment & Chat Activation Flow

Gdy użytkownik klika kafelek inspiracji ("Zaplanuj tę trasę" lub kliknięcie w kartę), zapytanie przekazywane do czatu nie może być ogólnym pytaniem, lecz **wzbogaconym, jednoznacznym poleceniem planowania** (Single-Turn Intent Fulfillment).

### Zasady Wzbogacania Promptu (Prompt Enrichment):
1. **Czas trwania (`duration_days`)**:
   - Wyraźne zadeklarowanie liczby dni (np. *"Zaplanuj dla mnie 3-dniowy wyjazd camperem VW California..."*).
   - Eliminuje konieczność dopytywania przez asystenta o długość podróży.
2. **Punkt startowy (`origin` / `user_location`)**:
   - Jeżeli geolokalizacja jest aktywna i znana (`state.locationEnabled && state.userLocation`), punkt startowy jest wstrzykiwany do promptu (np. *"...ze startem z: Poznań..."*).
   - Jeżeli geolokalizacja jest wyłączona lub niedostępna, klauzula startowa jest pomijana bez zgadywania.
3. **Cel i atmosfera (`destination`, `subtitle`)**:
   - Precyzyjny cel trasy (np. *"Cel: Mazurskie Uroki. Odkryj krystaliczne jeziora i malownicze lasy w sercu Mazur."*).
4. **Wymagania VW California (`vw_highlights`)**:
   - Wymienienie kluczowych parametrów kempingowych (np. *"Zależy mi na: parcelach z prądem 230V, ciszy nocnej i trasach na e-bike."*).

Dzięki temu czat natychmiast posiada komplet informacji do wywołania narzędzia `plan_route` bez zbędnego dialogu doprecyzowującego.

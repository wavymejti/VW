# User Memory RAG SOP

> Standard Operating Procedure for the Personalized Long-Term Memory (RAG) layer.
> **Golden Rule**: Update this SOP before updating code in `tools/user_memory.py` or `navigation/chat_handler.py`.

---

## 1. Purpose

Enable the VW California AI Trip Planner to remember and act upon long-term user preferences, habits, vehicle constraints, and travel styles across sessions without relying on static forms or polluting the context window.

---

## 2. Architecture & Data Flow

```text
                                WRITE PATH
User Input ───► [tools/user_memory.py: extract_memories_from_message]
                     │
                     ▼ (OpenAI gpt-4o-mini fact extraction)
                Atomic Facts (e.g. "Prefers quiet lakeside campings")
                     │
                     ▼ (OpenAI text-embedding-3-small)
                Normalized Embedding Vector (1536 floats)
                     │
                     ▼ (Deduplication / update)
                PostgreSQL: table `user_memories` (JSONB embedding)

                                READ PATH
User Input ───► [navigation/chat_handler.py: send_message]
                     │
                     ▼ (tools/user_memory.py: get_relevant_user_memories)
                text-embedding-3-small(query) ──► Cosine Similarity over user rows
                     │
                     ▼ Top-K matches (similarity >= threshold, default 0.45)
                [SYSTEM NOTE] Context Injection
                     │
                     ▼
                OpenAI Chat Completion with tools (search_campings, plan_route)
```

---

## 3. Database Specification (`user_memories`)

- `id UUID PRIMARY KEY DEFAULT uuid_generate_v4()`
- `user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE`
- `category VARCHAR(50) NOT NULL` (`camping_style`, `activities`, `pets`, `vehicle`, `dislikes`, `driving_pace`, `general`)
- `polarity VARCHAR(20) DEFAULT 'like'` (`like`, `dislike`, `constraint`, `habit`)
- `content TEXT NOT NULL`
- `embedding_json JSONB NOT NULL` (1536 float elements)
- `confidence NUMERIC(3, 2) DEFAULT 1.00`
- `is_active BOOLEAN DEFAULT TRUE`
- `created_at TIMESTAMPTZ DEFAULT NOW()`
- `updated_at TIMESTAMPTZ DEFAULT NOW()`

Indexed by `idx_user_memories_user_id` for fast $O(1)$ partition lookup per authenticated user.

---

## 4. Vector Similarity Calculation

Since OpenAI `text-embedding-3-small` outputs unit vectors ($L_2\text{ norm} = 1.0$), cosine similarity equals the dot product:

$$\text{similarity}(\vec{u}, \vec{v}) = \sum_{i=1}^{1536} u_i \cdot v_i$$

For an individual user with $N \le 100$ preference records, calculating the dot product in Python takes $< 0.2\text{ ms}$, eliminating the need for external vector database engines or C-extensions in PostgreSQL.

---

## 5. Memory Ingestion Rules

1. **Atomic facts only**: Extracted memories must be concise, declarative statements in natural language (e.g. *"Podróżuje z psem - unika kempingów bez wstępu dla zwierząt"*).
2. **Context vs. Long-term distinction**: One-time parameters (e.g. *"W tę środę chcę jechać do Berlina"*) belong to the current trip slots (`<slot_state>`), NOT to long-term memory. Long-term memory stores durable preferences.
3. **Deduplication**: If a new memory has cosine similarity $> 0.85$ with an existing active memory for the same user, the existing memory is updated rather than duplicated.
4. **User Control**: Users can inspect (`GET /api/memories`), add (`POST /api/memories`), or delete (`DELETE /api/memories/<id>`) memories in compliance with GDPR.

---

## 6. Remembered vehicle (Nov 2026)

The van the user travels in is a `vehicle` memory like any other (e.g. *"Podróżuje VW ID. Buzz (elektryczny)"*), so it lives in the same RAG store, is visible in `GET /api/user_memories` and can be deleted there.

- **Reading** — `tools/user_memory.py: remembered_vehicle(user_id)` takes the newest active `vehicle` memory that names a model and maps it to the stop planner's key (`vehicle_key_from_text`): `ev` (ID. Buzz, electric/elektryczny/elektrisch), `phev` (eHybrid, hybrid/hybryda, plug-in), `diesel` (T6.1, T7, TDI, diesel, a plain California). Checked in that order, so "California eHybrid" is `phev`. Memories about equipment (awning, bike rack) name no model and are skipped.
- **Writing** — `remember_vehicle(user_id, key)` (choosing a vehicle in the ⛽ Stops panel, `POST /api/vehicle`): `vehicle` memories naming another model are deleted, then one canonical memory is saved unless one with the same model already exists. Vehicles mentioned in the chat are saved by the normal extraction (its prompt names the models).
- **Using** — `find_route_stops` in the chat gets the remembered vehicle when the model passes none; `/api/route_stops` uses it when the request has no vehicle; the panel and the campsite window load it (`POST /api/vehicle` without a vehicle) and keep a copy in the browser for anonymous users.

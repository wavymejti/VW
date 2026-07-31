# Chat Orchestration SOP

> Standard Operating Procedure for the conversational AI layer.
> **Golden Rule**: Update this SOP before updating code in `navigation/chat_handler.py` or `tools/openai_client.py`.

---

## Purpose

Manage the conversational flow between the user and the OpenAI model, dispatching
structured intents to the appropriate tools. Ensure a natural, guided planning experience
for VW California camper van users through an advanced **Hard/Soft slot-filling architecture**.

---

## Architecture

```text
User Input
  → OpenAI API (with tools + system_prompt)
    → Hard Slot-filling check (all 5 filled?)
      → No  → Natural clarifying question (text response)
      → Yes → Soft Slot check (all filled or 2 rounds passed?)
                → Yes → Tool Call (`plan_route`) → Dispatcher
                  → OpenAI formats result (with transparency on daily splits)
                    → API returns slot_state (frontend updates progress bar)
```

---

## System Prompt & Tonality

The system instruction (`tools/openai_client.py`) sets the VW brand voice:
- Warm, competent travel companion. Not a form.
- Short sentences, uses "we" ("let's plan", "we are off to").
- No artificial enthusiasm for every user answer.

---

## Slot Model (9 Slots)

The chat collects 9 parameters before planning a route. They are divided into **Hard** and **Soft** slots.

### Hard Slots (Blocking)

`plan_route` CANNOT be called until these are filled.
1. `trip_type` — `"punkt-do-punktu"` (A to B) or `"baza-wypadowa"` (exploring a region). Must be clarified early if ambiguous.
2. `origin` — Starting location.
3. `start_date` — Starting date.
4. `duration` — Number of days.
5. `destination` — Depends on `trip_type`. Exact location for A to B, or general region/city for basecamp.

### Soft Slots (Non-Blocking)

These have default values. The AI asks a maximum of **2 rounds** for these. If still missing, it assumes defaults and communicates them before routing.
1. `party_composition` (Default: couple/small group of adults).
2. `experience` (Default: moderate experience).
3. `pace` (Default: basecamp every 2-3 days).
4. `infrastructure` (Default: mixed wild/full-service).

---

## Holistic Gathering & Contradictions

- **Holistic Gathering**: The AI groups missing questions into natural sentences, prioritizing hard slots. It does not ask sequentially.
- **Contradictions (Hard Rule)**:
  - If a user changes a **Hard Slot** (e.g., "7 days" to "14 days"), the AI MUST NOT overwrite silently. It must explicitly ask which one to use.
  - If a user changes a **Soft Slot**, the AI overwrites silently.

---

## Slot State (`<slot_state>`)

Every text response from the AI ends with a machine-readable JSON block tracking the 9 slots.
The backend `chat_handler.py` strips this from the visible text and returns it to the frontend.

```json
<slot_state>
{
  "trip_type": "baza-wypadowa",
  "origin": "Munich",
  "start_date": "2026-08-01",
  "duration": 7,
  "destination": "Alps",
  "party_composition": "couple",
  "experience": "veteran",
  "pace": "new-place-every-day",
  "infrastructure": "wild-camping"
}
</slot_state>
```
*Note: Unknown values are `null`.*

---

## Calling `plan_route`

Generating a route is expensive, so it is a **separate, explicitly confirmed step** — the AI never calls `plan_route` automatically immediately after completing slots.

1. AI ensures all Hard slots are filled.
2. AI assumes defaults for missing Soft slots (if max rounds exceeded).
3. AI writes a summary of collected data and ends it with an **explicit closing question**, e.g.: "Rozumiem: planujemy 14-dniową trasę... Zaczynam planować trasę?". It MUST NOT write "Daj mi chwilę..." at this stage.
4. AI **waits** for explicit user confirmation (e.g., "yes", "start").
5. As soon as the user confirms the plan (e.g., says "yes"), the AI MUST **IMMEDIATELY call the `plan_route` tool**. It must NOT ask additional clarifying questions (like confirming date formats) and must NOT repeat the summary.
6. If the user provides a correction instead of confirmation, the AI updates the slot, repeats the updated summary, and asks for confirmation again.
7. **Transparency Requirement**: The AI's final text presenting the route MUST explain the split between driving days and stationary days, justifying it based on `pace`, `experience`, and `trip_type`.

---

## Post-Planning Mode

Once a route is planned, the backend injects:
`[SYSTEM NOTE] Active trip ID: <uuid>. A route is already planned...`

The AI stops asking for trip parameters and handles intents:
- **Modify Route**: `modify_route` (changing cities, pace, avoiding regions).
- **Add Attraction**: `add_attraction` (specific POIs).
- **Information**: `search_campings` or general knowledge.
- **New Trip**: Requires explicit user confirmation before overwriting the current plan.
- **Ambiguous Command**: If the user says "change the camping", the AI must ask "which day?" before calling a tool.
- **Destructive Changes**: AI must briefly warn/confirm before deleting a day or shortening the trip.
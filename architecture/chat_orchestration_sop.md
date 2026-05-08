# Chat Orchestration SOP

> Standard Operating Procedure for the conversational AI layer.
> **Golden Rule**: Update this SOP before updating code in `navigation/chat_handler.py`.

---

## Purpose

Manage the conversational flow between the user and the OpenAI model (GPT), dispatching
structured intents to the appropriate tools. Ensure a natural, guided planning experience
for VW California camper van users through **slot-filling architecture**.

---

## Architecture

```text
User Input
  → OpenAI API (with tools + system_prompt)
    → Slot-filling check (all 5 filled?)
      → No  → Natural clarifying question (text response)
      → Yes → Tool Call → Dispatcher → Tool Script → Tool Response
                → OpenAI formats result → Final text to user
                  → API returns slot_state (frontend updates progress bar)
```

---

## System Prompt

The system instruction sets the VW brand voice and slot-filling behaviour:

- Professional, friendly, knowledgeable about camper van travel in Europe.
- Understands **VW California-specific needs** (shore power hookups, vehicle length, solar panels).
- Extracts structured data via OpenAI Function Calling.
- **Slot-filling guidance**: collects 5 parameters before calling `plan_route`, asking in
  natural order but accepting answers out of sequence.

### Holistic Parameter Gathering

The AI guides the user to collect the following slots, but it does NOT ask them one by one. It uses **Holistic Extraction** to gather as much context as possible from a single prompt:

| # | Slot | Key | Example values |
|---|---|---|---|
| 1 | **Vibe & Party** | `vibe` | mountains, coast, city; kids, pets, couple |
| 2 | **Experience** | `experience` | first-timer, intermediate, veteran |
| 3 | **Pace** | `pace` | new-place-every-day, basecamp |
| 4 | **Infrastructure** | `infrastructure` | wild-camping, full-service, mixed |
| 5 | **Duration** | `duration` | number of days |

> **Critical Routing Parameters**: The AI also implicitly extracts `origin` (Starting Point) and `start_date`.

### Handling Missing Information

If the user provides an extensive prompt (e.g., "Alps, wife, 7 days, wild camping, new place every day"), the AI will **acknowledge all of it** and check if any critical routing parameters (Origin, Start Date) or remaining slots are missing. 
If information is missing, the AI groups the remaining requirements into **one natural, bundled question** (e.g., "Super pomysł! Skąd ruszacie i kiedy?").

### Route Confirmation

Before calling `plan_route`, the AI **briefly confirms** all collected values in one sentence,
then calls the tool. Example:
> "Perfect — a 7-day wild camping trip to the Alps starting from Munich tomorrow. Let me plan your route now..."

---

## Slot State (slot_state)

Every API response from `/api/chat` includes a `slot_state` object indicating which slots
have been collected. The frontend uses this to update the progress bar.

```json
{
  "slot_state": {
    "vibe": "mountains_with_kids | null",
    "experience": "veteran | null",
    "pace": "basecamp | null",
    "infrastructure": "full-service | null",
    "duration": 7
  },
  "slots_complete": false
}
```

`slot_state` is extracted from the conversation history by the chat handler:
- After each turn, `chat_handler.py` calls a lightweight OpenAI completion (or regex scan)
  to extract current slot values from the conversation history.
- The result is appended to the API response JSON.

---

## Available Tools (OpenAI Tool Definitions)

| Tool | When to Call | Key Arguments |
|---|---|---|
| `search_campings` | User asks to find campgrounds in a specific area | `location`, `amenities_required` |
| `plan_route` | All 5 slots filled OR explicit action requested | `destination`, `duration_days`, `pace`, `granularity` |
| `expand_route_section` | User asks to detail part of a macro-plan | `section_id`, `start_date`, `end_date` |
| `add_waypoint` | User wants to add a stop to an existing day | `day_id`, `poi_name` |
| `adjust_schedule` | User wants to modify timing, swap days | `action`, `target_day` |
| `get_trip_summary` | User asks to see the current itinerary | `format` (brief/detailed) |

> **Duration rule**: If `duration_days` > 14 → Dispatcher forces `granularity: "macro"` to
> return a high-level chapter/basecamp plan instead of a daily breakdown.

---

## Conversation Flow

1. **Receive user message** — append to message history with `role: "user"`.

2. **Send to OpenAI API** — payload includes `model`, `messages` (history starting with
   `role: "system"`), and `tools` array.

3. **Check response `finish_reason`**:
   - **`stop` (slot-filling active)** → User has not provided all 5 slots. AI asks the next
     natural clarifying question. Return text to user directly.
   - **`tool_calls` (action requested)** → All slots filled or explicit action requested.
     Extract function name + args → send to Dispatcher.

4. **Execute tool** — Dispatcher routes to the correct tool script.

5. **Return tool result** — append to history with `role: "tool"` and `tool_call_id`.

6. **Generate final reply** — Call OpenAI API again with updated history. Model formats tool
   result as natural language (e.g., presents Macro plan and asks if user wants to detail Week 1).

7. **Extract slot_state** — Parse conversation history to determine which of the 5 slots have
   been mentioned. Append `slot_state` + `slots_complete` to the API response JSON.

8. **Store messages** — Save final assistant response to `chat_messages` table in DB.

---

## Error Handling

| Error | Action |
|---|---|
| OpenAI API timeout / 5xx | Retry once with exponential backoff, then apologise and suggest retry |
| Invalid function args (JSON validation failed) | Send system error message back to OpenAI as `role: "tool"` so model can auto-correct |
| Tool execution failure | Log error, append graceful error message as `role: "tool"`, let OpenAI inform the user |
| Ambiguous intent | Model should ask a clarifying question before calling a tool |
| Scope too large (>30 days detail) | Apologise, provide Macro plan, prompt user to plan week-by-week |
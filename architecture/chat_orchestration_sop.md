# Chat Orchestration SOP

> Standard Operating Procedure for the conversational AI layer.
> **Golden Rule**: Update this SOP before updating code in `navigation/chat_handler.py`.

---

## Purpose

Manage the conversational flow between the user and the Gemini AI,
dispatching structured intents to the appropriate tools.

## Architecture

```
User Input → Gemini API (with tools) → Function Call → Dispatcher → Tool → Response → Gemini → User
```

## System Prompt

The system instruction sets the VW brand voice:
- Professional, friendly, knowledgeable about camper van travel
- Understands VW California-specific needs
- Extracts structured data via function calling

## Available Tools (Gemini Function Definitions)

| Tool | When to Call |
|---|---|
| `search_campings` | User asks to find/discover campgrounds |
| `plan_route` | User asks to plan a trip or itinerary |
| `add_waypoint` | User wants to add a stop to an existing day |
| `adjust_schedule` | User wants to modify timing, swap days, rearrange |
| `get_trip_summary` | User asks to see the current itinerary |

## Conversation Flow

1. **Receive user message** — store as ChatMessage (role: "user").
2. **Send to Gemini** — include system prompt + conversation history + tools.
3. **Check response type**:
   - **Text only** → return to user directly.
   - **Function call** → extract function name + args → send to Dispatcher.
4. **Execute tool** — Dispatcher routes to the correct tool script.
5. **Return tool result** — send result back to Gemini as function response.
6. **Generate final reply** — Gemini formats the tool result as natural language.
7. **Store messages** — save assistant response as ChatMessage.

## Error Handling

| Error | Action |
|---|---|
| Gemini API timeout | Retry once, then apologize and suggest retry |
| Invalid function args | Ask user to rephrase with more detail |
| Tool execution failure | Log error, inform user gracefully |
| Ambiguous intent | Ask clarifying question before executing |

"""
OpenAI chat handler for the VW California AI Trip Planner.

Manages the conversational flow between the user and the
OpenAI model, dispatching function calls to tools via
the dispatcher.

Slot-filling: the AI embeds a <slot_state> JSON block in every
response. This handler strips it from the visible text and
returns it as a structured field in the API response.

See: architecture/chat_orchestration_sop.md
"""

import json
import re
import uuid
from datetime import datetime

from sqlalchemy import text

from tools.openai_client import (
    get_client,
    SYSTEM_PROMPT,
    MODEL_NAME,
    REASONING_SUPPORTED,
)
from tools.db import get_engine
from navigation.dispatcher import (
    dispatch,
    OPENAI_TOOL_DEFINITIONS,
    has_concrete_change,
)
from tools.interaction_logger import log_interaction
from tools.chat_log import log_chat_turn
import time
from tools.user_memory import (
    get_relevant_user_memories,
    format_memories_for_prompt,
    extract_memories_from_message,
)
from tools.location_service import (
    format_location_for_prompt,
    sanitize_coordinates,
)



def _real_user_id(session):
    """The logged-in user's id, or None for anonymous sessions (stored as "anon")."""
    uid = (session or {}).get("user_id")
    return None if not uid or uid == "anon" else uid


def create_chat_session(user_id=None, trip_id=None, lang="pl", load_history=True):
    """
    Create a new chat session with OpenAI, configured with
    VW trip planning tools and restored chat history.

    Args:
        user_id (str): Optional user UUID.
        trip_id (str): Optional trip UUID for context.
        lang (str): Selected language ('pl' or 'de').

    Returns:
        dict: Session info with client and config.
    """
    client = get_client()
    tools = OPENAI_TOOL_DEFINITIONS

    # Initialize history with system prompt
    history = [
        {"role": "system", "content": SYSTEM_PROMPT}
    ]

    # Restore saved chat messages from DB if available
    saved_history = load_chat_history(user_id=user_id, trip_id=trip_id) if load_history else []
    if saved_history:
        history.extend(saved_history)

    return {
        "client": client,
        "tools": tools,
        "user_id": user_id,
        "trip_id": trip_id,
        "history": history,
        "lang": lang or "pl",
        # Tracks the most recently planned trip — enables POST-PLANNING MODE
        "active_trip_id": trip_id,
    }


def _build_system_injections(session, user_message, user_location=None):
    """This turn's system notes: language, date, the 3-message rule, active trip, user prefs,
    long-term memories and location."""
    system_injections = []

    # Add language context injection
    lang = session.get("lang", "pl")
    if lang == "de":
        lang_context = (
            "[SYSTEM NOTE] User interface language is set to German (de). "
            "Respond in German. Maintain the VW California vanlife companion tone: "
            "address the user with informal 'Du', use proper German vanlife terminology "
            "(Landstrom / CEE-Anschluss, Aufstelldach, Wohnmobilstellplatz / Campingplatz, Freistehen). "
            "Plan the route as soon as start, destination and dates are known or can be inferred — "
            "no summary or confirmation question before planning. Never comment on <slot_state>."
        )
        system_injections.append({"role": "system", "content": lang_context})
    elif lang == "en":
        lang_context = (
            "[SYSTEM NOTE] User interface language is set to English (en). "
            "Always respond in English — also when the user writes in Polish, German or "
            "another language. Maintain the VW California vanlife companion tone: "
            "knowledgeable road-trip buddy, conversational, warm, enthusiastic about camper life. "
            "Use appropriate campervan terminology (shore power / hookup, pop-up roof, campsite / RV pitch, wild camping / boondocking). "
            "Plan the route as soon as start, destination and dates are known or can be inferred — "
            "no summary or confirmation question before planning. Never comment on <slot_state>."
        )
        system_injections.append({"role": "system", "content": lang_context})

    today = datetime.now()
    today_str = today.strftime("%Y-%m-%d (%A)")
    date_context = (
        f"[SYSTEM NOTE] Today is {today_str}. Trips start today or later, never in the past. "
        "Relative dates ('tomorrow', 'next weekend') count from today. A day or month "
        "without a year means its NEXT occurrence: if it has already passed this year, "
        f"use {today.year + 1} (e.g. '1 July' asked now -> {today.year + 1}-07-01)."
    )
    system_injections.append({"role": "system", "content": date_context})

    # The first route must come by the user's 3rd message at the latest.
    if not session.get("active_trip_id"):
        session["turns_without_plan"] = session.get("turns_without_plan", 0) + 1
        if session["turns_without_plan"] >= 3:
            system_injections.append({"role": "system", "content": (
                f"[SYSTEM NOTE] This is the user's message no. {session['turns_without_plan']} "
                "and there is no route yet. Call plan_route in THIS turn: assume anything "
                "missing (start from the user's location or the city mentioned, leave "
                "tomorrow, a sensible number of days for the distance) and say what you "
                "assumed. Only ask instead if the destination is completely unknown."
            )})

    active_trip_id = session.get("active_trip_id")
    if active_trip_id:
        # Insert a system reminder right after the main system prompt
        trip_context = (
            f"[SYSTEM NOTE] Active trip ID: {active_trip_id}. "
            "A route is already planned. Changes to THIS trip (via places, exclusions, "
            "more or fewer days, overnight stops) → modify_route / add_waypoint / "
            "add_attraction, without re-asking known parameters. A trip with a different "
            "origin or destination is a NEW trip → briefly confirm, then call plan_route "
            "with all its parameters (overnight_stops / num_days as the user said)."
        )
        system_injections.append({"role": "system", "content": trip_context})

    user_id = _real_user_id(session)
    if user_id:
        try:
            engine = get_engine()
            with engine.connect() as conn:
                prefs = conn.execute(
                    text("SELECT preferences_json FROM users WHERE id = :uid"), 
                    {"uid": user_id}
                ).scalar()
                if prefs and prefs != {}:
                    pref_context = f"[SYSTEM NOTE] User Preferences: {json.dumps(prefs)}. Keep these preferences in mind."
                    system_injections.append({"role": "system", "content": pref_context})
        except Exception as e:
            print(f"Failed to load user preferences: {e}")

        # Personalized RAG: retrieve and inject semantically relevant long-term memories
        try:
            relevant_memories = get_relevant_user_memories(
                user_id=user_id,
                query_text=user_message,
            )
            if relevant_memories:
                memory_note = format_memories_for_prompt(relevant_memories)
                system_injections.append({"role": "system", "content": memory_note})
        except Exception as e:
            print(f"[chat_handler] Failed to retrieve user memories: {e}")

    # Inject real-time user location context if provided
    if user_location and isinstance(user_location, dict):
        coords = sanitize_coordinates(user_location.get("lat"), user_location.get("lng"))
        if coords:
            normalized_loc = dict(user_location)
            normalized_loc["lat"], normalized_loc["lng"] = coords
            loc_note = format_location_for_prompt(normalized_loc, lang=lang)
            system_injections.append({"role": "system", "content": loc_note})
    return system_injections


def send_message(session, user_message, trip_id=None, user_location=None):
    """
    Send a user message, process any function calls,
    and return the final assistant response.

    Args:
        session (dict): Chat session from create_chat_session.
        user_message (str): The user's natural language input.
        trip_id (str): Trip UUID for storing chat messages.
        user_location (dict): Optional dict with user's current GPS location
            ({'lat': float, 'lng': float, 'name': str, ...}).

    Returns:
        dict: Response with assistant text and any tool results.
    """
    started = time.monotonic()
    effective_trip_id = trip_id or session.get("trip_id") or session.get("active_trip_id")
    user_id = _real_user_id(session)

    # Store user message in DB
    if user_id or _stored_trip(effective_trip_id):
        _store_message(user_id, effective_trip_id, "user", user_message)

    # Append user message to history
    session["history"].append(
        {"role": "user", "content": user_message}
    )

    try:
        client = session["client"]

        # Inject active trip context into a temporary system injection
        # so the AI knows a route already exists and enters POST-PLANNING MODE.
        messages_to_send = list(session["history"])
        system_injections = _build_system_injections(session, user_message, user_location)

        # The follow-up call after tool use needs the same notes (language etc.).
        session["system_injections"] = system_injections

        if system_injections:
            messages_to_send = [
                messages_to_send[0],
                *system_injections,
                *messages_to_send[1:],
            ]

        # Sanitize messages to satisfy OpenAI API contract (tool calls followed by tool responses)
        messages_to_send = _sanitize_messages_for_openai(messages_to_send)

        # Send to OpenAI with tools
        create_kwargs = dict(
            model=MODEL_NAME,
            messages=messages_to_send,
            tools=session["tools"],
        )
        if REASONING_SUPPORTED:
            create_kwargs["reasoning_effort"] = "none"
        response = client.chat.completions.create(**create_kwargs)

        # Process the response
        result = _process_response(
            session, response, effective_trip_id
        )

        log_interaction(user_message, result.get("text", ""))
        log_chat_turn(
            session.get("user_id"), session.get("lang"), MODEL_NAME, user_message,
            result, time.monotonic() - started,
            active_trip_id=session.get("active_trip_id"),
            raw_reply=session.pop("last_raw_reply", None),
        )

        # Non-blocking extraction of newly stated durable preferences
        if user_id:
            try:
                extract_memories_from_message(user_id, user_message)
            except Exception as e:
                print(f"[chat_handler] Memory extraction skipped: {e}")

        return result


    except Exception as e:
        import traceback
        print(f"❌ ERROR IN send_message: {e}")
        traceback.print_exc()

        lang = (session or {}).get("lang", "pl")
        if lang == "de":
            error_msg = "Entschuldigung, es gab ein vorübergehendes Problem. Bitte versuche es noch einmal."
        elif lang == "en":
            error_msg = "Sorry, a temporary connection or route processing issue occurred. Please try again."
        else:
            error_msg = "Przepraszam, wystąpił chwilowy problem z połączeniem lub przetworzeniem trasy. Spróbuj powtórzyć zapytanie."

        log_interaction(user_message, error_msg)
        log_chat_turn(
            (session or {}).get("user_id"), lang, MODEL_NAME, user_message,
            {"status": "error", "text": error_msg}, time.monotonic() - started,
            active_trip_id=(session or {}).get("active_trip_id"),
            error=f"{type(e).__name__}: {e}",
        )

        return {
            "status": "error",
            "message": error_msg,
            "text": error_msg,
            "tool_calls": [],
        }


def _for_model(result):
    """
    What the model reads back from a tool: route polylines, photos and the long
    campsite option details are dropped (the frontend still gets the full result).
    """
    if not isinstance(result, dict) or not result.get("daily_schedules"):
        return result
    slim = {k: v for k, v in result.items() if k != "daily_schedules"}
    slim["daily_schedules"] = []
    for d in result["daily_schedules"]:
        day = {k: v for k, v in d.items()
               if k not in ("route_polyline", "overnight_options", "overnight_camping", "weather")}
        camp = d.get("overnight_camping") or {}
        if camp:
            day["overnight_camping"] = {k: camp.get(k) for k in (
                "name", "source", "spot_type", "price_label", "price_info", "cost_per_night_eur",
                "has_power", "has_water", "has_showers", "has_toilets", "rating") if camp.get(k) is not None}
        day["overnight_options"] = [
            {k: o.get(k) for k in ("name", "source", "spot_type", "price_label", "price_info",
                                   "cost_per_night_eur")
             if o.get(k) is not None}
            for o in (d.get("overnight_options") or [])[:6]
        ]
        w = d.get("weather") or {}
        if w:
            day["weather"] = {k: w.get(k) for k in ("summary", "description", "temp_min", "temp_max",
                                                     "precipitation_mm", "alerts") if w.get(k) is not None}
        slim["daily_schedules"].append(day)
    return slim


def _compact_trip(result):
    """Small trip overview for the model: days, km, stops and campsites (no polylines/photos)."""
    trip = result.get("trip") or {}
    days = []
    for d in result.get("daily_schedules") or []:
        camp = d.get("overnight_camping") or {}
        days.append({
            "day": d.get("day_number"),
            "date": str(d.get("date") or d.get("schedule_date") or ""),
            "km": d.get("driving_km"),
            "hours": d.get("driving_hours"),
            "stay": bool(d.get("stay")) or all(
                w.get("type") == "stay" for w in (d.get("waypoints") or [{"type": ""}])),
            "stops": [f"{w.get('type')}: {w.get('label')}" for w in d.get("waypoints") or []],
            "campsite": camp.get("name"),
            "campsite_options": [
                {"name": o.get("name"), "source": o.get("source"),
                 "price": o.get("price_label") or o.get("price_info") or o.get("cost_per_night_eur")}
                for o in (d.get("overnight_options") or [])[:6]
            ],
        })
    return {
        "status": "success",
        "trip_id": trip.get("id") or result.get("trip_id"),
        "title": trip.get("title"),
        "start_date": trip.get("start_date"),
        "end_date": trip.get("end_date"),
        "total_driving_km": result.get("total_driving_km") or trip.get("total_driving_km"),
        "days": days,
    }


def _parse_slot_state(text, session=None):
    """
    Extract the <slot_state> JSON block from the AI response text.

    The AI appends a machine-readable slot_state block after its
    conversational reply. This function parses it and strips it
    from the visible message.

    Args:
        text (str): Raw assistant message content.
        session (dict): Active chat session (holds running slot_state).

    Returns:
        tuple: (clean_text, slot_state_dict)
    """
    # Default empty slot state
    default_state = {
        "trip_type": None,
        "origin": None,
        "start_date": None,
        "duration": None,
        "destination": None,
        "party_composition": None,
        "experience": None,
        "pace": None,
        "infrastructure": None,
    }

    if not text:
        return text, dict(default_state)

    # Match <slot_state>...</slot_state> block
    pattern = r"<slot_state>\s*(.+?)\s*</slot_state>"
    match = re.search(pattern, text, re.DOTALL)

    if not match:
        # The model skipped the <slot_state> block this turn. Preserve the
        # previously collected slots instead of wiping them to None (which
        # would break the progress bar and blocking logic in a multi-turn,
        # human-like conversation).
        prev = (session or {}).get("slot_state") or default_state
        return text, dict(prev)

    try:
        new_state = json.loads(match.group(1))
    except json.JSONDecodeError:
        new_state = {}

    # Merge: keep existing values, let the model override with non-null ones.
    prev = (session or {}).get("slot_state") or default_state
    merged = dict(prev)
    for key, val in new_state.items():
        if val is not None:
            merged[key] = val

    # Visible text = what the model wrote before the block. GPT-6 Luna sometimes
    # writes the reply, the block, and then the reply again in other words —
    # stripping only the block showed the user (and Sniffer) both versions.
    before = text[:match.start()]
    after = re.sub(pattern, "", text[match.end():], flags=re.DOTALL)
    before, after = before.strip(), after.strip()
    if before and after:
        print(f"[chat_handler] text after <slot_state> dropped: {after[:120]!r}")
    clean_text = before or after

    return clean_text, merged


def _slots_complete(slot_state):
    """
    Return True if all 5 hard slots have been filled.

    Args:
        slot_state (dict): Slot values dict.

    Returns:
        bool: True when all hard slots are non-null.
    """
    return all(
        slot_state.get(k) is not None
        for k in ("trip_type", "origin", "start_date", "duration", "destination")
    )


def _sanitize_messages_for_openai(messages):
    """
    Sanitize messages array to ensure strict OpenAI API contract:
    - Assistant messages with tool_calls must be followed by matching 'tool' role messages.
    - System messages and unfulfilled tool_calls are filtered/reordered cleanly.
    """
    sanitized = []
    i = 0
    while i < len(messages):
        msg = messages[i]
        if isinstance(msg, dict) and msg.get("role") == "assistant" and msg.get("tool_calls"):
            raw_tcs = msg.get("tool_calls", [])
            expected_ids = set()
            for tc in raw_tcs:
                if isinstance(tc, dict):
                    expected_ids.add(tc.get("id"))
                elif hasattr(tc, "id"):
                    expected_ids.add(getattr(tc, "id"))

            j = i + 1
            matching_tools = []
            system_notes = []
            while j < len(messages):
                next_msg = messages[j]
                if isinstance(next_msg, dict) and next_msg.get("role") == "tool" and next_msg.get("tool_call_id") in expected_ids:
                    matching_tools.append(next_msg)
                    j += 1
                elif isinstance(next_msg, dict) and next_msg.get("role") == "system":
                    system_notes.append(next_msg)
                    j += 1
                else:
                    break

            if len(matching_tools) == len(expected_ids) and len(expected_ids) > 0:
                sanitized.append(msg)
                sanitized.extend(matching_tools)
                sanitized.extend(system_notes)
                i = j
            else:
                # Omit orphan assistant tool_calls message that lacks tool responses
                i += 1
        else:
            sanitized.append(msg)
            i += 1
    return sanitized


MAX_TOOL_ROUNDS = 4


def _run_tool(session, tc, tool_calls):
    """Run one tool call from the model, record it in `tool_calls` and the history."""
    fn_name = tc.function.name
    
    try:
        fn_args = json.loads(tc.function.arguments)
    except json.JSONDecodeError:
        try:
            import ast
            # gpt-4o-mini sometimes outputs Python dict string instead of JSON
            # or adds trailing commas. ast.literal_eval can parse some of these.
            cleaned = tc.function.arguments.replace('true', 'True').replace('false', 'False').replace('null', 'None')
            fn_args = ast.literal_eval(cleaned)
        except Exception:
            print(f"  ⚠️ Failed to parse JSON or AST: {tc.function.arguments}")
            fn_args = {}

    print(f"  🔧 Tool call: {fn_name}({str(fn_args)[:100]}...)")

    # Inject active_trip_id into mutation tool calls if not provided
    if fn_name in ("modify_route", "add_attraction", "suggest_attractions", "edit_waypoint", "add_waypoint",
                   "set_overnight", "get_trip_summary"):
        if "trip_id" not in fn_args and session.get("active_trip_id"):
            fn_args["trip_id"] = session["active_trip_id"]

    # Inject user_id into plan_route / modify_route so the trip
    # gets persisted in the DB (AI doesn't know the logged-in user).
    if fn_name in ("plan_route", "modify_route", "add_waypoint"):
        if "user_id" not in fn_args and _real_user_id(session):
            fn_args["user_id"] = _real_user_id(session)

    # modify_route re-plans from the stored trip; an anonymous trip isn't stored,
    # so fill what the call leaves out from the trip planned in this conversation.
    # Only when the call changes something: filling these into a notes-only call
    # would make it look like a change and re-plan the same trip.
    if fn_name in ("modify_route", "add_waypoint") and session.get("last_plan"):
        if fn_name == "add_waypoint" or has_concrete_change(fn_args):
            for key, val in session["last_plan"].items():
                if key == "waypoints":
                    fn_args["_conversation_waypoints"] = val
                elif fn_args.get(key) is None and val is not None:
                    fn_args[key] = val

    # Dispatch to the appropriate tool
    tool_result = dispatch(fn_name, fn_args)
    if fn_name == "suggest_attractions" and tool_result.get("status") == "error" \
            and session.get("last_trip_rows"):
        # Trip not in the DB (anonymous / not saved): use the one from this chat.
        tool_result = dispatch(fn_name, {**fn_args, "schedules": session["last_trip_rows"]})
    tool_calls.append({
        "function_name": fn_name,
        "arguments": fn_args,
        "result": tool_result,
    })

    # Remember the trip's parameters for later modify_route calls.
    if fn_name in ("plan_route", "modify_route", "add_waypoint") \
            and tool_result.get("status") == "success" and tool_result.get("trip"):
        trip = tool_result.get("trip") or {}
        session["last_plan"] = {
            "waypoints": [
                {k: w.get(k) for k in ("label", "lat", "lng", "place_id", "emoji",
                                       "color", "category_label", "notes")}
                for d in tool_result.get("daily_schedules") or []
                for w in d.get("waypoints") or []
                if w.get("type") in ("attraction", "waypoint")
            ],
            "origin": trip.get("origin") or fn_args.get("origin"),
            "destination": trip.get("destination") or fn_args.get("destination"),
            "start_date": trip.get("start_date") or fn_args.get("start_date"),
            "num_days": tool_result.get("num_days") or fn_args.get("num_days"),
            **{k: fn_args.get(k) for k in (
                "round_trip", "stays", "rest_day_every", "overnight_stops",
                "overnight_preferences", "max_daily_km", "max_daily_drive_hours",
                "preferred_amenities")},
        }

    # Remember a compact view of the trip for get_trip_summary.
    if fn_name in ("plan_route", "modify_route", "add_waypoint", "set_overnight") \
            and tool_result.get("status") == "success" and tool_result.get("daily_schedules"):
        session["last_trip_summary"] = _compact_trip(tool_result)
        session["last_trip_rows"] = [
            (d.get("day_number"), d.get("waypoints") or [], d.get("route_polyline"))
            for d in tool_result["daily_schedules"]
        ]
    if fn_name == "get_trip_summary":
        if tool_result.get("status") == "success" and tool_result.get("daily_schedules"):
            tool_result = _compact_trip(tool_result)
        elif session.get("last_trip_summary"):
            tool_result = session["last_trip_summary"]
        tool_calls[-1]["result"] = tool_result

    # Persist the new trip_id when a route is planned or modified
    if fn_name in ("plan_route", "modify_route", "add_waypoint"):
        new_trip_id = (
            tool_result.get("trip", {}).get("id")
            or tool_result.get("trip_id")
        )
        if new_trip_id:
            session["active_trip_id"] = new_trip_id

    # MUST append tool response IMMEDIATELY after assistant's tool call for OpenAI contract
    session["history"].append({
        "role": "tool",
        "tool_call_id": tc.id,
        "name": fn_name,
        "content": json.dumps(_for_model(tool_result), default=str)
    })

    if fn_name == "plan_route" and tool_result.get("status") == "success":
        session["history"].append({
            "role": "system",
            "content": (
                "[SYSTEM NOTE] Route planned successfully. Describe it only from the tool result "
                "(days, overnight campsites). If the result has `warnings`, tell the user about "
                "them plainly. Then briefly ask whether to find 3-5 attractions on the way, "
                "asking first about their interests (e.g. castles, museums, nature). "
                "Reply in the user's interface language."
            )
        })


def _with_injections(session):
    """The history with this turn's system notes (language, date, trip) after the system prompt."""
    history = session["history"]
    injections = session.get("system_injections") or []
    if injections and history:
        return [history[0], *injections, *history[1:]]
    return history


def _fallback_text(tool_calls, lang="en"):
    """
    What to show when the model gives no text after its tools: say what actually happened,
    never claim a route was planned when it wasn't.
    """
    ok = {}
    errors = []
    for tc in tool_calls:
        res = tc.get("result") or {}
        if res.get("status") == "success":
            ok.setdefault(tc.get("function_name"), res)
        elif res.get("message"):
            errors.append(res["message"])
    route_tools = ("plan_route", "modify_route", "add_waypoint", "add_attraction", "edit_waypoint")
    if lang == "pl":
        if any(n in ok for n in route_tools):
            return "Trasa jest zaktualizowana: punkty i noclegi są na mapie i w kartach dni."
        if "set_overnight" in ok:
            return ok["set_overnight"].get("message") or "Nocleg został zmieniony."
        if "search_campings" in ok:
            n = ok["search_campings"].get("results_count") or len(ok["search_campings"].get("results") or [])
            return (f"Znalazłem {n} miejsc na nocleg — są na liście. Wybierz jedno i powiedz, "
                    "na którą noc je ustawić.")
        if errors:
            return "Nie udało się: " + errors[-1]
        return "Gotowe."
    if any(n in ok for n in route_tools):
        return "Your route is updated: all stops and campsites are on the map and in the day cards."
    if "set_overnight" in ok:
        return ok["set_overnight"].get("message") or "The overnight spot is changed."
    if "search_campings" in ok:
        n = ok["search_campings"].get("results_count") or len(ok["search_campings"].get("results") or [])
        return (f"I found {n} places to stay — they're in the list. Pick one and tell me which "
                "night to put it on.")
    if errors:
        return "That didn't work: " + errors[-1]
    return "Done."


def _process_response(session, response, trip_id):
    """
    Process OpenAI response, handling function calls if present.

    Args:
        session (dict): Active chat session.
        response: OpenAI API response.
        trip_id (str): Trip UUID.

    Returns:
        dict: Final response with text and tool results.
    """
    tool_calls = []
    lang = (session or {}).get("lang", "pl")

    message = response.choices[0].message
    
    # Check if response contains function calls
    if not message.tool_calls:
        # Text-only response — parse and strip slot_state block
        raw_text = message.content
        session["last_raw_reply"] = raw_text
        response_text, slot_state = _parse_slot_state(raw_text, session)

        # Store clean text (without slot_state block) in history
        session["history"].append({"role": "assistant", "content": response_text})

        user_id = _real_user_id(session)
        effective_trip_id = trip_id or session.get("trip_id") or session.get("active_trip_id")
        if user_id or _stored_trip(effective_trip_id):
            _store_message(user_id, effective_trip_id, "assistant", response_text)
        # Persist running slot_state on the session for the next turn.
        session["slot_state"] = slot_state
        return {
            "status": "success",
            "text": response_text,
            "tool_calls": [],
            "slot_state": slot_state,
            "slots_complete": _slots_complete(slot_state),
        }

    # Process function calls: run them, ask the model again, and repeat while it keeps
    # calling tools (e.g. search_campings, then set_overnight with a result), up to
    # MAX_TOOL_ROUNDS. Tool calls in a follow-up reply used to be dropped silently.
    session["history"].append(message.model_dump(exclude_unset=True))
    for tc in message.tool_calls:
        _run_tool(session, tc, tool_calls)

    return _finish_after_tools(session, tool_calls, trip_id)


def _finish_after_tools(session, tool_calls, trip_id):
    """
    After tools ran: ask the model again (running further tool calls, up to
    MAX_TOOL_ROUNDS), store and return its reply with the tool results.
    """
    lang = (session or {}).get("lang", "pl")
    # Get final text response from OpenAI
    try:
        final_kwargs = dict(
            model=MODEL_NAME,
            tools=session["tools"],
        )
        if REASONING_SUPPORTED:
            final_kwargs["reasoning_effort"] = "none"
        final_message = None
        for round_no in range(1, MAX_TOOL_ROUNDS + 1):
            final_kwargs["messages"] = _sanitize_messages_for_openai(_with_injections(session))
            if round_no == MAX_TOOL_ROUNDS:
                final_kwargs["tool_choice"] = "none"  # last round: text only
            final_response = session["client"].chat.completions.create(**final_kwargs)
            final_message = final_response.choices[0].message
            if not final_message.tool_calls or round_no == MAX_TOOL_ROUNDS:
                break
            session["history"].append(final_message.model_dump(exclude_unset=True))
            for tc in final_message.tool_calls:
                _run_tool(session, tc, tool_calls)
        final_text = final_message.content if final_message and final_message.content else None
        session["last_raw_reply"] = final_text

        if not final_text:
            final_text = _fallback_text(tool_calls, lang)

        session["history"].append({"role": "assistant", "content": final_text})

        # Store assistant response with tool calls
        user_id = _real_user_id(session)
        effective_trip_id = trip_id or session.get("trip_id") or session.get("active_trip_id")
        if user_id or _stored_trip(effective_trip_id):
            _store_message(
                user_id, effective_trip_id, "assistant", final_text,
                tool_calls=tool_calls,
            )

        # Parse slot_state from final text (usually all slots complete here)
        final_text, slot_state = _parse_slot_state(final_text, session)
        session["history"][-1]["content"] = final_text
        # Persist running slot_state on the session for the next turn.
        session["slot_state"] = slot_state

        return {
            "status": "success",
            "text": final_text,
            "tool_calls": tool_calls,
            "slot_state": slot_state,
            "slots_complete": _slots_complete(slot_state),
        }

    except Exception as e:
        # If final response fails, summarize tool results gracefully in user language
        if lang == 'de':
            summary = "Ergebnis deiner Anfrage:\n"
            for tc in tool_calls:
                fn = tc.get('function_name', '')
                if tc.get("result", {}).get("status") == "success":
                    summary += f"- {fn}: Erfolgreich ausgeführt\n"
                else:
                    summary += f"- {fn}: Fehler - {tc.get('result', {}).get('message', '')}\n"
        elif lang == 'en':
            summary = "Here's what was done:\n"
            for tc in tool_calls:
                fn = tc.get('function_name', '')
                if tc.get("result", {}).get("status") == "success":
                    summary += f"- {fn}: done\n"
                else:
                    summary += f"- {fn}: failed - {tc.get('result', {}).get('message', '')}\n"
        else:
            summary = "Oto podsumowanie wykonanych akcji:\n"
            for tc in tool_calls:
                fn = tc.get('function_name', '')
                if tc.get("result", {}).get("status") == "success":
                    summary += f"- {fn}: Trasa wyznaczona pomyślnie\n"
                else:
                    summary += f"- {fn}: Błąd - {tc.get('result', {}).get('message', '')}\n"
        
        session["history"].append({"role": "assistant", "content": summary})

        return {
            "status": "partial",
            "text": summary,
            "tool_calls": tool_calls,
            "slot_state": {
                "trip_type": None, "origin": None, "start_date": None,
                "duration": None, "destination": None,
                "party_composition": None, "experience": None,
                "pace": None, "infrastructure": None,
            },
            "slots_complete": False,
        }


def load_chat_history(user_id=None, trip_id=None):
    """
    Load chat history from the database for a user or trip.

    Returns:
        list: List of dicts formatted for OpenAI messages.
    """
    if not user_id and not trip_id:
        return []

    try:
        engine = get_engine()
        with engine.connect() as conn:
            query = "SELECT role, content FROM chat_messages WHERE "
            params = {}
            if trip_id:
                query += "trip_id = :trip_id "
                params["trip_id"] = trip_id
            elif user_id:
                query += "user_id = :user_id "
                params["user_id"] = user_id

            query += "ORDER BY created_at ASC"
            rows = conn.execute(text(query), params).fetchall()

            history = []
            for r in rows:
                if r[0] in ("user", "assistant"):
                    history.append({"role": r[0], "content": r[1]})

            return history
    except Exception as e:
        print(f"  ⚠️  Failed to load chat history: {e}")
        return []


def _stored_trip(trip_id):
    """True if the trip is saved in `trips` (anonymous trips are not, and storing a
    chat message that points at one breaks the trip_id foreign key)."""
    if not trip_id:
        return False
    try:
        with get_engine().connect() as conn:
            return conn.execute(
                text("SELECT 1 FROM trips WHERE id = :id"), {"id": trip_id}
            ).first() is not None
    except Exception:
        return False


def _store_message(arg1, arg2, arg3, arg4=None, tool_calls=None):
    """
    Store a chat message in the database.
    Supports flexible signature:
      _store_message(user_id, trip_id, role, content, tool_calls=None)
      _store_message(trip_id, role, content, tool_calls=None)
    """
    if arg4 is not None:
        user_id, trip_id, role, content = arg1, arg2, arg3, arg4
    else:
        user_id, trip_id, role, content = None, arg1, arg2, arg3

    if not user_id and not trip_id:
        return

    try:
        engine = get_engine()
        with engine.connect() as conn:
            conn.execute(
                text("""
                    INSERT INTO chat_messages
                        (id, user_id, trip_id, role, content, tool_calls)
                    VALUES
                        (:id, :user_id, :trip_id, :role, :content,
                         CAST(:tool_calls AS jsonb))
                """),
                {
                    "id": str(uuid.uuid4()),
                    "user_id": user_id,
                    "trip_id": trip_id,
                    "role": role,
                    "content": content,
                    "tool_calls": json.dumps(
                        tool_calls or [], default=str
                    ),
                },
            )
            conn.commit()
    except Exception as e:
        # Non-critical — log but don't fail
        print(f"  ⚠️  Failed to store message: {e}")

if __name__ == "__main__":
    # Interactive chat demo
    print("🚐 VW California Trip Planner — Chat Demo")
    print("=" * 55)
    print("Type your trip planning questions below.")
    print("Type 'quit' to exit.\n")

    session = create_chat_session()

    while True:
        try:
            user_input = input("You: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\n\nGoodbye! 🚐")
            break

        if user_input.lower() in ("quit", "exit", "q"):
            print("\nGoodbye! 🚐")
            break

        if not user_input:
            continue

        result = send_message(session, user_input)
        print(f"\nAssistant: {result['text']}\n")


def send_form(session, form, user_location=None):
    """
    Plan the first route from the start form (Direct / Point-to-point / Turnaround).

    The form is turned into plan_route arguments without asking the model, so the first
    route doesn't depend on free text being understood. The conversation then looks as if
    the user had asked for it and the model had called plan_route: a user message with the
    form summary, the tool call and its result; the model only describes the route.
    Later chat messages change this trip like any other.
    """
    from types import SimpleNamespace
    from navigation.plan_form import form_to_plan_args, FormError

    started = time.monotonic()
    try:
        args, summary = form_to_plan_args(form)
    except FormError as e:
        return {"status": "error", "text": str(e), "message": str(e), "tool_calls": []}

    # A new trip: the planner gets the logged-in user so it is saved.
    session["active_trip_id"] = None
    user_id = _real_user_id(session)
    if user_id:
        args["user_id"] = user_id
        _store_message(user_id, None, "user", summary)
    session["history"].append({"role": "user", "content": summary})

    try:
        session["system_injections"] = _build_system_injections(session, summary, user_location)
        call = SimpleNamespace(
            id=f"call_form_{uuid.uuid4().hex[:12]}",
            type="function",
            function=SimpleNamespace(name="plan_route", arguments=json.dumps(args, default=str)),
        )
        session["history"].append({
            "role": "assistant", "content": None,
            "tool_calls": [{"id": call.id, "type": "function",
                            "function": {"name": "plan_route", "arguments": call.function.arguments}}],
        })
        tool_calls = []
        _run_tool(session, call, tool_calls)
        result = _finish_after_tools(session, tool_calls, session.get("active_trip_id"))
    except Exception as e:
        import traceback
        traceback.print_exc()
        result = {"status": "error", "tool_calls": [],
                  "text": "Sorry, the route could not be planned right now. Please try again.",
                  "message": f"{type(e).__name__}: {e}"}
    result["summary"] = summary
    log_chat_turn(session.get("user_id"), session.get("lang"), MODEL_NAME, "[form] " + summary,
                  result, time.monotonic() - started,
                  active_trip_id=session.get("active_trip_id"),
                  raw_reply=session.pop("last_raw_reply", None))
    return result

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
)
from tools.interaction_logger import log_interaction


def create_chat_session(user_id=None, trip_id=None, lang="pl"):
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
    saved_history = load_chat_history(user_id=user_id, trip_id=trip_id)
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


def send_message(session, user_message, trip_id=None):
    """
    Send a user message, process any function calls,
    and return the final assistant response.

    Args:
        session (dict): Chat session from create_chat_session.
        user_message (str): The user's natural language input.
        trip_id (str): Trip UUID for storing chat messages.

    Returns:
        dict: Response with assistant text and any tool results.
    """
    effective_trip_id = trip_id or session.get("trip_id") or session.get("active_trip_id")
    user_id = session.get("user_id")

    # Store user message in DB
    if user_id or effective_trip_id:
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
        system_injections = []

        # Add language context injection
        lang = session.get("lang", "pl")
        if lang == "de":
            lang_context = (
                "[SYSTEM NOTE] User interface language is set to German (de). "
                "Respond in German. Maintain the VW California vanlife companion tone."
            )
            system_injections.append({"role": "system", "content": lang_context})

        active_trip_id = session.get("active_trip_id")
        if active_trip_id:
            # Insert a system reminder right after the main system prompt
            trip_context = (
                f"[SYSTEM NOTE] Active trip ID: {active_trip_id}. "
                "A route is already planned. The user may now request modifications. "
                "Use modify_route or add_attraction tools — do NOT re-ask for trip parameters."
            )
            system_injections.append({"role": "system", "content": trip_context})

        user_id = session.get("user_id")
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

        return result

    except Exception as e:
        import traceback
        print(f"❌ ERROR IN send_message: {e}")
        traceback.print_exc()

        lang = (session or {}).get("lang", "pl")
        if lang == "de":
            error_msg = "Entschuldigung, es gab ein vorübergehendes Problem. Bitte versuche es noch einmal."
        else:
            error_msg = "Przepraszam, wystąpił chwilowy problem z połączeniem lub przetworzeniem trasy. Spróbuj powtórzyć zapytanie."

        log_interaction(user_message, error_msg)

        return {
            "status": "error",
            "message": error_msg,
            "text": error_msg,
            "tool_calls": [],
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

    clean_text = text

    # Strip the block from visible text and trim whitespace
    clean_text = re.sub(pattern, "", text, flags=re.DOTALL).strip()

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
        response_text, slot_state = _parse_slot_state(raw_text)

        # Store clean text (without slot_state block) in history
        session["history"].append({"role": "assistant", "content": response_text})

        user_id = session.get("user_id")
        effective_trip_id = trip_id or session.get("trip_id") or session.get("active_trip_id")
        if user_id or effective_trip_id:
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

    # Process function calls
    # Add model's response to history
    session["history"].append(message.model_dump(exclude_unset=True))

    for tc in message.tool_calls:
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
        if fn_name in ("modify_route", "add_attraction", "suggest_attractions", "edit_waypoint"):
            if "trip_id" not in fn_args and session.get("active_trip_id"):
                fn_args["trip_id"] = session["active_trip_id"]

        # Inject user_id into plan_route / modify_route so the trip
        # gets persisted in the DB (AI doesn't know the logged-in user).
        if fn_name in ("plan_route", "modify_route"):
            if "user_id" not in fn_args and session.get("user_id"):
                fn_args["user_id"] = session["user_id"]

        # Dispatch to the appropriate tool
        tool_result = dispatch(fn_name, fn_args)
        tool_calls.append({
            "function_name": fn_name,
            "arguments": fn_args,
            "result": tool_result,
        })

        # Persist the new trip_id when a route is planned or modified
        if fn_name in ("plan_route", "modify_route"):
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
            "content": json.dumps(tool_result, default=str)
        })

        if fn_name == "plan_route" and tool_result.get("status") == "success":
            session["history"].append({
                "role": "system",
                "content": "[SYSTEM NOTE] Route planned successfully. Krótko zapytaj użytkownika czy chce, żebym wyszukał mu 3-5 atrakcji po drodze, pytając najpierw o jego preferencje (np. zamki, muzea, natura)."
            })

    # Get final text response from OpenAI
    try:
        sanitized_history = _sanitize_messages_for_openai(session["history"])
        final_kwargs = dict(
            model=MODEL_NAME,
            messages=sanitized_history,
            tools=session["tools"],
        )
        if REASONING_SUPPORTED:
            final_kwargs["reasoning_effort"] = "none"
        final_response = session["client"].chat.completions.create(**final_kwargs)
        final_message = final_response.choices[0].message
        final_text = final_message.content if final_message and final_message.content else None

        if not final_text:
            if lang == 'de':
                final_text = "Hier ist deine geplante Route! Alle Wegpunkte und empfohlenen Campingplätze wurden auf der Karte hinzugefügt. Du kannst die Details auf der Karte einsehen."
            else:
                final_text = "Oto Twoja zaplanowana trasa! Wszystkie punkty trasy oraz rekomendowane kempingi zostały pomyślnie wyznaczone. Przejdź do zakładki Mapa lub sprawdź kartę podsumowania poniżej."

        session["history"].append({"role": "assistant", "content": final_text})

        # Store assistant response with tool calls
        user_id = session.get("user_id")
        effective_trip_id = trip_id or session.get("trip_id") or session.get("active_trip_id")
        if user_id or effective_trip_id:
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

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

from tools.openai_client import get_client, SYSTEM_PROMPT, MODEL_NAME
from tools.db import get_engine
from navigation.dispatcher import (
    dispatch,
    OPENAI_TOOL_DEFINITIONS,
)


def create_chat_session(trip_id=None):
    """
    Create a new chat session with OpenAI, configured with
    VW trip planning tools.

    Args:
        trip_id (str): Optional trip UUID for context.

    Returns:
        dict: Session info with client and config.
    """
    client = get_client()
    tools = OPENAI_TOOL_DEFINITIONS

    # Initialize history with system prompt
    history = [
        {"role": "system", "content": SYSTEM_PROMPT}
    ]

    return {
        "client": client,
        "tools": tools,
        "trip_id": trip_id,
        "history": history,
        # Tracks the most recently planned trip — enables POST-PLANNING MODE
        "active_trip_id": None,
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
    effective_trip_id = trip_id or session.get("trip_id")

    # Store user message
    if effective_trip_id:
        _store_message(effective_trip_id, "user", user_message)

    # Append user message to history
    session["history"].append(
        {"role": "user", "content": user_message}
    )

    try:
        client = session["client"]

        # Inject active trip context into a temporary system injection
        # so the AI knows a route already exists and enters POST-PLANNING MODE.
        messages_to_send = list(session["history"])
        active_trip_id = session.get("active_trip_id")
        if active_trip_id:
            # Insert a system reminder right after the main system prompt
            trip_context = (
                f"[SYSTEM NOTE] Active trip ID: {active_trip_id}. "
                "A route is already planned. The user may now request modifications. "
                "Use modify_route or add_attraction tools — do NOT re-ask for trip parameters."
            )
            messages_to_send = [
                messages_to_send[0],
                {"role": "system", "content": trip_context},
                *messages_to_send[1:],
            ]

        # Send to OpenAI with tools
        response = client.chat.completions.create(
            model=MODEL_NAME,
            messages=messages_to_send,
            tools=session["tools"],
        )

        # Process the response
        result = _process_response(
            session, response, effective_trip_id
        )

        return result

    except Exception as e:
        error_msg = (
            "I'm having trouble connecting right now. "
            f"Please try again in a moment. (Error: {e})"
        )
        return {
            "status": "error",
            "text": error_msg,
            "tool_calls": [],
        }


def _parse_slot_state(text):
    """
    Extract the <slot_state> JSON block from the AI response text.

    The AI appends a machine-readable slot_state block after its
    conversational reply. This function parses it and strips it
    from the visible message.

    Args:
        text (str): Raw assistant message content.

    Returns:
        tuple: (clean_text, slot_state_dict)
    """
    # Default empty slot state
    default_state = {
        "vibe": None,
        "experience": None,
        "pace": None,
        "infrastructure": None,
        "duration": None,
    }

    if not text:
        return text, default_state

    # Match <slot_state>...</slot_state> block
    pattern = r"<slot_state>\s*(.+?)\s*</slot_state>"
    match = re.search(pattern, text, re.DOTALL)

    if not match:
        return text, default_state

    try:
        slot_state = json.loads(match.group(1))
    except json.JSONDecodeError:
        slot_state = default_state

    # Strip the block from visible text and trim whitespace
    clean_text = re.sub(pattern, "", text, flags=re.DOTALL).strip()

    return clean_text, slot_state


def _slots_complete(slot_state):
    """
    Return True if all 5 required slots have been filled.

    Args:
        slot_state (dict): Slot values dict.

    Returns:
        bool: True when all slots are non-null.
    """
    return all(
        slot_state.get(k) is not None
        for k in ("vibe", "experience", "pace", "infrastructure", "duration")
    )


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

    message = response.choices[0].message
    
    # Check if response contains function calls
    if not message.tool_calls:
        # Text-only response — parse and strip slot_state block
        raw_text = message.content
        response_text, slot_state = _parse_slot_state(raw_text)

        # Store clean text (without slot_state block) in history
        session["history"].append({"role": "assistant", "content": response_text})

        if trip_id:
            _store_message(trip_id, "assistant", response_text)
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
        if fn_name in ("modify_route", "add_attraction"):
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

        # Build function response for OpenAI
        session["history"].append({
            "role": "tool",
            "tool_call_id": tc.id,
            "name": fn_name,
            "content": json.dumps(tool_result, default=str)
        })

    # Get final text response from OpenAI
    try:
        final_response = session["client"].chat.completions.create(
            model=MODEL_NAME,
            messages=session["history"],
            tools=session["tools"],
        )

        final_message = final_response.choices[0].message
        final_text = final_message.content
        session["history"].append({"role": "assistant", "content": final_text})

        # Store assistant response with tool calls
        if trip_id:
            _store_message(
                trip_id, "assistant", final_text,
                tool_calls=tool_calls,
            )

        # Parse slot_state from final text (usually all slots complete here)
        final_text, slot_state = _parse_slot_state(final_text)
        session["history"][-1]["content"] = final_text

        return {
            "status": "success",
            "text": final_text,
            "tool_calls": tool_calls,
            "slot_state": slot_state,
            "slots_complete": _slots_complete(slot_state),
        }

    except Exception as e:
        # If final response fails, summarize tool results
        summary = "Here's what I found:\n"
        for tc in tool_calls:
            summary += f"- {tc['function_name']}: "
            if tc["result"].get("status") == "success":
                summary += "completed successfully\n"
            else:
                summary += (
                    f"error - {tc['result'].get('message', '')}\n"
                )
        
        session["history"].append({"role": "assistant", "content": summary})

        return {
            "status": "partial",
            "text": summary,
            "tool_calls": tool_calls,
            "slot_state": {
                "vibe": None, "experience": None,
                "pace": None, "infrastructure": None, "duration": None,
            },
            "slots_complete": False,
        }


def _store_message(trip_id, role, content, tool_calls=None):
    """
    Store a chat message in the database.

    Args:
        trip_id (str): Trip UUID.
        role (str): Message role (user/assistant/system).
        content (str): Message text content.
        tool_calls (list): Optional tool call records.
    """
    try:
        engine = get_engine()
        with engine.connect() as conn:
            conn.execute(
                text("""
                    INSERT INTO chat_messages
                        (id, trip_id, role, content, tool_calls)
                    VALUES
                        (:id, :trip_id, :role, :content,
                         :tool_calls::jsonb)
                """),
                {
                    "id": str(uuid.uuid4()),
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

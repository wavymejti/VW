"""
OpenAI chat handler for the VW California AI Trip Planner.

Manages the conversational flow between the user and the
OpenAI model, dispatching function calls to tools via
the dispatcher.

See: architecture/chat_orchestration_sop.md
"""

import json
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

        # Send to OpenAI with tools
        response = client.chat.completions.create(
            model=MODEL_NAME,
            messages=session["history"],
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
        # Text-only response
        response_text = message.content
        session["history"].append({"role": "assistant", "content": response_text})

        if trip_id:
            _store_message(trip_id, "assistant", response_text)
        return {
            "status": "success",
            "text": response_text,
            "tool_calls": [],
        }

    # Process function calls
    # Add model's response to history
    session["history"].append(message.model_dump(exclude_unset=True))

    for tc in message.tool_calls:
        fn_name = tc.function.name
        
        try:
            fn_args = json.loads(tc.function.arguments)
        except json.JSONDecodeError:
            fn_args = {}

        print(f"  🔧 Tool call: {fn_name}({str(fn_args)[:100]}...)")

        # Dispatch to the appropriate tool
        tool_result = dispatch(fn_name, fn_args)
        tool_calls.append({
            "function_name": fn_name,
            "arguments": fn_args,
            "result": tool_result,
        })

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

        return {
            "status": "success",
            "text": final_text,
            "tool_calls": tool_calls,
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

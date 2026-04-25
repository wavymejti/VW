"""
Integration tests for the navigation/orchestration layer.

Tests the dispatcher and chat handler working together
with the tools layer.

Tests:
- Dispatcher routing to correct tools
- Unknown function handling
- Chat session creation
- Message sending and response structure
"""

import pytest
from navigation.dispatcher import dispatch, TOOL_REGISTRY
from navigation.chat_handler import create_chat_session, send_message


class TestDispatcher:
    """Tests for the intent dispatcher."""

    def test_registry_has_expected_tools(self):
        """Tool registry should contain all core tools."""
        assert "search_campings" in TOOL_REGISTRY
        assert "plan_route" in TOOL_REGISTRY
        assert "upload_photos" in TOOL_REGISTRY

    def test_dispatch_search_campings(self):
        """Dispatching search_campings should call the tool."""
        result = dispatch(
            "search_campings",
            {"lat": 46.36, "lng": 14.09, "radius_km": 50},
        )
        assert result["status"] == "success"
        assert "results" in result

    def test_dispatch_unknown_function(self):
        """Unknown function should return error."""
        result = dispatch("nonexistent_tool", {})
        assert result["status"] == "error"
        assert "Unknown function" in result["message"]

    def test_dispatch_bad_arguments(self):
        """Bad arguments should return error, not crash."""
        result = dispatch(
            "search_campings",
            {"invalid_param": "value"},
        )
        # Should get an error about bad arguments
        assert result["status"] == "error"

    def test_dispatch_search_with_amenities(self):
        """Dispatching with amenity filters should work."""
        result = dispatch(
            "search_campings",
            {
                "lat": 46.36,
                "lng": 14.09,
                "amenities": ["power", "showers"],
                "vw_compatible": True,
            },
        )
        assert result["status"] == "success"


class TestChatHandler:
    """Tests for the chat handler."""

    def test_create_session(self):
        """Session should be created with required fields."""
        session = create_chat_session()
        assert "client" in session
        assert "tools" in session
        assert "history" in session
        assert isinstance(session["history"], list)

    def test_send_message_returns_response(self):
        """Sending a message should return a response dict."""
        session = create_chat_session()
        result = send_message(session, "Hello, what can you do?")

        assert "status" in result
        assert "text" in result
        assert result["text"]  # Should not be empty
        assert result["status"] in (
            "success", "partial", "error"
        )

    def test_send_message_with_tool_trigger(self):
        """Asking about campings should trigger a tool call."""
        session = create_chat_session()
        result = send_message(
            session,
            "Find campgrounds with power near Lake Bled, "
            "Slovenia (lat 46.36, lng 14.09)",
        )

        assert "status" in result
        assert "text" in result
        # The AI should have responded with camping info
        assert len(result["text"]) > 0

import pytest
from unittest.mock import patch, MagicMock
from navigation.chat_handler import send_message, _process_response, _store_message, create_chat_session


class TestChatHandlerExtended:
    @patch("navigation.chat_handler._store_message")
    def test_send_message_api_down(self, mock_store):
        session = create_chat_session(trip_id="test-trip")
        
        mock_client = MagicMock()
        mock_client.chat.completions.create.side_effect = Exception("API limit reached")
        
        session["client"] = mock_client
        
        result = send_message(session, "Hello")
        assert result["status"] == "error"
        assert "trouble connecting" in result["text"]
        
        # User message was stored before failure
        mock_store.assert_called_once_with("test-trip", "user", "Hello")

    @patch("navigation.chat_handler._store_message")
    @patch("navigation.chat_handler.dispatch")
    def test_process_response_final_error(self, mock_dispatch, mock_store):
        session = create_chat_session()
        
        # We need a response with a function call
        mock_tc = MagicMock()
        mock_tc.id = "call_123"
        mock_tc.function.name = "search_campings"
        mock_tc.function.arguments = "{}"
        
        mock_message = MagicMock()
        mock_message.tool_calls = [mock_tc]
        # mock_dump must be provided for message.model_dump()
        mock_message.model_dump.return_value = {"role": "assistant", "tool_calls": [{"id": "call_123", "type": "function", "function": {"name": "search_campings", "arguments": "{}"}}]}
        
        mock_response = MagicMock()
        mock_response.choices = [MagicMock(message=mock_message)]
        
        mock_dispatch.return_value = {"status": "success"}
        
        # Setup the client to fail on the SECOND call (final response)
        mock_client = MagicMock()
        mock_client.chat.completions.create.side_effect = Exception("Second try failed")
        session["client"] = mock_client
        
        result = _process_response(session, mock_response, trip_id="trip-1")
        assert result["status"] == "partial"
        assert "Here's what I found" in result["text"]
        
        # Check tool was logged in summary
        assert "search_campings: completed successfully" in result["text"]

    @patch("navigation.chat_handler.get_engine")
    def test_store_message_db_exception(self, mock_engine):
        mock_engine.side_effect = Exception("DB Connection closed")
        # Should not crash
        _store_message("t1", "user", "hi")

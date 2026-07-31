"""
Unit tests for Chat Memory Persistence in VW California AI Trip Planner.
Tests storing, retrieving, and restoring chat message history from PostgreSQL.
"""

import unittest
import uuid
from unittest.mock import patch, MagicMock
from navigation.chat_handler import _store_message, load_chat_history, create_chat_session


class TestChatMemoryPersistence(unittest.TestCase):
    def setUp(self):
        self.user_id = str(uuid.uuid4())
        self.trip_id = str(uuid.uuid4())

    @patch("navigation.chat_handler.get_engine")
    def test_store_and_load_chat_history(self, mock_get_engine):
        mock_engine = MagicMock()
        mock_conn = MagicMock()
        mock_get_engine.return_value = mock_engine
        mock_engine.connect.return_value.__enter__.return_value = mock_conn

        # Mock DB select result for load_chat_history
        mock_conn.execute.return_value.fetchall.return_value = [
            ("user", "Chcę pojechać w góry na 5 dni."),
            ("assistant", "Jasne! Przygotowuję plan 5-dniowej trasy w góry.")
        ]

        history = load_chat_history(user_id=self.user_id, trip_id=self.trip_id)

        self.assertEqual(len(history), 2)
        self.assertEqual(history[0]["role"], "user")
        self.assertEqual(history[0]["content"], "Chcę pojechać w góry na 5 dni.")
        self.assertEqual(history[1]["role"], "assistant")

    @patch("navigation.chat_handler.load_chat_history")
    @patch("navigation.chat_handler.get_client")
    def test_create_session_restores_chat_memory(self, mock_get_client, mock_load_chat_history):
        mock_load_chat_history.return_value = [
            {"role": "user", "content": "Witaj, planujemy wyjazd."},
            {"role": "assistant", "content": "Cześć! Dokąd zmierzamy?"}
        ]

        session = create_chat_session(user_id=self.user_id, trip_id=self.trip_id)

        # System prompt + 2 restored messages = 3 items in history
        self.assertEqual(len(session["history"]), 3)
        self.assertEqual(session["history"][1]["content"], "Witaj, planujemy wyjazd.")
        self.assertEqual(session["history"][2]["content"], "Cześć! Dokąd zmierzamy?")


if __name__ == "__main__":
    unittest.main()

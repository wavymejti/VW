"""
Unit and integration tests for Personalized User Memory (RAG) system.

Tests vector cosine similarity, database storage/retrieval, deduplication,
prompt formatting, API endpoints, and chat handler context injection.
"""

import json
import uuid
from unittest.mock import patch, MagicMock
import pytest

from tools.user_memory import (
    cosine_similarity,
    format_memories_for_prompt,
    save_user_memory,
    get_relevant_user_memories,
    list_user_memories,
    delete_user_memory,
    DEFAULT_SIMILARITY_THRESHOLD,
    DEDUPLICATION_THRESHOLD,
)
from tools.server import app


# --- 1. Math & Similarity Tests ---

def test_cosine_similarity_identical():
    """Verify that identical vectors yield similarity 1.0."""
    v1 = [1.0, 2.0, 3.0]
    v2 = [1.0, 2.0, 3.0]
    sim = cosine_similarity(v1, v2)
    assert pytest.approx(sim, 0.0001) == 1.0


def test_cosine_similarity_orthogonal():
    """Verify that orthogonal vectors yield similarity 0.0."""
    v1 = [1.0, 0.0]
    v2 = [0.0, 1.0]
    sim = cosine_similarity(v1, v2)
    assert pytest.approx(sim, 0.0001) == 0.0


def test_cosine_similarity_opposite():
    """Verify that opposite vectors yield similarity -1.0."""
    v1 = [1.0, 0.0]
    v2 = [-1.0, 0.0]
    sim = cosine_similarity(v1, v2)
    assert pytest.approx(sim, 0.0001) == -1.0


def test_cosine_similarity_empty_or_zero():
    """Verify safe fallback for empty or zero vectors."""
    assert cosine_similarity([], []) == 0.0
    assert cosine_similarity([0.0, 0.0], [1.0, 2.0]) == 0.0
    assert cosine_similarity([1.0], [1.0, 2.0]) == 0.0


# --- 2. Prompt Formatting Tests ---

def test_format_memories_for_prompt_empty():
    """Verify that empty memory list returns empty string."""
    assert format_memories_for_prompt([]) == ""


def test_format_memories_for_prompt_with_items():
    """Verify that memories are formatted into structured system notes."""
    sample = [
        {"category": "pets", "polarity": "constraint", "content": "Podróżuje z psem."},
        {"category": "camping_style", "polarity": "like", "content": "Lubi jeziora."},
        {"category": "dislikes", "polarity": "dislike", "content": "Unika autostrad."},
    ]
    formatted = format_memories_for_prompt(sample)
    assert "[SYSTEM NOTE]" in formatted
    assert "[Ograniczenie/Warunek] Podróżuje z psem." in formatted
    assert "[Upodobanie] Lubi jeziora." in formatted
    assert "[Czego unika] Unika autostrad." in formatted


# --- 3. Retrieval & Storage Tests (Mocked DB & Embeddings) ---

@patch("tools.user_memory.get_engine")
@patch("tools.user_memory.get_embedding")
def test_get_relevant_user_memories_ranking(mock_embed, mock_engine):
    """Verify semantic ranking and filtering by threshold."""
    # Query vector points along X axis
    mock_embed.return_value = [1.0, 0.0, 0.0]

    # Mock DB rows: mem_id, category, polarity, content, emb_json, conf
    mock_rows = [
        # Highly aligned with X axis (sim ~ 0.96)
        ("m1", "camping_style", "like", "Spokojne kempingi", [0.96, 0.28, 0.0], 1.0),
        # Moderately aligned (sim ~ 0.6)
        ("m2", "pets", "constraint", "Pies na pokładzie", [0.6, 0.8, 0.0], 1.0),
        # Orthogonal to X axis (sim = 0.0) -> should be filtered out by threshold
        ("m3", "activities", "like", "Wspinaczka", [0.0, 1.0, 0.0], 1.0),
    ]

    mock_conn = MagicMock()
    mock_conn.execute.return_value.fetchall.return_value = mock_rows
    mock_engine.return_value.connect.return_value.__enter__.return_value = mock_conn

    results = get_relevant_user_memories("user-123", "Szukam kempingu", limit=5, threshold=0.5)

    assert len(results) == 2
    assert results[0]["id"] == "m1"
    assert results[0]["similarity"] > results[1]["similarity"]
    assert results[1]["id"] == "m2"


@patch("tools.user_memory.get_engine")
@patch("tools.user_memory.get_embedding")
def test_save_user_memory_deduplication(mock_embed, mock_engine):
    """Verify that saving a memory similar to an existing one updates it."""
    # Same or almost identical embedding
    mock_embed.return_value = [1.0, 0.0, 0.0]

    existing_rows = [
        ("mem-existing", "pets", "like", "Lubi psy", [0.99, 0.05, 0.0]),
    ]

    mock_conn = MagicMock()
    mock_conn.execute.return_value.fetchall.return_value = existing_rows
    mock_engine.return_value.begin.return_value.__enter__.return_value = mock_conn

    res = save_user_memory("user-123", "Uwielbia podróże z psem", category="pets", polarity="like")

    assert res["action"] == "updated"
    assert res["id"] == "mem-existing"


# --- 4. Flask API Endpoints Tests ---

def test_api_user_memories_unauthorized():
    """Verify /api/user_memories returns 401 when not logged in."""
    client = app.test_client()
    res = client.get("/api/user_memories")
    assert res.status_code == 401


@patch("tools.server.list_user_memories")
def test_api_get_user_memories_authorized(mock_list):
    """Verify /api/user_memories returns memories for authenticated user."""
    mock_list.return_value = [
        {"id": "m1", "category": "pets", "polarity": "like", "content": "Pies"}
    ]
    client = app.test_client()
    with client.session_transaction() as sess:
        sess["user_id"] = "test-user-uuid"

    res = client.get("/api/user_memories")
    assert res.status_code == 200
    data = res.get_json()
    assert data["status"] == "success"
    assert len(data["memories"]) == 1


@patch("tools.server.delete_user_memory")
def test_api_delete_user_memory(mock_delete):
    """Verify DELETE /api/user_memories/<id> handles success and not found."""
    mock_delete.return_value = True
    client = app.test_client()
    with client.session_transaction() as sess:
        sess["user_id"] = "test-user-uuid"

    res = client.delete("/api/user_memories/test-id")
    assert res.status_code == 200
    assert res.get_json()["status"] == "success"

    mock_delete.return_value = False
    res2 = client.delete("/api/user_memories/unknown-id")
    assert res2.status_code == 404


# --- 5. Chat Handler Integration Test ---

@patch("navigation.chat_handler.get_client")
@patch("navigation.chat_handler.get_relevant_user_memories")
@patch("navigation.chat_handler.get_engine")
def test_chat_handler_memory_injection(mock_engine, mock_memories, mock_client):
    """Verify that chat_handler injects user memories into OpenAI messages."""
    from navigation.chat_handler import create_chat_session, send_message

    # Mock user memory retrieval
    mock_memories.return_value = [
        {"category": "pets", "polarity": "constraint", "content": "Podróżuje z psem."}
    ]

    # Mock DB engine for user preferences
    mock_conn = MagicMock()
    mock_conn.execute.return_value.scalar.return_value = {}
    mock_engine.return_value.connect.return_value.__enter__.return_value = mock_conn

    # Mock OpenAI API client
    mock_openai = MagicMock()
    mock_response = MagicMock()
    mock_choice = MagicMock()
    mock_choice.message.content = "Jasne, zaplanuję trasę przyjazną dla psa! <slot_state>{}</slot_state>"
    mock_choice.message.tool_calls = None
    mock_response.choices = [mock_choice]
    mock_openai.chat.completions.create.return_value = mock_response
    mock_client.return_value = mock_openai

    session = create_chat_session(user_id="user-xyz")
    with patch("navigation.chat_handler._store_message"):
        result = send_message(session, "Szukam kempingu w górach")

    assert "przyjazną dla psa" in result["text"]

    # Verify that the system note with memory was injected into messages
    call_args = mock_openai.chat.completions.create.call_args[1]
    messages_sent = call_args["messages"]

    memory_injected = any(
        m["role"] == "system" and "Podróżuje z psem." in m["content"]
        for m in messages_sent
    )
    assert memory_injected is True, "Expected user memory to be injected into system prompt"



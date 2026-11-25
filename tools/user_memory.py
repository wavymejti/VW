"""
User Memory & Personalized RAG module for VW California AI Trip Planner.

Provides storage, semantic retrieval, and extraction of long-term user
preferences, vehicle constraints, and travel habits using OpenAI embeddings
and PostgreSQL.
"""

import json
import math
import uuid
from typing import Any, Dict, List, Optional
from sqlalchemy import text

from tools.db import get_engine
from tools.openai_client import get_client, MODEL_NAME, chat_kwargs


# Default embedding model (1536 dimensions, highly cost-effective)
EMBEDDING_MODEL = "text-embedding-3-small"

# Default similarity threshold for injecting memories into chat context
DEFAULT_SIMILARITY_THRESHOLD = 0.45

# Threshold above which a new memory is considered a duplicate of an existing one
DEDUPLICATION_THRESHOLD = 0.85


def get_embedding(input_text: str) -> List[float]:
    """
    Generate a normalized embedding vector for the provided text using OpenAI.

    Args:
        input_text (str): Natural language text to embed.

    Returns:
        List[float]: 1536-dimensional unit vector.
    """
    clean_text = input_text.strip().replace("\n", " ")
    if not clean_text:
        return [0.0] * 1536

    client = get_client()
    response = client.embeddings.create(
        model=EMBEDDING_MODEL,
        input=clean_text,
    )
    return response.data[0].embedding


def cosine_similarity(v1: List[float], v2: List[float]) -> float:
    """
    Compute cosine similarity between two float vectors.

    Since OpenAI embeddings are pre-normalized to unit length (L2 norm = 1),
    the cosine similarity is equal to their dot product. We include a safe
    fallback norm check to handle any non-normalized or arbitrary vectors.

    Args:
        v1 (List[float]): First vector.
        v2 (List[float]): Second vector.

    Returns:
        float: Cosine similarity score between -1.0 and 1.0.
    """
    if not v1 or not v2 or len(v1) != len(v2):
        return 0.0

    dot_product = sum(a * b for a, b in zip(v1, v2))
    norm_v1 = math.sqrt(sum(a * a for a, b in zip(v1, v1)))
    norm_v2 = math.sqrt(sum(b * b for a, b in zip(v2, v2)))

    if norm_v1 == 0.0 or norm_v2 == 0.0:
        return 0.0

    return dot_product / (norm_v1 * norm_v2)


def save_user_memory(
    user_id: str,
    content: str,
    category: str = "general",
    polarity: str = "like",
    confidence: float = 1.0,
    embedding: Optional[List[float]] = None,
) -> Dict[str, Any]:
    """
    Store or update a user preference memory in PostgreSQL.

    If a semantically similar memory (> DEDUPLICATION_THRESHOLD) already exists
    for this user, the existing memory is updated in place.

    Args:
        user_id (str): UUID of the user.
        content (str): Natural language fact/preference statement.
        category (str): Category (e.g. 'camping_style', 'activities', 'pets', 'vehicle').
        polarity (str): 'like', 'dislike', 'constraint', or 'habit'.
        confidence (float): Confidence score between 0.0 and 1.0.
        embedding (List[float], optional): Precomputed embedding vector.

    Returns:
        Dict[str, Any]: Dictionary representation of the saved memory record.
    """
    if not user_id or not content.strip():
        raise ValueError("user_id and non-empty content are required.")

    vector = embedding if embedding is not None else get_embedding(content)
    engine = get_engine()

    with engine.begin() as conn:
        # Check existing active memories for deduplication
        existing_rows = conn.execute(
            text("""
                SELECT id, category, polarity, content, embedding_json
                FROM user_memories
                WHERE user_id = :uid AND is_active = TRUE
            """),
            {"uid": user_id},
        ).fetchall()

        for row in existing_rows:
            mem_id, mem_cat, mem_pol, mem_content, mem_emb = row
            if mem_emb and isinstance(mem_emb, list):
                sim = cosine_similarity(vector, mem_emb)
                if sim >= DEDUPLICATION_THRESHOLD:
                    # Update existing record
                    conn.execute(
                        text("""
                            UPDATE user_memories
                            SET content = :content,
                                category = :category,
                                polarity = :polarity,
                                embedding_json = :emb,
                                confidence = :conf,
                                updated_at = NOW()
                            WHERE id = :id
                        """),
                        {
                            "id": mem_id,
                            "content": content,
                            "category": category,
                            "polarity": polarity,
                            "emb": json.dumps(vector),
                            "conf": confidence,
                        },
                    )
                    return {
                        "id": str(mem_id),
                        "user_id": str(user_id),
                        "category": category,
                        "polarity": polarity,
                        "content": content,
                        "confidence": confidence,
                        "action": "updated",
                    }

        # Insert new record
        new_id = str(uuid.uuid4())
        conn.execute(
            text("""
                INSERT INTO user_memories (
                    id, user_id, category, polarity, content,
                    embedding_json, confidence, is_active
                ) VALUES (
                    :id, :user_id, :category, :polarity, :content,
                    :embedding_json, :confidence, TRUE
                )
            """),
            {
                "id": new_id,
                "user_id": user_id,
                "category": category,
                "polarity": polarity,
                "content": content,
                "embedding_json": json.dumps(vector),
                "confidence": confidence,
            },
        )

    return {
        "id": new_id,
        "user_id": str(user_id),
        "category": category,
        "polarity": polarity,
        "content": content,
        "confidence": confidence,
        "action": "created",
    }


def get_relevant_user_memories(
    user_id: str,
    query_text: str,
    limit: int = 4,
    threshold: float = DEFAULT_SIMILARITY_THRESHOLD,
) -> List[Dict[str, Any]]:
    """
    Retrieve user memories that are semantically relevant to the user query.

    Args:
        user_id (str): UUID of the user.
        query_text (str): Incoming natural language message or search query.
        limit (int): Maximum number of memories to return.
        threshold (float): Minimum cosine similarity to be included.

    Returns:
        List[Dict[str, Any]]: Ranked list of matching memories with similarity scores.
    """
    if not user_id or not query_text.strip():
        return []

    query_vector = get_embedding(query_text)
    engine = get_engine()

    with engine.connect() as conn:
        rows = conn.execute(
            text("""
                SELECT id, category, polarity, content, embedding_json, confidence
                FROM user_memories
                WHERE user_id = :uid AND is_active = TRUE
            """),
            {"uid": user_id},
        ).fetchall()

    if not rows:
        return []

    scored_memories = []
    for row in rows:
        mem_id, category, polarity, content, emb_json, conf = row
        if not emb_json:
            continue

        sim = cosine_similarity(query_vector, emb_json)
        if sim >= threshold:
            scored_memories.append({
                "id": str(mem_id),
                "category": category,
                "polarity": polarity,
                "content": content,
                "confidence": float(conf) if conf is not None else 1.0,
                "similarity": round(sim, 4),
            })

    # Sort descending by cosine similarity
    scored_memories.sort(key=lambda x: x["similarity"], reverse=True)
    return scored_memories[:limit]


def list_user_memories(user_id: str, category: Optional[str] = None) -> List[Dict[str, Any]]:
    """
    List all active memories for a given user.

    Args:
        user_id (str): UUID of the user.
        category (str, optional): Filter by category.

    Returns:
        List[Dict[str, Any]]: List of memory records without raw embedding payloads.
    """
    if not user_id:
        return []

    engine = get_engine()
    with engine.connect() as conn:
        query = """
            SELECT id, category, polarity, content, confidence, created_at, updated_at
            FROM user_memories
            WHERE user_id = :uid AND is_active = TRUE
        """
        params: Dict[str, Any] = {"uid": user_id}

        if category:
            query += " AND category = :cat"
            params["cat"] = category

        query += " ORDER BY updated_at DESC"
        rows = conn.execute(text(query), params).fetchall()

    return [
        {
            "id": str(r[0]),
            "category": r[1],
            "polarity": r[2],
            "content": r[3],
            "confidence": float(r[4]) if r[4] is not None else 1.0,
            "created_at": r[5].isoformat() if r[5] else None,
            "updated_at": r[6].isoformat() if r[6] else None,
        }
        for r in rows
    ]


def delete_user_memory(user_id: str, memory_id: str) -> bool:
    """
    Delete a specific user memory (hard delete or deactivate).

    Args:
        user_id (str): UUID of the user owning the memory.
        memory_id (str): UUID of the memory record.

    Returns:
        bool: True if a record was removed, False otherwise.
    """
    if not user_id or not memory_id:
        return False

    engine = get_engine()
    with engine.begin() as conn:
        res = conn.execute(
            text("""
                DELETE FROM user_memories
                WHERE id = :id AND user_id = :uid
            """),
            {"id": memory_id, "uid": user_id},
        )
        return res.rowcount > 0


def format_memories_for_prompt(memories: List[Dict[str, Any]]) -> str:
    """
    Format a list of retrieved memories into a clean system instruction snippet.

    Args:
        memories (List[Dict[str, Any]]): Retrieved memories from get_relevant_user_memories.

    Returns:
        str: Formatted instruction text.
    """
    if not memories:
        return ""

    lines = [
        "[SYSTEM NOTE] Relewantne preferencje i pamięć długoterminowa użytkownika:"
    ]
    for mem in memories:
        pol_label = {
            "like": "Upodobanie",
            "dislike": "Czego unika",
            "constraint": "Ograniczenie/Warunek",
            "habit": "Zwyczaj",
        }.get(mem.get("polarity", "like"), "Preferencja")

        lines.append(f"- [{pol_label}] {mem['content']}")

    lines.append("Uwzględnij te wytyczne w doborze kempingów, tempa i atrakcji bez konieczności ponownego pytania.")
    return "\n".join(lines)


def extract_memories_from_message(user_id: str, user_message: str) -> List[Dict[str, Any]]:
    """
    Analyze user message using an LLM to extract durable travel preferences.

    Filters out ephemeral trip parameters (like 'tomorrow I want 5 days') and
    identifies long-term habits, vehicle equipment, dislikes, or pet information.

    Args:
        user_id (str): UUID of the user.
        user_message (str): Incoming message from user.

    Returns:
        List[Dict[str, Any]]: Newly saved memory records.
    """
    if not user_id or not user_message or len(user_message.strip()) < 10:
        return []

    extraction_prompt = (
        "Jesteś modułem ekstrakcji pamięci długoterminowej dla asystenta podróży VW California. "
        "Twoim zadaniem jest wyłapanie TRWAŁYCH preferencji, nawyków, antypatii lub ograniczeń podróżnika "
        "(np. podróż z psem, unikanie płatnych dróg, preferowanie kempingów nad jeziorem, zamiłowanie do rowerów, "
        "posiadanie markizy, ograniczenia budżetowe na nocleg, model auta którym podróżuje — "
        "np. VW ID. Buzz (elektryczny), California eHybrid, California T6.1 diesel — kategoria vehicle).\n\n"
        "IGNORUJ tymczasowe parametry wycieczki (np. daty startu, konkretną trasę na ten weekend, liczbę dni).\n\n"
        "Zwróć TYLKO poprawny JSON (tablicę obiektów) lub pustą tablicę `[]` jeśli w wypowiedzi nie ma żadnych trwałych preferencji:\n"
        "[\n"
        "  {\n"
        "    \"category\": \"camping_style | activities | pets | vehicle | dislikes | driving_pace | general\",\n"
        "    \"polarity\": \"like | dislike | constraint | habit\",\n"
        "    \"content\": \"Krótkie, konkretne zdanie opisujące preferencję\"\n"
        "  }\n"
        "]"
    )

    client = get_client()
    try:
        response = client.chat.completions.create(
            model=MODEL_NAME,
            messages=[
                {"role": "system", "content": extraction_prompt},
                {"role": "user", "content": user_message},
            ],
            response_format={"type": "json_object"},
            **chat_kwargs(temperature=0.1),
        )

        content = response.choices[0].message.content or "{}"
        parsed = json.loads(content)
        # Some models wrap in a top-level key like {"memories": [...]}
        items = parsed if isinstance(parsed, list) else parsed.get("memories", parsed.get("items", []))

        saved = []
        for item in items:
            text_val = item.get("content", "").strip()
            if text_val:
                record = save_user_memory(
                    user_id=user_id,
                    content=text_val,
                    category=item.get("category", "general"),
                    polarity=item.get("polarity", "like"),
                    confidence=0.95,
                )
                saved.append(record)

        return saved

    except Exception as e:
        print(f"[user_memory] Memory extraction failed: {e}")
        return []


# ── Remembered vehicle (Nov 2026) ─────────────────────────────────────────────
# The van is an ordinary `vehicle` memory; these map it to the stop planner's keys.
VEHICLE_PATTERNS = (  # checked in this order: "California eHybrid" is phev, not diesel
    ("ev", r"id\.?\s*buzz|\belectric|elektr|\bev\b|\bbev\b"),
    ("phev", r"e-?hybrid|hybr|plug-?in|\bphev\b"),
    ("diesel", r"\bt6(\.1)?\b|\bt7\b|\btdi\b|diesel|california"),
)
VEHICLE_MEMORY_TEXT = {
    "ev": "Podróżuje VW ID. Buzz (elektryczny)",
    "phev": "Podróżuje VW California eHybrid (hybryda plug-in)",
    "diesel": "Podróżuje VW California T6.1 (diesel)",
}


def vehicle_key_from_text(text_value: str) -> Optional[str]:
    """'ev' / 'phev' / 'diesel' for a memory that names a van model, else None."""
    import re
    low = (text_value or "").lower()
    for key, pattern in VEHICLE_PATTERNS:
        if re.search(pattern, low):
            return key
    return None


def remembered_vehicle(user_id: Optional[str]) -> Optional[str]:
    """The user's van from the newest active `vehicle` memory naming a model (None if unknown)."""
    if not user_id:
        return None
    try:
        for mem in list_user_memories(user_id, category="vehicle"):  # newest first
            key = vehicle_key_from_text(mem.get("content"))
            if key:
                return key
    except Exception as e:
        print(f"[user_memory] Could not read the remembered vehicle: {e}")
    return None


def remember_vehicle(user_id: Optional[str], key: str) -> bool:
    """
    Make `key` the user's van: delete `vehicle` memories naming another model and save
    one canonical memory unless the same model is already remembered.
    """
    if not user_id or key not in VEHICLE_MEMORY_TEXT:
        return False
    try:
        same = False
        for mem in list_user_memories(user_id, category="vehicle"):
            mem_key = vehicle_key_from_text(mem.get("content"))
            if mem_key and mem_key != key:
                delete_user_memory(user_id, mem["id"])
            elif mem_key == key:
                same = True
        if not same:
            save_user_memory(user_id, VEHICLE_MEMORY_TEXT[key], category="vehicle",
                             polarity="habit", confidence=1.0)
        return True
    except Exception as e:
        print(f"[user_memory] Could not remember the vehicle: {e}")
        return False


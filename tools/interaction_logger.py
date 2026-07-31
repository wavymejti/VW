import uuid
from sqlalchemy import text
from tools.db import get_engine
from tools.memory_logger import get_memory_logger


def log_interaction(user_message: str, model_response: str) -> None:
    """
    Store every user message and model response pair for analysis.
    This module operates entirely independently of the core system
    and logs both in database memory log table and in-memory buffer.

    Args:
        user_message (str): Message from the user.
        model_response (str): Final text response from the model.
    """
    # Record in memory logger buffer
    memory_logger = get_memory_logger()
    memory_logger.info(
        message=f"User: {user_message[:50]}... | Model: {model_response[:50]}...",
        category="INTERACTION",
        metadata={
            "user_message": user_message,
            "model_response": model_response,
        },
    )

    try:
        engine = get_engine()
        with engine.connect() as conn:
            conn.execute(
                text("""
                    INSERT INTO interaction_logs
                        (id, user_message, model_response)
                    VALUES
                        (:id, :user_message, :model_response)
                """),
                {
                    "id": str(uuid.uuid4()),
                    "user_message": user_message,
                    "model_response": model_response,
                },
            )
            conn.commit()
    except Exception as e:
        # Fails silently to prevent affecting core modules
        print(f"  ⚠️  Failed to store interaction log: {e}")


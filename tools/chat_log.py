"""
Persistent chat log for diagnosing the trip planner.

Every chat turn is appended as one JSON line to logs/chat.jsonl (rotated at
5 MB, 5 files kept): the user message, the model, every tool call with its
arguments and a short summary of the result, the final reply and the timing.
Logging never breaks a chat request.
"""

import json
import logging
import os
from datetime import datetime, timezone
from logging.handlers import RotatingFileHandler

# VW_CHAT_LOG_DIR overrides the folder (tests point it at a temp dir).
LOG_DIR = os.getenv("VW_CHAT_LOG_DIR") or os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "logs"
)
LOG_PATH = os.path.join(LOG_DIR, "chat.jsonl")

_logger = None


def _get_logger():
    global _logger
    if _logger is None:
        os.makedirs(LOG_DIR, exist_ok=True)
        logger = logging.getLogger("vw.chat_log")
        logger.setLevel(logging.INFO)
        logger.propagate = False
        if not logger.handlers:
            handler = RotatingFileHandler(
                LOG_PATH, maxBytes=5 * 1024 * 1024, backupCount=5, encoding="utf-8"
            )
            handler.setFormatter(logging.Formatter("%(message)s"))
            logger.addHandler(handler)
        _logger = logger
    return _logger


def _summarize_result(result):
    """Keep what matters for diagnosis, not the whole payload (polylines, photos)."""
    if not isinstance(result, dict):
        return {"type": type(result).__name__}
    summary = {
        "status": result.get("status"),
        "message": result.get("message"),
        "warnings": result.get("warnings") or None,
        "num_days": result.get("num_days"),
        "trip_id": (result.get("trip") or {}).get("id") or result.get("trip_id"),
        "saved": result.get("saved"),
        "save_error": result.get("save_error"),
    }
    days = result.get("daily_schedules")
    if isinstance(days, list):
        summary["days"] = [
            {
                "day": d.get("day_number"),
                "hours": d.get("driving_hours"),
                "km": d.get("driving_km"),
                "stops": [
                    f"{w.get('type')}:{w.get('label')}" for w in (d.get("waypoints") or [])
                ],
            }
            for d in days
        ]
    if isinstance(result.get("results"), list):
        summary["results_count"] = len(result["results"])
    return {k: v for k, v in summary.items() if v is not None}


def log_chat_turn(user_id, lang, model, user_message, result, duration_s,
                  active_trip_id=None, error=None, raw_reply=None):
    """Append one chat turn to logs/chat.jsonl. Never raises."""
    try:
        result = result or {}
        entry = {
            "ts": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "user_id": user_id,
            "lang": lang,
            "model": model,
            "active_trip_id": active_trip_id,
            "message": user_message,
            "tool_calls": [
                {
                    "fn": tc.get("function_name"),
                    "args": tc.get("arguments"),
                    "result": _summarize_result(tc.get("result")),
                }
                for tc in (result.get("tool_calls") or [])
            ],
            "status": result.get("status"),
            "reply": result.get("text"),
            "slots_complete": result.get("slots_complete"),
            "duration_s": round(duration_s, 2),
        }
        if raw_reply and raw_reply.strip() != (result.get("text") or "").strip():
            entry["raw_reply"] = raw_reply  # model output before slot_state stripping
        if error:
            entry["error"] = error
        _get_logger().info(json.dumps(entry, ensure_ascii=False, default=str))
    except Exception as e:
        print(f"[chat_log] could not write log: {e}")

"""
Flask API server for the VW California AI Trip Planner.

Serves the frontend dashboard and provides REST API endpoints
for chat, camping search, route planning, and photo upload.

Usage:
    python3 -m tools.server
"""

import os
import sys

# Ensure project root is in sys.path when running script directly
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import json
from datetime import datetime, timedelta
from dotenv import load_dotenv
from flask import Flask, render_template, request, jsonify, send_from_directory, session, send_file, make_response, Response
from flask_cors import CORS
from sqlalchemy import text
from werkzeug.security import generate_password_hash, check_password_hash
import uuid

from tools import audius_service

from navigation.chat_handler import create_chat_session, send_message
from tools.search_campings import search_campings
from tools.plan_route import plan_route
from tools.extract_exif import store_photo, pin_photo_location, generate_thumbnail
from tools.generate_summary import generate_summary
from tools.db import get_engine
from tools.maps_client import get_client as get_maps_client, maps_allows, disabled_message as maps_disabled_message, place_details_basic, strip_paid_photos
from tools.openai_client import get_client
from tools.sniffer_line import make_sniffer_line
from tools.suggest_attractions import suggest_attractions
from tools.attractions_cache import (
    get_trip_attractions_cache,
    save_trip_attractions_cache,
)
from tools.user_memory import list_user_memories, save_user_memory, delete_user_memory
from tools.travel_suggestions import (
    generate_dynamic_suggestions,
    record_suggestion_choice,
    get_curated_fallback_suggestions,
)
from tools.location_service import (
    reverse_geocode_coordinates,
    sanitize_coordinates,
)
from navigation.dispatcher import _recalculate_day_route, apply_campsite_change

# Load environment variables
load_dotenv()

# Flask app setup
app = Flask(
    __name__,
    template_folder=os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        "frontend",
    ),
    static_folder=os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        "frontend",
    ),
    static_url_path="/static",
)
CORS(app)


@app.after_request
def _strip_paid_google_photos(response):
    """Unless GOOGLE_MAPS_MODE=full, remove billed Place Photo URLs from every JSON response
    (they may come from caches filled while photos were on). See tools/maps_client.py."""
    if maps_allows("places_rich") or not response.is_json or response.direct_passthrough:
        return response
    raw = response.get_data(as_text=True)
    if "/place/photo" not in raw and "/photos/" not in raw:
        return response
    try:
        data, removed = strip_paid_photos(json.loads(raw))
    except ValueError:
        return response
    if removed:
        response.set_data(json.dumps(data, ensure_ascii=False))
        print(f"[maps] stripped {removed} paid Google photo URL(s) from {request.path}")
    return response

# In-memory per-user chat sessions, keyed by user_id.
# We deliberately keep the full conversation history HERE (server memory)
# rather than in the Flask `session` cookie — the history (system prompt +
# model replies) is far too large for a cookie and would exceed the
# 4093-byte limit, silently breaking multi-turn conversations.
# Flask `session` only stores the tiny scalar `user_id` / `active_trip_id`.
_CHAT_SESSIONS = {}

# In-memory cache for /api/attractions — keyed by trip+params,
# valid for the lifetime of the server process.
_ATTRACTIONS_CACHE = {}

app.secret_key = os.getenv("SECRET_KEY", "dev_secret_key_vw_planner")
app.config["SEND_FILE_MAX_AGE_DEFAULT"] = 0

# --- Authentication ---

@app.route("/api/register", methods=["POST"])
def api_register():
    data = request.get_json()
    email = data.get("email")
    password = data.get("password")
    display_name = data.get("display_name", "VW Explorer")

    if not email or not password:
        return jsonify({"status": "error", "message": "Email and password required."}), 400

    try:
        engine = get_engine()
        with engine.begin() as conn:
            existing = conn.execute(text("SELECT id FROM users WHERE email = :email"), {"email": email}).fetchone()
            if existing:
                return jsonify({"status": "error", "message": "Email already registered."}), 400

            pwd_hash = generate_password_hash(password, method='pbkdf2:sha256')
            user_id = str(uuid.uuid4())
            conn.execute(
                text("INSERT INTO users (id, email, password_hash, display_name) VALUES (:id, :email, :hash, :name)"),
                {"id": user_id, "email": email, "hash": pwd_hash, "name": display_name}
            )

            session["user_id"] = user_id
            return jsonify({"status": "success", "user": {"id": user_id, "email": email, "display_name": display_name}})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route("/api/login", methods=["POST"])
def api_login():
    data = request.get_json()
    email = data.get("email")
    password = data.get("password")

    try:
        engine = get_engine()
        with engine.connect() as conn:
            user = conn.execute(
                text("SELECT id, email, display_name, password_hash FROM users WHERE email = :email"),
                {"email": email}
            ).fetchone()

            if user and user[3] and check_password_hash(user[3], password):
                session["user_id"] = str(user[0])
                return jsonify({"status": "success", "user": {"id": str(user[0]), "email": user[1], "display_name": user[2]}})
            else:
                return jsonify({"status": "error", "message": "Invalid email or password."}), 401
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route("/api/logout", methods=["POST"])
def api_logout():
    session.pop("user_id", None)
    return jsonify({"status": "success"})

@app.route("/api/trips", methods=["GET"])
def api_get_trips():
    """Get all trips for the authenticated user."""
    user_id = session.get("user_id")
    if not user_id:
        return jsonify({"status": "error", "message": "Not authenticated"}), 401

    try:
        engine = get_engine()
        with engine.connect() as conn:
            trips = conn.execute(
                text("SELECT id, title, start_date, end_date, status FROM trips WHERE user_id = :uid ORDER BY created_at DESC"),
                {"uid": user_id}
            ).fetchall()

            trip_list = [
                {"id": str(t[0]), "title": t[1], "start_date": str(t[2]), "end_date": str(t[3]), "status": t[4]}
                for t in trips
            ]

            return jsonify({
                "status": "success",
                "trips": trip_list
            })
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500


@app.route("/api/me", methods=["GET"])
def api_me():
    user_id = session.get("user_id")
    if not user_id:
        return jsonify({"status": "error", "message": "Not authenticated"}), 401

    try:
        engine = get_engine()
        with engine.connect() as conn:
            user = conn.execute(
                text("SELECT id, email, display_name FROM users WHERE id = :id"),
                {"id": user_id}
            ).fetchone()
            if user:
                return jsonify({"status": "success", "user": {"id": str(user[0]), "email": user[1], "display_name": user[2]}})
            return jsonify({"status": "error", "message": "User not found"}), 404
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500


@app.route("/api/preferences", methods=["GET"])
def api_get_preferences():
    """Get user preferences from preferences_json column."""
    user_id = session.get("user_id")
    if not user_id:
        return jsonify({"status": "error", "message": "Not authenticated"}), 401

    try:
        engine = get_engine()
        with engine.connect() as conn:
            prefs = conn.execute(
                text("SELECT preferences_json FROM users WHERE id = :id"),
                {"id": user_id}
            ).scalar()

            # Default preferences if none set
            default_prefs = {
                "max_daily_drive_hours": 6.0,
                "preferred_amenities": [],
                "budget_per_night_eur": None,
                "hookup_type": None,
                "vehicle_model": "VW California"
            }

            if prefs:
                # Merge with defaults to ensure all keys exist
                default_prefs.update(prefs)

            return jsonify({"status": "success", "preferences": default_prefs})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500


@app.route("/api/preferences", methods=["PUT"])
def api_update_preferences():
    """Update user preferences in preferences_json column."""
    user_id = session.get("user_id")
    if not user_id:
        return jsonify({"status": "error", "message": "Not authenticated"}), 401

    data = request.get_json()
    if not data:
        return jsonify({"status": "error", "message": "No data provided"}), 400

    # Validate and extract allowed preference fields
    allowed_fields = {
        "max_daily_drive_hours": (float, int),
        "preferred_amenities": list,
        "budget_per_night_eur": (float, int, type(None)),
        "hookup_type": (str, type(None)),
        "vehicle_model": (str, type(None))
    }

    prefs_to_save = {}
    for field, expected_type in allowed_fields.items():
        if field in data:
            value = data[field]
            # Validate type
            if value is not None and not isinstance(value, expected_type):
                return jsonify({"status": "error", "message": f"Invalid type for {field}"}), 400
            prefs_to_save[field] = value

    try:
        engine = get_engine()
        with engine.begin() as conn:
            # Get existing preferences
            existing = conn.execute(
                text("SELECT preferences_json FROM users WHERE id = :id"),
                {"id": user_id}
            ).scalar() or {}

            # Merge with new preferences
            existing.update(prefs_to_save)

            # Update the database
            conn.execute(
                text("UPDATE users SET preferences_json = :prefs, updated_at = NOW() WHERE id = :id"),
                {"prefs": json.dumps(existing), "id": user_id}
            )

            return jsonify({"status": "success", "preferences": existing})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500


@app.route("/api/user_memories", methods=["GET"])
def api_get_user_memories():
    """Get all stored long-term memories/preferences for the authenticated user."""
    user_id = session.get("user_id")
    if not user_id:
        return jsonify({"status": "error", "message": "Not authenticated"}), 401

    category = request.args.get("category")
    try:
        memories = list_user_memories(user_id=user_id, category=category)
        return jsonify({"status": "success", "memories": memories})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500


@app.route("/api/user_memories", methods=["POST"])
def api_add_user_memory():
    """Manually add or update a long-term preference memory for the user."""
    user_id = session.get("user_id")
    if not user_id:
        return jsonify({"status": "error", "message": "Not authenticated"}), 401

    data = request.get_json() or {}
    content = data.get("content", "").strip()
    category = data.get("category", "general")
    polarity = data.get("polarity", "like")

    if not content:
        return jsonify({"status": "error", "message": "Content is required"}), 400

    try:
        record = save_user_memory(
            user_id=user_id,
            content=content,
            category=category,
            polarity=polarity,
            confidence=1.0,
        )
        return jsonify({"status": "success", "memory": record})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500


@app.route("/api/user_memories/<memory_id>", methods=["DELETE"])
def api_delete_user_memory(memory_id):
    """Delete a specific user memory (GDPR / user control)."""
    user_id = session.get("user_id")
    if not user_id:
        return jsonify({"status": "error", "message": "Not authenticated"}), 401

    try:
        success = delete_user_memory(user_id=user_id, memory_id=memory_id)
        if success:
            return jsonify({"status": "success", "message": "Memory deleted."})
        return jsonify({"status": "error", "message": "Memory not found or unauthorized."}), 404
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500


@app.route("/api/travel_suggestions", methods=["GET"])
def api_get_travel_suggestions():
    """
    Get dynamic travel suggestions tailored for middle-aged travelers (40-60).

    Integrates with RAG user memories if user is authenticated and supports
    duration filtering (all, weekend, week, expedition).
    """
    user_id = session.get("user_id")
    lang = request.args.get("lang", "pl")
    duration = request.args.get("duration", "all")
    if duration not in ("all", "weekend", "week", "expedition"):
        duration = "all"

    user_location = request.args.get("location")
    if not user_location:
        city = request.args.get("city")
        country = request.args.get("country")
        if city and country:
            user_location = f"{city}, {country}"
        elif city:
            user_location = city

    try:
        count = int(request.args.get("count", 3))
    except (ValueError, TypeError):
        count = 3
    count = max(1, min(count, 6))

    try:
        suggestions = generate_dynamic_suggestions(
            user_id=user_id,
            lang=lang,
            count=count,
            duration=duration,
            user_location=user_location,
        )
        return jsonify({
            "status": "success",
            "suggestions": suggestions,
            "personalized": bool(user_id),
            "duration": duration,
            "user_location": user_location,
        })
    except Exception as e:
        print(f"Error in api_get_travel_suggestions: {e}")
        fallback = get_curated_fallback_suggestions(
            lang=lang, duration=duration, shuffle=True, user_location=user_location
        )[:count]
        return jsonify({
            "status": "success",
            "suggestions": fallback,
            "personalized": False,
            "fallback": True,
            "duration": duration,
            "user_location": user_location,
        })


@app.route("/api/travel_suggestions/select", methods=["POST"])
def api_select_travel_suggestion():
    """
    Record user selection of a travel suggestion card and feed into RAG memory.
    """
    user_id = session.get("user_id")
    data = request.get_json() or {}
    suggestion = data.get("suggestion")

    if not suggestion:
        return jsonify({"status": "error", "message": "Suggestion data is required"}), 400

    saved_memory = None
    if user_id:
        try:
            saved_memory = record_suggestion_choice(user_id=user_id, suggestion_data=suggestion)
        except Exception as e:
            print(f"Failed to record suggestion in RAG memory: {e}")

    prompt = suggestion.get("prompt", "")
    return jsonify({
        "status": "success",
        "prompt": prompt,
        "rag_memory_recorded": bool(saved_memory),
        "memory": saved_memory,
    })




from tools.trip_store import _sanitize_for_json, _get_trip_data  # noqa: E402


@app.route("/api/trip/<trip_id>", methods=["GET"])
def api_get_trip(trip_id):
    """Get details for a specific trip."""
    user_id = session.get("user_id")
    if not user_id:
        return jsonify({"status": "error", "message": "Not authenticated"}), 401

    trip_data = _get_trip_data(trip_id)
    if not trip_data:
        return jsonify({"status": "error", "message": "Trip not found"}), 404

    return jsonify({"status": "success", "trip_data": trip_data})


_MAX_CHAT_SESSIONS = 200


def get_chat_session(user_id=None, trip_id=None, lang="pl", conversation_id=None):
    """
    Get or create a chat session held in SERVER memory (`_CHAT_SESSIONS`).
    The conversation history + slot_state live here (never in the Flask cookie).

    With `conversation_id` (the frontend makes a new one on every page load) each
    page load is its own fresh chat: no history from the DB and no active trip
    carried over from the cookie. Without it (older clients) one session per user
    is kept, as before.

    Returns:
        dict: Active chat session (with live client/tools attached).
    """
    uid = user_id or "anon"
    if conversation_id:
        key = f"{uid}:{conversation_id}"
    elif user_id:
        key = uid
    else:
        # Anonymous client without a conversation id (older frontend): one shared
        # session, as before. The current frontend always sends a conversation id.
        key = "anon"

    known = key in _CHAT_SESSIONS
    print(f"[get_chat_session] key={key!r} lang={lang!r} known={known} sessions={len(_CHAT_SESSIONS)}", flush=True)

    if not known:
        fresh = bool(conversation_id)
        sess = create_chat_session(
            user_id=user_id,
            trip_id=None if fresh else trip_id,
            lang=lang,
            load_history=not fresh,
        )
        sess["user_id"] = uid
        sess["slot_state"] = None
        sess["active_trip_id"] = None if fresh else session.get("active_trip_id")
        sess["conversation_id"] = conversation_id
        _CHAT_SESSIONS[key] = sess
        # Drop the oldest sessions so page reloads don't grow memory forever.
        while len(_CHAT_SESSIONS) > _MAX_CHAT_SESSIONS:
            _CHAT_SESSIONS.pop(next(iter(_CHAT_SESSIONS)))
    else:
        sess = _CHAT_SESSIONS[key]
        sess["lang"] = lang or sess.get("lang", "pl")
        if not conversation_id:
            if trip_id:
                sess["trip_id"] = trip_id
            # Re-sync the active_trip_id from the Flask session if present.
            if session.get("active_trip_id"):
                sess["active_trip_id"] = session["active_trip_id"]

    sess["_key"] = key
    return sess


# ── Frontend Route ────────────────────────────────────────────
@app.route("/")
def index():
    """Serve the main dashboard."""
    return render_template(
        "index.html",
        # The interactive map (Maps JS) loads only when GOOGLE_MAPS_MODE=full.
        google_maps_key=os.getenv("GOOGLE_MAPS_API_KEY", "") if maps_allows("map") else "",
    )


@app.route("/summaries/<path:filename>")
def serve_summary(filename):
    """Serve generated summary images/files."""
    summary_dir = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        ".tmp",
        "summaries",
    )
    return send_from_directory(summary_dir, filename)


@app.route("/photos/file/<path:filename>", methods=["GET", "OPTIONS"])
def serve_photo_file(filename):
    """Serve uploaded photos or thumbnails, converting HEIC/HEIF to JPEG for browser support."""
    if request.method == "OPTIONS":
        resp = make_response("", 204)
        resp.headers["Access-Control-Allow-Origin"] = "*"
        resp.headers["Access-Control-Allow-Methods"] = "GET, OPTIONS"
        resp.headers["Access-Control-Allow-Headers"] = "*"
        return resp

    tmp_dir = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        ".tmp"
    )
    upload_dir = os.path.join(tmp_dir, "uploads")
    
    # Check if file exists in upload_dir or tmp_dir
    target_path = None
    if os.path.exists(os.path.join(upload_dir, filename)):
        target_path = os.path.join(upload_dir, filename)
    elif os.path.exists(os.path.join(tmp_dir, filename)):
        target_path = os.path.join(tmp_dir, filename)

    # On-demand thumbnail fallback if requested thumbnail does not yet exist
    if not target_path and "_thumb." in filename:
        name_part, thumb_ext = os.path.splitext(filename)
        base_stem = name_part.replace("_thumb", "")
        # Search for original file with various extensions
        candidate_exts = [".jpg", ".jpeg", ".png", ".webp", ".heic", ".heif", ".JPG", ".JPEG", ".PNG", ".HEIC"]
        for ext in candidate_exts:
            for check_dir in [upload_dir, tmp_dir]:
                candidate = os.path.join(check_dir, f"{base_stem}{ext}")
                if os.path.exists(candidate):
                    generated_thumb = generate_thumbnail(candidate, output_dir=tmp_dir)
                    if generated_thumb and os.path.exists(generated_thumb):
                        target_path = generated_thumb
                        break
            if target_path:
                break

    if target_path:
        ext = os.path.splitext(target_path)[1].lower()
        if ext in (".heic", ".heif"):
            # Convert HEIC to browser-renderable JPEG
            jpg_name = f"{os.path.splitext(os.path.basename(target_path))[0]}_converted.jpg"
            jpg_path = os.path.join(upload_dir, jpg_name)
            if not os.path.exists(jpg_path):
                try:
                    from PIL import Image
                    try:
                        from pillow_heif import register_heif_opener
                        register_heif_opener()
                    except ImportError:
                        pass
                    im = Image.open(target_path)
                    im.convert("RGB").save(jpg_path, "JPEG", quality=90)
                except Exception as e:
                    print(f"⚠️ Failed to convert HEIC to JPG: {e}")
            if os.path.exists(jpg_path):
                response = send_from_directory(upload_dir, jpg_name, mimetype="image/jpeg")
                response.headers["Access-Control-Allow-Origin"] = "*"
                response.headers["Access-Control-Allow-Methods"] = "GET, OPTIONS"
                response.headers["Cache-Control"] = "public, max-age=86400"
                return response

        response = send_from_directory(os.path.dirname(target_path), os.path.basename(target_path))
        response.headers["Access-Control-Allow-Origin"] = "*"
        response.headers["Access-Control-Allow-Methods"] = "GET, OPTIONS"
        response.headers["Cache-Control"] = "public, max-age=86400"
        return response

    response = jsonify({"status": "error", "message": "File not found"})
    response.headers["Access-Control-Allow-Origin"] = "*"
    return response, 404


# ── API Routes ────────────────────────────────────────────────

@app.route("/api/location/reverse", methods=["POST"])
def api_reverse_location():
    """
    Reverse geocode client coordinates to human-readable address and city.
    """
    data = request.get_json() or {}
    lat = data.get("lat")
    lng = data.get("lng")
    lang = data.get("lang", "pl")

    result = reverse_geocode_coordinates(lat, lng, lang=lang)
    return jsonify(result)


@app.route("/api/chat", methods=["POST"])
def api_chat():
    """
    Handle a chat message from the user.

    Sends the message through the OpenAI model with tool calling,
    and returns the assistant's response.
    """
    data = request.get_json() or {}
    user_message = data.get("message", "").strip()
    lang = data.get("lang", "pl")
    user_location = data.get("user_location") or data.get("location")

    if not user_message:
        return jsonify({
            "status": "error",
            "message": "Empty message.",
        }), 400

    # Pass the logged-in user_id (and active trip, if known) into a
    # per-user chat session so messages persist and trips are linked.
    user_id = session.get("user_id")
    conversation_id = (data.get("conversation_id") or "").strip()[:64] or None
    active_trip_id = session.get("active_trip_id")
    chat = get_chat_session(user_id=user_id, trip_id=active_trip_id, lang=lang,
                            conversation_id=conversation_id)
    if conversation_id:
        # A fresh conversation only knows the trips planned in it.
        active_trip_id = chat.get("active_trip_id")
    print(f"[api_chat] user_id={user_id!r} conv={conversation_id!r} lang={lang!r} active_trip_id={active_trip_id!r} msg={user_message[:30]!r} loc={user_location!r}")
    chat["lang"] = lang
    result = send_message(
        chat,
        user_message,
        trip_id=active_trip_id,
        user_location=user_location,
    )

    # Persist the running slot_state + active_trip_id in server memory
    # (never the cookie) so the next request can merge with it and the
    # route stays in context. Also mirror active_trip_id into the Flask
    # session for cross-endpoint use (e.g. /api/trip lookups).
    key = chat.get("_key")
    if key in _CHAT_SESSIONS:
        _CHAT_SESSIONS[key]["slot_state"] = result.get("slot_state")
        if chat.get("active_trip_id"):
            _CHAT_SESSIONS[key]["active_trip_id"] = chat["active_trip_id"]
            session["active_trip_id"] = chat["active_trip_id"]

    # What the 3D Sniffer reads aloud: the reply itself in English (+ mood); None if unavailable.
    if result.get("text") and result.get("status") in ("success", "partial"):
        result["sniffer"] = make_sniffer_line(user_message, result["text"], lang=lang)

    return jsonify(result)


@app.route("/api/chat/history", methods=["GET"])
def api_chat_history():
    """Get stored chat history for the logged-in user or active trip."""
    user_id = session.get("user_id")
    trip_id = request.args.get("trip_id") or session.get("active_trip_id")

    if not user_id and not trip_id:
        return jsonify({"status": "success", "messages": []})

    try:
        engine = get_engine()
        with engine.connect() as conn:
            query = "SELECT id, role, content, created_at FROM chat_messages WHERE "
            params = {}
            if trip_id:
                query += "trip_id = :trip_id "
                params["trip_id"] = trip_id
            elif user_id:
                query += "user_id = :user_id "
                params["user_id"] = user_id

            query += "ORDER BY created_at ASC"
            rows = conn.execute(text(query), params).fetchall()

            messages = [
                {
                    "id": str(r[0]),
                    "role": r[1],
                    "content": r[2],
                    "created_at": r[3].isoformat() if r[3] else None
                }
                for r in rows
            ]

            return jsonify({"status": "success", "messages": messages})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500


@app.route("/api/search_campings", methods=["POST"])
def api_search_campings():
    """
    Search for campgrounds near a location.

    Expects JSON with lat, lng, and optional filters.
    """
    data = request.get_json()
    lat = data.get("lat")
    lng = data.get("lng")

    if lat is None or lng is None:
        return jsonify({
            "status": "error",
            "message": "lat and lng are required.",
        }), 400

    result = search_campings(
        lat=lat,
        lng=lng,
        radius_km=data.get("radius_km", 50),
        amenities=data.get("amenities"),
        max_cost_eur=data.get("max_cost_eur"),
        vw_compatible=data.get("vw_compatible", True),
        limit=data.get("limit", 10),
    )

    return jsonify(result)


@app.route("/api/plan_route", methods=["POST"])
def api_plan_route():
    """
    Plan a multi-day route.

    Expects JSON with origin, destination, num_days,
    and start_date.
    """
    data = request.get_json()
    user_id = session.get("user_id")
    if not user_id:
        return jsonify({"status": "error", "message": "Not authenticated"}), 401

    required = ["origin", "destination", "num_days", "start_date"]
    for field in required:
        if field not in data:
            return jsonify({
                "status": "error",
                "message": f"Missing required field: {field}",
            }), 400

    result = plan_route(
        origin=data["origin"],
        destination=data["destination"],
        num_days=data["num_days"],
        start_date=data["start_date"],
        max_daily_drive_hours=data.get(
            "max_daily_drive_hours", 6.0
        ),
        preferred_amenities=data.get("preferred_amenities"),
        budget_per_night_eur=data.get("budget_per_night_eur"),
        user_id=user_id,
        round_trip=data.get("round_trip", False)
    )

    return jsonify(result)


@app.route("/api/select_camping", methods=["POST"])
def api_select_camping():
    """
    Select a new camping option for a specific day.
    Replaces the overnight waypoint and recalculates the route.
    """
    data = request.get_json()
    user_id = session.get("user_id")
    if not user_id:
        return jsonify({"status": "error", "message": "Not authenticated"}), 401

    trip_id = data.get("trip_id")
    day_number = data.get("day_number")
    camping = data.get("camping")

    if not all([trip_id, day_number, camping]):
        return jsonify({"status": "error", "message": "trip_id, day_number, and camping are required"}), 400

    result = apply_campsite_change(trip_id, day_number, camping)
    if result.get("status") != "success":
        return jsonify(result), result.pop("http_status", 400)
    trip_data = _get_trip_data(trip_id)
    return jsonify({"status": "success", "message": "Camping selected and route updated.", "trip_data": trip_data})


@app.route("/api/add_attraction", methods=["POST"])
def api_add_attraction():
    """
    Add an attraction to a specific day's route schedule.
    Inserts a new waypoint of type 'attraction' and recalculates the day's route.
    """
    data = request.get_json()
    user_id = session.get("user_id")
    if not user_id:
        return jsonify({"status": "error", "message": "Not authenticated"}), 401

    trip_id = data.get("trip_id")
    day_number = data.get("day_number", 1)
    attraction = data.get("attraction")

    if not trip_id or not attraction or not isinstance(attraction, dict):
        return jsonify({"status": "error", "message": "trip_id and attraction object are required"}), 400

    attr_name = attraction.get("name", "Atrakcja")
    attr_lat = attraction.get("lat")
    attr_lng = attraction.get("lng")

    if attr_lat is None or attr_lng is None:
        return jsonify({"status": "error", "message": "attraction lat and lng are required"}), 400

    try:
        engine = get_engine()
        with engine.begin() as conn:
            schedule_row = conn.execute(
                text("SELECT id, waypoints FROM daily_schedules WHERE trip_id = :tid AND day_number = :day"),
                {"tid": trip_id, "day": day_number}
            ).fetchone()

            if not schedule_row:
                return jsonify({"status": "error", "message": f"Day schedule for day {day_number} not found"}), 404

            schedule_id = schedule_row[0]
            waypoints = schedule_row[1] or []
            if isinstance(waypoints, str):
                waypoints = json.loads(waypoints)

            # Check if this attraction is already in the waypoints for this day
            attr_place_id = attraction.get("place_id")
            already_added = any(
                (attr_place_id and wp.get("place_id") == attr_place_id) or
                (wp.get("label") == attr_name and abs(wp.get("lat", 0) - attr_lat) < 0.0001 and abs(wp.get("lng", 0) - attr_lng) < 0.0001)
                for wp in waypoints
            )

            if not already_added:
                new_wp = {
                    "order": max(len(waypoints) - 1, 0),
                    "type": "attraction",
                    "label": attr_name,
                    "lat": attr_lat,
                    "lng": attr_lng,
                    "place_id": attr_place_id,
                    "address": attraction.get("address"),
                    "rating": attraction.get("rating"),
                    "photo_url": attraction.get("photo_url"),
                    "category_label": attraction.get("category_label", "Atrakcja"),
                    "emoji": attraction.get("emoji", "⭐"),
                    "color": attraction.get("color", "#F9A825"),
                    "notes": "Added from map attractions"
                }

                if len(waypoints) > 1:
                    # Insert right before the last waypoint (which is destination/camping)
                    waypoints = waypoints[:-1] + [new_wp] + waypoints[-1:]
                else:
                    waypoints.append(new_wp)

                # Re-index order
                for i, wp in enumerate(waypoints):
                    wp["order"] = i

                # Recalculate route and save
                update_done = _recalculate_day_route(conn, schedule_id, waypoints)
                if not update_done:
                    conn.execute(
                        text("UPDATE daily_schedules SET waypoints = CAST(:wps AS jsonb) WHERE id = :sid"),
                        {"wps": json.dumps(waypoints), "sid": str(schedule_id)}
                    )

        # Invalidate attractions cache for this trip so fresh data is computed
        cache_keys = [k for k in list(_ATTRACTIONS_CACHE.keys()) if k.startswith(f"{trip_id}:")]
        for k in cache_keys:
            _ATTRACTIONS_CACHE.pop(k, None)

        trip_data = _get_trip_data(trip_id)
        return jsonify({
            "status": "success",
            "message": f"Added attraction '{attr_name}' to Day {day_number}.",
            "trip_data": trip_data
        })
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500


@app.route("/api/attractions/<trip_id>", methods=["GET"])
def api_get_attractions(trip_id):
    """
    Return points of interest along the route for a given trip.

    Decodes each day's route polyline, samples it at regular intervals,
    queries Google Places Nearby API, deduplicates by place_id, and
    returns attractions grouped by day number.

    Results are cached in memory for the duration of the server process
    (keyed by trip_id + preferences + limit) so repeated calls are instant.

    Query params:
        preferences (str): Comma-separated keywords, e.g. 'zamki,natura'.
        limit_per_day (int): Max results per day (default 8).
        sample_every_km (int): Sampling interval in km (default 80).
    """
    preferences = request.args.get("preferences", None)
    limit_per_day = int(request.args.get("limit_per_day", 8))
    # Default sample interval raised to 80 km to reduce API call count
    sample_every_km = float(request.args.get("sample_every_km", 80))

    # Build a cache key
    cache_key = f"{trip_id}:{preferences or ''}:{limit_per_day}:{int(sample_every_km)}"
    if cache_key in _ATTRACTIONS_CACHE:
        print(f"[api_get_attractions] RAM Cache HIT for {cache_key}", flush=True)
        return jsonify(_ATTRACTIONS_CACHE[cache_key])

    # Check PostgreSQL persistent cache
    db_cached = get_trip_attractions_cache(trip_id, cache_key)
    if db_cached:
        print(f"[api_get_attractions] PostgreSQL Cache HIT for {cache_key}", flush=True)
        _ATTRACTIONS_CACHE[cache_key] = db_cached
        return jsonify(db_cached)

    print(f"[api_get_attractions] Fetching attractions for trip {trip_id} "
          f"(pref={preferences}, limit={limit_per_day}, km={sample_every_km})", flush=True)

    result = suggest_attractions(
        trip_id=trip_id,
        preferences=preferences,
        limit_per_day=limit_per_day,
        sample_every_km=sample_every_km,
    )

    if result.get("status") == "success":
        _ATTRACTIONS_CACHE[cache_key] = result
        save_trip_attractions_cache(trip_id, cache_key, result)

    print(f"[api_get_attractions] Done — status={result.get('status')} "
          f"days={len(result.get('attractions_by_day', {}))}", flush=True)
    return jsonify(result)


@app.route("/api/place_details/<place_id>", methods=["GET"])
def api_place_details(place_id):
    """Fetch details from Google Places API."""
    if not maps_allows("places"):
        return jsonify({"status": "error", "message": maps_disabled_message()}), 503
    if not maps_allows("places_rich"):
        # Basic fields only: no photos, rating, reviews, phone or website (cost switch)
        try:
            result = place_details_basic(place_id)
            result["photo_urls"] = []
            return jsonify({"status": "success", "details": result})
        except Exception as e:
            return jsonify({"status": "error", "message": str(e)}), 500
    try:
        client = get_maps_client()
        details = client.place(
            place_id=place_id,
            fields=["name", "rating", "reviews", "photos", "url", "formatted_phone_number", "website"]
        )

        result = details.get("result", {})

        # We need to construct actual photo URLs using the photo_reference
        photos = []
        gmaps_key = os.getenv("GOOGLE_MAPS_API_KEY")
        for p in result.get("photos", [])[:5]:
            ref = p.get("photo_reference")
            if ref:
                url = f"https://maps.googleapis.com/maps/api/place/photo?maxwidth=800&photoreference={ref}&key={gmaps_key}"
                photos.append(url)

        result["photo_urls"] = photos
        return jsonify({"status": "success", "details": result})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500


@app.route("/api/upload_photo", methods=["POST"])
def api_upload_photo():
    """
    Upload and process a photo for Travel Memory.

    Accepts multipart form data with a 'photo' file.
    """
    user_id = session.get("user_id")
    if not user_id:
        return jsonify({"status": "error", "message": "Not authenticated"}), 401

    if "photo" not in request.files:
        return jsonify({
            "status": "error",
            "message": "No photo file provided.",
        }), 400

    photo_file = request.files["photo"]

    if photo_file.filename == "":
        return jsonify({
            "status": "error",
            "message": "Empty filename.",
        }), 400

    # Save to .tmp/ directory
    tmp_dir = os.path.join(
        os.path.dirname(
            os.path.dirname(os.path.abspath(__file__))
        ),
        ".tmp",
        "uploads",
    )
    os.makedirs(tmp_dir, exist_ok=True)

    filepath = os.path.join(tmp_dir, photo_file.filename)
    photo_file.save(filepath)

    # Optional trip_id from frontend (fallback to active trip in session)
    trip_id = request.form.get("trip_id") or session.get("active_trip_id")

    # Process the photo
    result = store_photo(
        filepath=filepath,
        user_id=user_id,
        trip_id=trip_id,
    )

    return jsonify(result)


@app.route("/api/pin_photo", methods=["POST"])
def api_pin_photo():
    """
    Manually pin a photo or update its location, capture date, trip day, and trip.

    Expects JSON with photo_id, and optional lat, lng, captured_at, tagged_day_schedule_id, day_number, trip_id.
    """
    user_id = session.get("user_id")
    if not user_id:
        return jsonify({"status": "error", "message": "Not authenticated"}), 401

    data = request.get_json() or {}
    photo_id = data.get("photo_id")
    lat = data.get("lat")
    lng = data.get("lng")
    captured_at = data.get("captured_at")
    tagged_day_schedule_id = data.get("tagged_day_schedule_id")
    day_number = data.get("day_number")
    trip_id = data.get("trip_id") or session.get("active_trip_id")

    if not photo_id:
        return jsonify({
            "status": "error",
            "message": "photo_id is required.",
        }), 400

    result = pin_photo_location(
        photo_id=photo_id,
        lat=lat,
        lng=lng,
        user_id=user_id,
        captured_at=captured_at,
        tagged_day_schedule_id=tagged_day_schedule_id,
        trip_id=trip_id,
        day_number=day_number,
    )
    return jsonify(result)


@app.route("/api/trips/<trip_id>/update_dates", methods=["POST"])
def api_update_trip_dates(trip_id):
    """
    Update start_date and optionally end_date for a trip, shifting all daily schedules accordingly.
    """
    user_id = session.get("user_id")
    if not user_id:
        return jsonify({"status": "error", "message": "Not authenticated"}), 401

    data = request.get_json() or {}
    new_start_str = data.get("start_date")
    if not new_start_str:
        return jsonify({"status": "error", "message": "start_date is required (YYYY-MM-DD)"}), 400

    try:
        new_start = datetime.strptime(new_start_str, "%Y-%m-%d").date()
    except ValueError:
        return jsonify({"status": "error", "message": "Invalid start_date format. Use YYYY-MM-DD"}), 400

    new_end_str = data.get("end_date")
    new_end = None
    if new_end_str:
        try:
            new_end = datetime.strptime(new_end_str, "%Y-%m-%d").date()
        except ValueError:
            return jsonify({"status": "error", "message": "Invalid end_date format. Use YYYY-MM-DD"}), 400

    try:
        engine = get_engine()
        with engine.begin() as conn:
            trip_row = conn.execute(
                text("SELECT id, start_date, end_date FROM trips WHERE id = :tid AND user_id = :uid"),
                {"tid": trip_id, "uid": user_id}
            ).fetchone()

            if not trip_row:
                return jsonify({"status": "error", "message": "Trip not found or unauthorized"}), 404

            old_start = trip_row.start_date
            old_end = trip_row.end_date

            if not new_end and old_start and old_end:
                duration = (old_end - old_start).days
                new_end = new_start + timedelta(days=duration)
            elif not new_end:
                new_end = new_start

            # Update trips table
            conn.execute(
                text("UPDATE trips SET start_date = :s, end_date = :e, updated_at = NOW() WHERE id = :tid"),
                {"s": new_start, "e": new_end, "tid": trip_id}
            )

            # Update daily schedules
            scheds = conn.execute(
                text("SELECT id, day_number FROM daily_schedules WHERE trip_id = :tid ORDER BY day_number"),
                {"tid": trip_id}
            ).fetchall()

            for sched in scheds:
                day_offset = (sched.day_number - 1) if sched.day_number else 0
                s_date = new_start + timedelta(days=day_offset)
                conn.execute(
                    text("UPDATE daily_schedules SET schedule_date = :s_date WHERE id = :sid"),
                    {"s_date": s_date, "sid": sched.id}
                )

        return jsonify({
            "status": "success",
            "message": "Trip dates updated successfully",
            "trip_id": trip_id,
            "start_date": new_start.isoformat(),
            "end_date": new_end.isoformat(),
        })
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500


@app.route("/api/photos", methods=["GET"])
def api_get_photos():
    """Get stored photos for the authenticated user (and optional trip_id)."""
    user_id = session.get("user_id")
    if not user_id:
        return jsonify({"status": "error", "message": "Not authenticated"}), 401

    trip_id = request.args.get("trip_id") or session.get("active_trip_id")

    try:
        engine = get_engine()
        with engine.connect() as conn:
            query = """
                SELECT id, user_id, trip_id, file_url, thumbnail_url,
                       lat, lng, captured_at, caption, tagged_day_schedule_id, original_filename
                FROM photos
                WHERE user_id = :uid
            """
            params = {"uid": user_id}
            if trip_id:
                query += " AND (trip_id = :tid OR trip_id IS NULL)"
                params["tid"] = trip_id

            query += " ORDER BY captured_at DESC NULLS LAST, created_at DESC"

            rows = conn.execute(text(query), params).fetchall()

            photo_list = []
            for r in rows:
                file_name = os.path.basename(r[3]) if r[3] else ""
                thumb_name = os.path.basename(r[4]) if r[4] else file_name

                file_url = f"/photos/file/{file_name}" if file_name else ""
                thumb_url = f"/photos/file/{thumb_name}" if thumb_name else file_url

                photo_list.append({
                    "id": str(r[0]),
                    "user_id": str(r[1]),
                    "trip_id": str(r[2]) if r[2] else None,
                    "file_url": file_url,
                    "thumbnail_url": thumb_url,
                    "lat": float(r[5]) if r[5] is not None else None,
                    "lng": float(r[6]) if r[6] is not None else None,
                    "captured_at": r[7].isoformat() if r[7] else None,
                    "caption": r[8],
                    "tagged_day_schedule_id": str(r[9]) if r[9] else None,
                    "original_filename": r[10]
                })

            return jsonify({"status": "success", "photos": photo_list})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500


@app.route("/api/generate_summary", methods=["POST"])
def api_generate_summary():
    """
    Generate a visual trip summary.

    Expects JSON with trip_id and optional format.
    """
    data = request.get_json()
    user_id = session.get("user_id")
    if not user_id:
        return jsonify({"status": "error", "message": "Not authenticated"}), 401

    trip_id = data.get("trip_id")

    if not trip_id:
        return jsonify({
            "status": "error",
            "message": "trip_id is required.",
        }), 400

    format = data.get("format", "image_slideshow")
    music_track = data.get("music_track")
    lang = data.get("lang", "pl")

    result = generate_summary(
        trip_id=trip_id,
        format=format,
        music_track=music_track,
        lang=lang,
    )

    # Convert absolute paths to frontend-accessible relative URLs
    if result["status"] == "success":
        if result.get("file_url"):
            result["file_url"] = f"/summaries/{os.path.basename(result['file_url'])}"
        if result.get("all_slides"):
            result["all_slides"] = [
                f"/summaries/{os.path.basename(path)}"
                for path in result["all_slides"]
            ]

    return jsonify(result)
 
 
@app.route("/api/music/moods", methods=["GET"])
def api_get_music_moods():
    """
    Pobierz listę dostępnych nastrojów muzycznych Audius oraz utwory dla wybranego nastroju.

    Query params:
        mood (str): Klucz nastroju (np. 'roadtrip', 'lofi', 'acoustic', 'nature', 'summer', 'jazz', 'offline')
        limit (int): Maksymalna liczba utworów (domyślnie 8)
    """
    mood = request.args.get("mood", "roadtrip")
    try:
        limit = int(request.args.get("limit", 8))
    except (ValueError, TypeError):
        limit = 8

    presets = []
    for k, v in audius_service.MOOD_PRESETS.items():
        presets.append({
            "key": k,
            "label": v["label"],
            "icon": v["icon"],
            "genre": v["genre"],
        })
    presets.append({
        "key": "offline",
        "label": "Dźwięki Offline (Proceduralne)",
        "icon": "📁",
        "genre": "Offline Local",
    })

    mood_data = audius_service.get_mood_tracks(mood=mood, limit=limit)
    return jsonify({
        "status": "success",
        "presets": presets,
        "current_mood": mood_data,
    })


@app.route("/api/music/search", methods=["GET"])
def api_search_music():
    """
    Wyszukaj utwory w serwisie Audius na podstawie zapytania tekstowego.

    Query params:
        q (str): Wyszukiwana fraza
        limit (int): Maksymalna liczba utworów (domyślnie 12)
    """
    query = request.args.get("q", "").strip()
    try:
        limit = int(request.args.get("limit", 12))
    except (ValueError, TypeError):
        limit = 12

    if not query:
        return jsonify({"status": "success", "tracks": []})

    tracks = audius_service.search_tracks(query=query, limit=limit)
    return jsonify({
        "status": "success",
        "query": query,
        "tracks": tracks,
    })


@app.route("/api/music/stream/<path:track_id>", methods=["GET"])
def api_stream_music(track_id):
    """
    Pobierz lub strumieniuj utwór muzyczny (z cache lub z Audius).

    Obsługuje również identyfikatory lokalne offline.
    """
    clean_id = track_id.replace("audius:", "").strip()

    # Sprawdź czy utwór jest w cache lub czy można go pobrać
    cached = audius_service.download_and_cache_track(clean_id)
    if cached and os.path.exists(cached):
        return send_file(cached, mimetype="audio/mpeg")

    return jsonify({
        "status": "error",
        "message": "Track stream unavailable",
    }), 404


@app.route("/api/memories", methods=["GET"])
def api_get_memories():
    """
    Pobierz galerię wygenerowanych Memories dla zalogowanego użytkownika.

    Zwraca listę trip_summaries posortowanych od najnowszych,
    wzbogaconą o tytuł i daty wycieczki.
    """
    user_id = session.get("user_id")
    if not user_id:
        return jsonify({"status": "error", "message": "Not authenticated"}), 401

    try:
        engine = get_engine()
        with engine.connect() as conn:
            rows = conn.execute(
                text("""
                    SELECT
                        ts.id,
                        ts.trip_id,
                        ts.format,
                        ts.file_url,
                        ts.music_track,
                        ts.generated_at,
                        t.title  AS trip_title,
                        t.start_date,
                        t.end_date
                    FROM trip_summaries ts
                    LEFT JOIN trips t ON ts.trip_id = t.id
                    WHERE ts.user_id = :uid
                    ORDER BY ts.generated_at DESC
                """),
                {"uid": user_id},
            ).fetchall()

        memories = []
        for row in rows:
            raw_url = row[3] or ""
            # Konwertuj ścieżkę absolutną na URL dostępny przez przeglądarkę
            if raw_url.startswith("/") or (len(raw_url) > 1 and raw_url[1] == ":"):
                web_url = f"/summaries/{os.path.basename(raw_url)}"
            else:
                web_url = raw_url

            # Sprawdź, czy plik faktycznie istnieje na dysku
            summary_dir = os.path.join(
                os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                ".tmp", "summaries",
            )
            file_exists = os.path.exists(
                os.path.join(summary_dir, os.path.basename(raw_url))
            )

            memories.append({
                "id": str(row[0]),
                "trip_id": str(row[1]) if row[1] else None,
                "format": row[2],
                "file_url": web_url,
                "music_track": row[4],
                "generated_at": str(row[5]) if row[5] else None,
                "trip_title": row[6] or "Nieznana wycieczka",
                "start_date": str(row[7]) if row[7] else None,
                "end_date": str(row[8]) if row[8] else None,
                "file_exists": file_exists,
            })

        return jsonify({"status": "success", "memories": memories})

    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500


@app.route("/api/transcribe", methods=["POST"])
def api_transcribe():
    """
    Transcribe uploaded audio file (from MediaRecorder or voice input)
    using OpenAI Whisper API with graceful fallback.
    """
    lang = request.form.get("lang", "pl")

    if "file" not in request.files and "audio" not in request.files:
        if lang == "de":
            msg = "Keine Audiodatei in der Anfrage."
        elif lang == "en":
            msg = "No audio file in request."
        else:
            msg = "Brak pliku audio w żądaniu."
        return jsonify({"status": "error", "message": msg}), 200

    audio_file = request.files.get("file") or request.files.get("audio")

    if not audio_file or audio_file.filename == "":
        if lang == "de":
            msg = "Leere Audiodatei."
        elif lang == "en":
            msg = "Empty audio file."
        else:
            msg = "Pusty plik audio."
        return jsonify({"status": "error", "message": msg}), 200

    temp_dir = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        ".tmp"
    )
    os.makedirs(temp_dir, exist_ok=True)

    filename = f"voice_{uuid.uuid4().hex}.webm"
    temp_path = os.path.join(temp_dir, filename)

    try:
        audio_file.save(temp_path)
        file_size = os.path.getsize(temp_path)
        print(f"[Transcribe] Saved temp audio file: {temp_path} ({file_size} bytes)", flush=True)

        if file_size < 300:
            if lang == "de":
                msg = "Die Aufnahme ist zu kurz oder enthält keinen Ton."
            elif lang == "en":
                msg = "Recording is too short or contains no audio."
            else:
                msg = "Nagranie jest za krótkie lub nie zawiera dźwięku."
            return jsonify({"status": "error", "message": msg}), 200

        client = get_client()

        text = ""
        try:
            with open(temp_path, "rb") as f:
                transcript = client.audio.transcriptions.create(
                    model="whisper-1",
                    file=f,
                    language=lang if lang in ["pl", "de", "en"] else "pl"
                )
            text = transcript.text.strip() if transcript and hasattr(transcript, "text") else ""
            print(f"[Transcribe Success] Result: '{text}'", flush=True)
        except Exception as err:
            print(f"[Whisper API Exception] {type(err).__name__}: {err}", flush=True)

        if text:
            return jsonify({
                "status": "success",
                "text": text
            })
        else:
            if lang == "de":
                msg = "Keine Sprache in der Aufnahme erkannt. Bitte versuche es lauter."
            elif lang == "en":
                msg = "No speech detected in recording. Please try speaking louder."
            else:
                msg = "Nie wykryto mowy w nagraniu. Spróbuj powtórzyć głośniej."
            return jsonify({
                "status": "error",
                "message": msg
            }), 200

    except Exception as e:
        print(f"[Transcribe Server Error] {type(e).__name__}: {e}", flush=True)
        if lang == "de":
            msg = f"Fehler bei der Audioverarbeitung: {str(e)}"
        elif lang == "en":
            msg = f"Audio processing error: {str(e)}"
        else:
            msg = f"Błąd przetwarzania dźwięku: {str(e)}"
        return jsonify({"status": "error", "message": msg}), 200
    finally:
        if os.path.exists(temp_path):
            try:
                os.remove(temp_path)
            except Exception:
                pass


@app.route("/api/tts/speak", methods=["POST"])
def api_tts_speak():
    """
    Generate natural human neural speech audio for Volkswagen Sniffer using ElevenLabs / OpenAI TTS.
    Returns audio/mpeg with caching.
    """
    try:
        from tools.tts_service import generate_speech_audio

        data = request.get_json(silent=True) or {}
        text = data.get("text", "")
        lang = data.get("lang", "pl")
        voice = data.get("voice", "onyx")
        eleven_voice_id = data.get("eleven_voice_id")

        if not text:
            return jsonify({"status": "error", "message": "Text is required"}), 400

        audio_bytes = generate_speech_audio(
            text=text,
            lang=lang,
            voice=voice,
            eleven_voice_id=eleven_voice_id,
        )
        if not audio_bytes:
            return jsonify({"status": "error", "message": "Failed to generate speech"}), 500

        return Response(audio_bytes, mimetype="audio/mpeg")

    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500


# ── 3D Sniffer voice: proxy to the local HeadTTS server ────────
# The AVW Sniffer module calls POST /tts/v1/synthesize on this origin (no CORS); HeadTTS
# (Kokoro, English) runs next to Flask, see README "3D Sniffer".
HEADTTS_URL = os.getenv("HEADTTS_URL", "http://127.0.0.1:8882").rstrip("/")


@app.route("/tts/v1/synthesize", methods=["POST"])
def tts_proxy():
    """Forward a synthesis request to HeadTTS and return its JSON (audio + word/viseme timings)."""
    import urllib.error
    import urllib.request

    body = request.get_data()
    if len(body) > 20_000:
        return jsonify({"error": "Request too large."}), 413
    req = urllib.request.Request(
        f"{HEADTTS_URL}/v1/synthesize",
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=60) as upstream:
            return Response(upstream.read(), status=upstream.status, mimetype="application/json")
    except urllib.error.HTTPError as e:
        return Response(e.read(), status=e.code, mimetype="application/json")
    except (urllib.error.URLError, TimeoutError) as e:
        return jsonify({"error": f"HeadTTS is not reachable at {HEADTTS_URL}: {e}"}), 502


@app.route("/assets/audio/<path:filename>")
def serve_audio_file(filename):
    """Serve predefined audio track files."""
    audio_dir = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        "frontend", "assets", "audio"
    )
    return send_from_directory(audio_dir, filename)


# ── Server Entry Point ────────────────────────────────────────
if __name__ == "__main__":
    print("🚐 VW California AI Trip Planner — Web Server")
    print("=" * 55)
    print(f"  Dashboard: http://localhost:5050")
    print(f"  API Base:  http://localhost:5050/api")
    print("=" * 55)
    print()

    port = int(os.getenv("PORT", 5050))
    app.run(
        host="0.0.0.0",
        port=port,
        debug=False,
        use_reloader=False,
    )

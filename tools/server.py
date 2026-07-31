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
from dotenv import load_dotenv
from flask import Flask, render_template, request, jsonify, send_from_directory, session
from flask_cors import CORS
from sqlalchemy import text
from werkzeug.security import generate_password_hash, check_password_hash
import uuid

from navigation.chat_handler import create_chat_session, send_message
from tools.search_campings import search_campings
from tools.plan_route import plan_route
from tools.extract_exif import store_photo, pin_photo_location
from tools.generate_summary import generate_summary
from tools.db import get_engine
from tools.maps_client import get_client as get_maps_client
from tools.openai_client import get_client
from tools.suggest_attractions import suggest_attractions
from navigation.dispatcher import _recalculate_day_route

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


def _sanitize_for_json(obj):
    import decimal
    if isinstance(obj, decimal.Decimal):
        return float(obj)
    if isinstance(obj, dict):
        return {k: _sanitize_for_json(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_sanitize_for_json(item) for item in obj]
    return obj


def _get_trip_data(trip_id):
    """Fetch trip and schedules from DB to return to frontend."""
    import json
    engine = get_engine()
    with engine.connect() as conn:
        trip_row = conn.execute(
            text("SELECT id, user_id, title, origin_label, origin_lat, origin_lng, destination_label, destination_lat, destination_lng, start_date, end_date, status FROM trips WHERE id = :tid"),
            {"tid": trip_id}
        ).fetchone()

        if not trip_row:
            return None

        trip = {
            "id": str(trip_row[0]),
            "user_id": str(trip_row[1]) if trip_row[1] else None,
            "title": trip_row[2],
            "origin": {"label": trip_row[3], "lat": float(trip_row[4]) if trip_row[4] is not None else 0.0, "lng": float(trip_row[5]) if trip_row[5] is not None else 0.0},
            "destination": {"label": trip_row[6], "lat": float(trip_row[7]) if trip_row[7] is not None else 0.0, "lng": float(trip_row[8]) if trip_row[8] is not None else 0.0},
            "start_date": str(trip_row[9]) if trip_row[9] else "",
            "end_date": str(trip_row[10]) if trip_row[10] else "",
            "status": trip_row[11]
        }

        schedules_rows = conn.execute(
            text("SELECT id, day_number, schedule_date, driving_hours, driving_km, waypoints, route_polyline FROM daily_schedules WHERE trip_id = :tid ORDER BY day_number ASC"),
            {"tid": trip_id}
        ).fetchall()

        is_round_trip = (
            (trip.get("origin", {}).get("label") and trip.get("destination", {}).get("label") and trip["origin"]["label"] == trip["destination"]["label"]) or
            (trip.get("origin", {}).get("lat") == trip.get("destination", {}).get("lat") and trip.get("origin", {}).get("lng") == trip.get("destination", {}).get("lng"))
        )

        schedules = []
        num_schedules = len(schedules_rows)
        for r in schedules_rows:
            wps = r[5] if isinstance(r[5], list) else json.loads(r[5] or "[]")
            overnight = next((w for w in reversed(wps) if w.get("type") == "camping"), None)
            day_num = r[1]
            is_return = is_round_trip and num_schedules > 1 and (day_num > (num_schedules / 2))
            
            overnight_opts = []
            if day_num < num_schedules:
                target_point = overnight or (wps[-1] if wps else None)
                if target_point and target_point.get("lat") and target_point.get("lng"):
                    c_res = search_campings(
                        lat=target_point["lat"],
                        lng=target_point["lng"],
                        radius_km=30,
                        limit=3
                    )
                    if c_res.get("results"):
                        overnight_opts = c_res["results"]

            schedules.append({
                "id": str(r[0]),
                "day_number": day_num,
                "date": str(r[2]) if r[2] else "",
                "driving_hours": float(r[3]) if r[3] is not None else 0.0,
                "driving_km": float(r[4]) if r[4] is not None else 0.0,
                "waypoints": wps,
                "overnight_camping": overnight,
                "overnight_options": overnight_opts,
                "route_polyline": r[6],
                "is_return": is_return
            })

        result_payload = {
            "trip": trip,
            "daily_schedules": schedules,
            "total_driving_hours": sum(float(s["driving_hours"] or 0) for s in schedules),
            "total_driving_km": sum(float(s["driving_km"] or 0) for s in schedules)
        }

        return _sanitize_for_json(result_payload)


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


def get_chat_session(user_id=None, trip_id=None, lang="pl"):
    """
    Get or create a per-user chat session held in SERVER memory
    (`_CHAT_SESSIONS`). The conversation history + slot_state live here
    (never in the Flask cookie), so multi-turn chat works reliably.

    Returns:
        dict: Active chat session (with live client/tools attached).
    """
    if not user_id:
        # Anonymous/MVP usage: fall back to a single transient key.
        user_id = "anon"

    print(f"[get_chat_session] user_id={user_id!r} lang={lang!r} known={user_id in _CHAT_SESSIONS} keys={list(_CHAT_SESSIONS.keys())}", flush=True)

    if user_id not in _CHAT_SESSIONS:
        sess = create_chat_session(trip_id=trip_id, lang=lang)
        sess["user_id"] = user_id
        sess["slot_state"] = None
        sess["active_trip_id"] = session.get("active_trip_id")
        _CHAT_SESSIONS[user_id] = sess
    else:
        sess = _CHAT_SESSIONS[user_id]
        sess["user_id"] = user_id
        sess["lang"] = lang or sess.get("lang", "pl")
        if trip_id:
            sess["trip_id"] = trip_id
        # Re-sync the active_trip_id from the Flask session if present.
        if session.get("active_trip_id"):
            sess["active_trip_id"] = session["active_trip_id"]

    return sess


# ── Frontend Route ────────────────────────────────────────────
@app.route("/")
def index():
    """Serve the main dashboard."""
    return render_template(
        "index.html",
        google_maps_key=os.getenv("GOOGLE_MAPS_API_KEY", ""),
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


@app.route("/photos/file/<path:filename>")
def serve_photo_file(filename):
    """Serve uploaded photos or thumbnails, converting HEIC/HEIF to JPEG for browser support."""
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
                return send_from_directory(upload_dir, jpg_name, mimetype="image/jpeg")

        return send_from_directory(os.path.dirname(target_path), os.path.basename(target_path))

    return jsonify({"status": "error", "message": "File not found"}), 404


# ── API Routes ────────────────────────────────────────────────

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

    if not user_message:
        return jsonify({
            "status": "error",
            "message": "Empty message.",
        }), 400

    # Pass the logged-in user_id (and active trip, if known) into a
    # per-user chat session so messages persist and trips are linked.
    user_id = session.get("user_id")
    active_trip_id = session.get("active_trip_id")
    print(f"[api_chat] user_id={user_id!r} lang={lang!r} active_trip_id={active_trip_id!r} msg={user_message[:30]!r}")
    chat = get_chat_session(user_id=user_id, trip_id=active_trip_id, lang=lang)
    chat["lang"] = lang
    result = send_message(chat, user_message, trip_id=active_trip_id)

    # Persist the running slot_state + active_trip_id in server memory
    # (never the cookie) so the next request can merge with it and the
    # route stays in context. Also mirror active_trip_id into the Flask
    # session for cross-endpoint use (e.g. /api/trip lookups).
    uid = user_id or "anon"
    if uid in _CHAT_SESSIONS:
        _CHAT_SESSIONS[uid]["slot_state"] = result.get("slot_state")
        if chat.get("active_trip_id"):
            _CHAT_SESSIONS[uid]["active_trip_id"] = chat["active_trip_id"]
            session["active_trip_id"] = chat["active_trip_id"]

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

    try:
        engine = get_engine()
        with engine.begin() as conn:
            schedule_row = conn.execute(
                text("SELECT id, waypoints FROM daily_schedules WHERE trip_id = :tid AND day_number = :day"),
                {"tid": trip_id, "day": day_number}
            ).fetchone()

            if not schedule_row:
                return jsonify({"status": "error", "message": "Day schedule not found"}), 404

            schedule_id = schedule_row[0]
            waypoints = schedule_row[1] or []

            if not waypoints:
                return jsonify({"status": "error", "message": "No waypoints found for this day"}), 400

            # Replace the last waypoint (which is the overnight camping or destination)
            new_wp = {
                "order": len(waypoints) - 1,
                "type": "camping",
                "label": camping.get("name", "Camping"),
                "lat": camping.get("lat"),
                "lng": camping.get("lng"),
                "place_id": camping.get("place_id"),
                "notes": "User selected camping"
            }
            waypoints[-1] = new_wp

            # Update db and recalculate
            update_done = _recalculate_day_route(conn, schedule_id, waypoints)
            if not update_done:
                conn.execute(
                    text("UPDATE daily_schedules SET waypoints = CAST(:wps AS jsonb), overnight_camping_id = :cid WHERE id = :sid"),
                    {"wps": json.dumps(waypoints), "cid": camping.get("id"), "sid": str(schedule_id)}
                )

            # Update start location of next day if day_number + 1 exists
            next_day_row = conn.execute(
                text("SELECT id, waypoints FROM daily_schedules WHERE trip_id = :tid AND day_number = :day"),
                {"tid": trip_id, "day": day_number + 1}
            ).fetchone()
            if next_day_row:
                next_sid = next_day_row[0]
                next_wps = next_day_row[1] or []
                if isinstance(next_wps, str):
                    next_wps = json.loads(next_wps)
                if next_wps:
                    next_wps[0] = {
                        "order": 0,
                        "type": "start",
                        "label": camping.get("name", "Start"),
                        "lat": camping.get("lat"),
                        "lng": camping.get("lng")
                    }
                    _recalculate_day_route(conn, next_sid, next_wps)

        trip_data = _get_trip_data(trip_id)
        return jsonify({"status": "success", "message": "Camping selected and route updated.", "trip_data": trip_data})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500


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
        limit_per_day (int): Max results per day (default 5).
        sample_every_km (int): Sampling interval in km (default 80).
    """
    preferences = request.args.get("preferences", None)
    limit_per_day = int(request.args.get("limit_per_day", 5))
    # Default sample interval raised to 80 km to reduce API call count
    sample_every_km = float(request.args.get("sample_every_km", 80))

    # Build a cache key
    cache_key = f"{trip_id}:{preferences or ''}:{limit_per_day}:{int(sample_every_km)}"
    if cache_key in _ATTRACTIONS_CACHE:
        print(f"[api_get_attractions] Cache HIT for {cache_key}", flush=True)
        return jsonify(_ATTRACTIONS_CACHE[cache_key])

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

    print(f"[api_get_attractions] Done — status={result.get('status')} "
          f"days={len(result.get('attractions_by_day', {}))}", flush=True)
    return jsonify(result)


@app.route("/api/place_details/<place_id>", methods=["GET"])
def api_place_details(place_id):
    """Fetch details from Google Places API."""
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

    # Optional trip_id from frontend
    trip_id = request.form.get("trip_id")

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
    Manually pin a photo that lacked GPS data to a specific location.

    Expects JSON with photo_id, lat, lng.
    """
    user_id = session.get("user_id")
    if not user_id:
        return jsonify({"status": "error", "message": "Not authenticated"}), 401

    data = request.get_json()
    photo_id = data.get("photo_id")
    lat = data.get("lat")
    lng = data.get("lng")

    if not photo_id or lat is None or lng is None:
        return jsonify({
            "status": "error",
            "message": "photo_id, lat, and lng are required.",
        }), 400

    result = pin_photo_location(photo_id, lat, lng, user_id)
    return jsonify(result)


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

    result = generate_summary(
        trip_id=trip_id,
        format=format,
        music_track=music_track,
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
    if "file" not in request.files and "audio" not in request.files:
        return jsonify({"status": "error", "message": "Brak pliku audio w żądaniu."}), 200

    audio_file = request.files.get("file") or request.files.get("audio")
    lang = request.form.get("lang", "pl")

    if not audio_file or audio_file.filename == "":
        return jsonify({"status": "error", "message": "Pusty plik audio."}), 200

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
            return jsonify({"status": "error", "message": "Nagranie jest za krótkie lub nie zawiera dźwięku."}), 200

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
            return jsonify({
                "status": "error",
                "message": "Nie wykryto mowy w nagraniu. Spróbuj powtórzyć głośniej."
            }), 200

    except Exception as e:
        print(f"[Transcribe Server Error] {type(e).__name__}: {e}", flush=True)
        return jsonify({"status": "error", "message": f"Błąd przetwarzania dźwięku: {str(e)}"}), 200
    finally:
        if os.path.exists(temp_path):
            try:
                os.remove(temp_path)
            except Exception:
                pass


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

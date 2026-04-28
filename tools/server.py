"""
Flask API server for the VW California AI Trip Planner.

Serves the frontend dashboard and provides REST API endpoints
for chat, camping search, route planning, and photo upload.

Usage:
    python3 -m tools.server
"""

import os
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
from tools.extract_exif import store_photo
from tools.generate_summary import generate_summary
from tools.db import get_engine

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

# Global chat session (per-server instance for MVP)
chat_session = None

# User ID for MVP (single-user mode) - REMOVED
# DEFAULT_USER_ID = "a1b2c3d4-e5f6-7890-abcd-ef1234567890"

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


@app.route("/api/trip/<trip_id>", methods=["GET"])
def api_get_trip(trip_id):
    """Get details for a specific trip."""
    user_id = session.get("user_id")
    if not user_id:
        return jsonify({"status": "error", "message": "Not authenticated"}), 401
    
    # Implementation placeholder or fetch from DB
    return jsonify({"status": "success", "trip_id": trip_id})



def get_chat_session():
    """
    Get or create the global chat session.

    Returns:
        dict: Active chat session.
    """
    global chat_session
    if chat_session is None:
        chat_session = create_chat_session()
    return chat_session


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


# ── API Routes ────────────────────────────────────────────────

@app.route("/api/chat", methods=["POST"])
def api_chat():
    """
    Handle a chat message from the user.

    Sends the message through the Gemini AI with tool calling,
    and returns the assistant's response.
    """
    data = request.get_json()
    user_message = data.get("message", "").strip()

    if not user_message:
        return jsonify({
            "status": "error",
            "message": "Empty message.",
        }), 400

    session = get_chat_session()
    result = send_message(session, user_message)

    return jsonify(result)


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
        user_id=DEFAULT_USER_ID,
        title=data.get("title"),
    )

    return jsonify(result)


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

    result = generate_summary(
        trip_id=trip_id,
        format=format,
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


# ── Server Entry Point ────────────────────────────────────────
if __name__ == "__main__":
    print("🚐 VW California AI Trip Planner — Web Server")
    print("=" * 55)
    print(f"  Dashboard: http://localhost:5050")
    print(f"  API Base:  http://localhost:5050/api")
    print("=" * 55)
    print()

    app.run(
        host="0.0.0.0",
        port=5050,
        debug=True,
    )

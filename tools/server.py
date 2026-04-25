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
from flask import Flask, render_template, request, jsonify
from flask_cors import CORS

from navigation.chat_handler import create_chat_session, send_message
from tools.search_campings import search_campings
from tools.plan_route import plan_route
from tools.extract_exif import store_photo

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

# User ID for MVP (single-user mode)
DEFAULT_USER_ID = "a1b2c3d4-e5f6-7890-abcd-ef1234567890"


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

    # Process the photo
    result = store_photo(
        filepath=filepath,
        user_id=DEFAULT_USER_ID,
    )

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

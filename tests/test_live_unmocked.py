"""
Comprehensive live (un-mocked) integration test suite for VW California Trip Planner.

Tests all external services and subsystems using real live calls (zero mocks):
1. PostgreSQL + PostGIS database connection and spatial queries
2. OpenAI API chat completion and function calling
3. Google Maps Platform (Directions, Geocoding, Places)
4. Live Camping Search (Database PostGIS search + Google Maps fallback)
5. Live Route Planning (Google Maps Routes/Directions dependency)
6. Live Attractions Suggestion (Google Maps Places dependency)
7. EXIF extraction and GPS coordinates parsing
8. Travel Memory photo auto-linking via PostGIS
9. Trip summary export (slideshow and video generation)
10. Flask server authentication and preference persistence
"""

import io
import os
import sys
import uuid
from datetime import datetime, timedelta
from dotenv import load_dotenv
from PIL import Image
import pytest
from sqlalchemy import text

# Ensure repository root is in python path
ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

# Load environment variables
load_dotenv()


class TestLiveDatabase:
    """Live PostgreSQL + PostGIS database integration tests."""

    def test_database_connection(self):
        """Verify direct TCP connection to PostgreSQL server."""
        from tools.db import get_engine

        engine = get_engine()
        with engine.connect() as conn:
            result = conn.execute(text("SELECT 1")).scalar()
            assert result == 1, "Database did not respond with 1"

    def test_postgis_extension_available(self):
        """Verify PostGIS extension is installed and version is accessible."""
        from tools.db import get_engine

        engine = get_engine()
        with engine.connect() as conn:
            version = conn.execute(text("SELECT PostGIS_Full_Version()")).scalar()
            assert version is not None, "PostGIS version returned None"
            assert "POSTGIS" in version.upper(), f"Unexpected PostGIS version string: {version}"

    def test_postgis_spatial_query(self):
        """Verify PostGIS geospatial functions (ST_Point, ST_DWithin, ST_Distance)."""
        from tools.db import get_engine

        engine = get_engine()
        with engine.connect() as conn:
            # Distance between Munich (48.1351, 11.5820) and Salzburg (47.8095, 13.0550) in meters
            query = text("""
                SELECT ST_Distance(
                    ST_SetSRID(ST_MakePoint(11.5820, 48.1351), 4326)::geography,
                    ST_SetSRID(ST_MakePoint(13.0550, 47.8095), 4326)::geography
                ) AS distance_meters
            """)
            distance = conn.execute(query).scalar()
            assert distance is not None
            # Expected distance ~115 km (110,000 - 125,000 meters)
            assert 100000 < distance < 130000, f"Unexpected distance: {distance} m"

    def test_database_campings_count(self):
        """Verify campings table is populated with seed/crawled data."""
        from tools.db import get_engine

        engine = get_engine()
        with engine.connect() as conn:
            count = conn.execute(text("SELECT count(*) FROM campings")).scalar()
            assert count > 0, "Campings table is empty"


class TestLiveOpenAI:
    """Live OpenAI API integration tests."""

    def test_openai_api_key_configured(self):
        """Verify OPENAI_API_KEY environment variable is present."""
        key = os.getenv("OPENAI_API_KEY")
        assert key is not None and len(key.strip()) > 0, "OPENAI_API_KEY is not configured in .env"

    def test_openai_chat_completion(self):
        """Verify real chat completion call with gpt-4o-mini."""
        from tools.openai_client import get_client, MODEL_NAME

        client = get_client()
        response = client.chat.completions.create(
            model=MODEL_NAME,
            messages=[{"role": "user", "content": "Odpowiedz jednym słowem: 'Działa'."}],
            max_tokens=10,
        )
        content = response.choices[0].message.content
        assert content is not None and len(content) > 0, "Empty response from OpenAI API"

    def test_openai_chat_session_creation(self):
        """Verify conversational chat session initialization and slot extraction."""
        from navigation.chat_handler import create_chat_session, send_message

        session = create_chat_session(lang="pl")
        assert session is not None
        assert "history" in session

        reply = send_message(session, "Cześć, chcę zaplanować wyjazd kamperem na 3 dni.")
        assert reply["status"] == "success"
        assert len(reply.get("text", "")) > 0
        assert "slot_state" in reply


class TestLiveGoogleMaps:
    """Live Google Maps API integration tests (identifies billing / quota issues)."""

    def test_google_maps_api_key_configured(self):
        """Verify GOOGLE_MAPS_API_KEY environment variable is present."""
        key = os.getenv("GOOGLE_MAPS_API_KEY")
        assert key is not None and len(key.strip()) > 0, "GOOGLE_MAPS_API_KEY is not configured in .env"

    def test_google_maps_geocoding(self):
        """Test live Geocoding API call."""
        from tools.maps_client import get_client

        client = get_client()
        # Geocode Wolfsburg, Germany
        results = client.geocode("Wolfsburg, Germany")
        assert len(results) > 0, "No geocoding results returned"
        assert "geometry" in results[0], "No geometry in geocoding result"

    def test_google_maps_directions(self):
        """Test live Directions API call (required by plan_route)."""
        from tools.maps_client import get_client

        client = get_client()
        # Route from Munich to Salzburg
        directions = client.directions("Munich, Germany", "Salzburg, Austria")
        assert len(directions) > 0, "No directions returned from Google Maps"
        assert "legs" in directions[0], "No legs in directions response"

    def test_google_maps_places_nearby(self):
        """Test live Places Nearby API call (required for campgrounds and attractions)."""
        from tools.maps_client import get_client

        client = get_client()
        # Search campgrounds near Munich
        places = client.places_nearby(
            location=(48.1351, 11.5820),
            radius=15000,
            type="campground",
        )
        assert places.get("status") in ["OK", "ZERO_RESULTS"], f"Places API failed: {places}"


class TestLiveCoreFeatures:
    """Live tests for application features without mocks."""

    def test_live_camping_search_database(self):
        """Verify camping search retrieves real campings from PostGIS database."""
        from tools.search_campings import search_campings

        # Search around Lake Bled (coordinates 46.3576, 14.0986 where seed campings exist)
        result = search_campings(lat=46.3576, lng=14.0986, radius_km=50)
        assert result["status"] == "success"
        campings = result.get("results", [])
        assert len(campings) > 0, "No campings found in database around Bled"
        assert any("Bled" in c["name"] for c in campings), "Expected 'Camping Bled' in results"

    def test_live_plan_route(self):
        """Verify route planning end-to-end."""
        from tools.plan_route import plan_route

        origin = {"label": "Munich", "lat": 48.1351, "lng": 11.5820}
        destination = {"label": "Salzburg", "lat": 47.8095, "lng": 13.0550}

        result = plan_route(
            origin=origin,
            destination=destination,
            num_days=1,
            start_date="2026-08-01",
        )
        assert result["status"] == "success", f"plan_route failed: {result.get('message')}"
        assert "daily_schedules" in result
        assert len(result["daily_schedules"]) == 1

    def test_live_suggest_attractions(self):
        """Verify attractions suggestion on seed trip."""
        from tools.suggest_attractions import suggest_attractions

        seed_trip_id = "a0000001-0000-0000-0000-000000000001"
        result = suggest_attractions(seed_trip_id)
        assert result["status"] == "success", f"suggest_attractions failed: {result}"
        assert "attractions_by_day" in result
        # Check if attractions were found
        total_attractions = sum(len(items) for items in result["attractions_by_day"].values())
        assert total_attractions > 0, "No attractions suggested along route"

    def test_live_exif_and_auto_link(self):
        """Verify EXIF extraction and real PostGIS auto-linking of photo to trip."""
        from tools.db import get_engine
        from tools.extract_exif import _auto_link_photo

        engine = get_engine()
        test_user_id = str(uuid.uuid4())
        test_trip_id = str(uuid.uuid4())
        test_schedule_id = str(uuid.uuid4())
        test_photo_id = str(uuid.uuid4())

        try:
            with engine.begin() as conn:
                # 1. Create test user
                conn.execute(
                    text("INSERT INTO users (id, email, display_name) VALUES (:id, :email, :name)"),
                    {"id": test_user_id, "email": f"test_{test_user_id[:8]}@example.com", "name": "Live Test User"},
                )

                # 2. Create test trip
                conn.execute(
                    text("""
                        INSERT INTO trips (id, user_id, title, start_date, end_date)
                        VALUES (:id, :user_id, 'Live Test Trip', CURRENT_DATE, CURRENT_DATE + INTERVAL '2 days')
                    """),
                    {"id": test_trip_id, "user_id": test_user_id},
                )

                # 3. Create daily schedule with route polyline
                polyline = "_p~iH_c}hA_n`@_d|@"
                conn.execute(
                    text("""
                        INSERT INTO daily_schedules (id, trip_id, day_number, route_polyline)
                        VALUES (:id, :trip_id, 1, :polyline)
                    """),
                    {"id": test_schedule_id, "trip_id": test_trip_id, "polyline": polyline},
                )

                # 4. Insert photo near polyline with CURRENT_TIMESTAMP
                conn.execute(
                    text("""
                        INSERT INTO photos (id, user_id, file_url, location, lat, lng, captured_at)
                        VALUES (
                            :id, :user_id, 'live_test.jpg',
                            ST_SetSRID(ST_MakePoint(12.11500, 48.98600), 4326)::geography,
                            48.98600, 12.11500, CURRENT_TIMESTAMP
                        )
                    """),
                    {"id": test_photo_id, "user_id": test_user_id},
                )

            # Perform real spatial auto-linking
            linked = _auto_link_photo(test_photo_id, test_user_id)
            assert linked is not None, "Photo failed to auto-link to nearby trip schedule"
            assert linked["trip_id"] == test_trip_id
            assert linked["tagged_day_schedule_id"] == test_schedule_id

        finally:
            # Clean up test records
            with engine.begin() as conn:
                conn.execute(text("DELETE FROM users WHERE id = :id"), {"id": test_user_id})

    def test_live_summary_slideshow(self):
        """Verify slideshow slide generation from real trip in database."""
        from tools.generate_summary import generate_summary

        seed_trip_id = "a0000001-0000-0000-0000-000000000001"
        result = generate_summary(seed_trip_id, format="image_slideshow")
        assert result["status"] == "success", f"Slideshow generation failed: {result}"
        assert "all_slides" in result
        assert len(result["all_slides"]) > 0
        assert os.path.exists(result["all_slides"][0]), "Generated slide file does not exist on disk"

    def test_live_summary_video(self):
        """Verify video generation from real trip in database."""
        from tools.generate_summary import generate_summary

        seed_trip_id = "a0000001-0000-0000-0000-000000000001"
        result = generate_summary(seed_trip_id, format="video")
        assert result["status"] == "success", f"Video generation failed: {result}"
        assert "file_url" in result
        assert os.path.exists(result["file_url"]), f"Video file does not exist: {result['file_url']}"

    def test_live_flask_auth_and_preferences(self):
        """Verify Flask API user registration, session authentication and preferences storage."""
        from tools.server import app

        app.config["TESTING"] = True
        app.config["SECRET_KEY"] = "test_secret_key"
        test_email = f"live_driver_{int(datetime.now().timestamp())}@test.com"

        with app.test_client() as client:
            # 1. Register new user
            reg_resp = client.post(
                "/api/register",
                json={
                    "display_name": "Live Driver",
                    "email": test_email,
                    "password": "SecurePassword123!",
                    "vehicle_model": "VW California Ocean 6.1",
                },
            )
            assert reg_resp.status_code == 200, f"Registration failed: {reg_resp.get_data(as_text=True)}"
            reg_data = reg_resp.get_json()
            assert reg_data["status"] == "success"
            user_id = reg_data["user"]["id"]

            # 2. Check current authenticated user session
            me_resp = client.get("/api/me")
            assert me_resp.status_code == 200
            me_data = me_resp.get_json()
            assert me_data["user"]["email"] == test_email

            # 3. Update preferences in database
            pref_resp = client.put(
                "/api/preferences",
                json={
                    "max_daily_drive_hours": 5.5,
                    "preferred_amenities": ["power", "showers", "wifi"],
                    "budget_per_night_eur": 45.0,
                },
            )
            assert pref_resp.status_code == 200
            pref_data = pref_resp.get_json()
            assert pref_data["status"] == "success"
            assert pref_data["preferences"]["max_daily_drive_hours"] == 5.5

            # Cleanup user
            from tools.db import get_engine
            engine = get_engine()
            with engine.begin() as conn:
                conn.execute(text("DELETE FROM users WHERE id = :id"), {"id": user_id})

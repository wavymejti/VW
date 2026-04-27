import pytest
import uuid
from datetime import datetime, timedelta
from sqlalchemy import text
from tools.db import get_engine
from tools.extract_exif import _auto_link_photo

def test_auto_link_photo():
    engine = get_engine()
    
    with engine.begin() as conn:
        # Create test user
        user_id = str(uuid.uuid4())
        conn.execute(
            text("INSERT INTO users (id, email, display_name) VALUES (:id, :email, :name)"),
            {"id": user_id, "email": f"{user_id}@test.com", "name": "Test User"}
        )
        
        # Create test trip
        trip_id = str(uuid.uuid4())
        start_date = datetime.now().date()
        conn.execute(
            text("""
                INSERT INTO trips (id, user_id, title, start_date, end_date) 
                VALUES (:id, :user_id, :title, :start_date, :end_date)
            """),
            {
                "id": trip_id, 
                "user_id": user_id, 
                "title": "Test Trip",
                "start_date": start_date,
                "end_date": start_date + timedelta(days=2)
            }
        )
        
        # Create daily schedule with a simple polyline near Munich (48.1351, 11.5820)
        # Polyline for [(48.1351, 11.5820), (48.1400, 11.5900)] is '_p~iH_c}hA_n`@_d|@'
        ds_id = str(uuid.uuid4())
        polyline = "_p~iH_c}hA_n`@_d|@"
        conn.execute(
            text("""
                INSERT INTO daily_schedules (id, trip_id, day_number, route_polyline)
                VALUES (:id, :trip_id, 1, :polyline)
            """),
            {"id": ds_id, "trip_id": trip_id, "polyline": polyline}
        )
        
        # Create a photo near the polyline start point with matching timestamp
        photo_id_match = str(uuid.uuid4())
        conn.execute(
            text("""
                INSERT INTO photos (id, user_id, file_url, location, lat, lng, captured_at)
                VALUES (:id, :user_id, 'test.jpg', ST_SetSRID(ST_MakePoint(12.11500, 48.98600), 4326)::geography, 48.98600, 12.11500, :captured_at)
            """),
            {"id": photo_id_match, "user_id": user_id, "captured_at": datetime.now()}
        )
        
        # Create a photo far away (Berlin: 52.5200, 13.4050)
        photo_id_far = str(uuid.uuid4())
        conn.execute(
            text("""
                INSERT INTO photos (id, user_id, file_url, location, lat, lng, captured_at)
                VALUES (:id, :user_id, 'test2.jpg', ST_SetSRID(ST_MakePoint(13.4050, 52.5200), 4326)::geography, 52.5200, 13.4050, :captured_at)
            """),
            {"id": photo_id_far, "user_id": user_id, "captured_at": datetime.now()}
        )

    # Test auto linking matching photo
    result = _auto_link_photo(photo_id_match, user_id)
    assert result is not None
    assert result["trip_id"] == trip_id
    assert result["tagged_day_schedule_id"] == ds_id
    assert result["day_number"] == 1
    
    # Test auto linking far photo (should fail)
    result_far = _auto_link_photo(photo_id_far, user_id)
    assert result_far is None
    
    # Cleanup
    with engine.begin() as conn:
        conn.execute(text("DELETE FROM users WHERE id = :id"), {"id": user_id})

if __name__ == "__main__":
    test_auto_link_photo()
    print("✅ All auto-linking tests passed!")

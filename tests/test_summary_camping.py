
import os
import pytest
from unittest.mock import patch, MagicMock
from tools.generate_summary import generate_summary, get_trip_summary
from tools.db import get_engine
from sqlalchemy import text
from PIL import Image
import io

@pytest.fixture
def mock_trip_data():
    # Setup a camping with a photo URL in the DB
    engine = get_engine()
    with engine.connect() as conn:
        # Ensure test camping exists
        test_camping_id = "c0000001-0000-0000-0000-000000000001"
        conn.execute(text(f"""
            INSERT INTO campings (id, name, photos, lat, lng, has_power)
            VALUES ('{test_camping_id}', 'Ocean View Camping', ARRAY['https://example.com/camping.jpg'], 48.0, 11.0, true)
            ON CONFLICT (id) DO UPDATE SET photos = ARRAY['https://example.com/camping.jpg'], name = 'Ocean View Camping'
        """))
        # Update the seed trip day 1 to use this camping
        conn.execute(text(f"""
            UPDATE daily_schedules 
            SET overnight_camping_id = '{test_camping_id}'
            WHERE trip_id = 'a0000001-0000-0000-0000-000000000001' AND day_number = 1
        """))
        conn.commit()

def test_summary_with_camping_photo(mock_trip_data):
    # Mock requests.get to return a dummy image
    dummy_img = Image.new('RGB', (500, 300), color=(0, 135, 90)) # VW Green
    img_byte_arr = io.BytesIO()
    dummy_img.save(img_byte_arr, format='JPEG')
    img_bytes = img_byte_arr.getvalue()
    
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.content = img_bytes
    
    # We need the trip data to pass to _generate_slideshow
    trip_data = get_trip_summary("a0000001-0000-0000-0000-000000000001")
    assert trip_data["status"] == "success"
    # The name should be 'Ocean View Camping' now
    assert trip_data["daily_schedules"][0]["camping_name"] == "Ocean View Camping"

    from tools.generate_summary import _generate_slideshow
    with patch('requests.get', return_value=mock_resp):
        result = _generate_slideshow(trip_data)
        
    assert result["status"] == "success"
    # Slide 0 is title, Slide 1 is Day 1
    day_1_slide_path = result["all_slides"][1]
    assert os.path.exists(day_1_slide_path)
    
    print(f"\n  ✅ Summary Slide generated at: {day_1_slide_path}")

if __name__ == "__main__":
    # Manual run if needed
    pytest.main([__file__])

"""
Verification tool for the VW California Travel Memory pipeline.

This script creates a test user, a test trip with a daily schedule and route,
generates different mock photos (matching EXIF, wrong location, wrong date, no EXIF),
and runs them through the EXIF extraction and auto-linking database pipeline.

Usage:
    python3 -m tools.verify_travel_memory [--cleanup] [--no-interactive]
"""

import os
import sys
import uuid
import argparse
from datetime import datetime, timedelta
from sqlalchemy import text
from PIL import Image

# Ensure project root is in sys.path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from tools.db import get_engine
from tools.mock_photo import generate_mock_photo
from tools.extract_exif import store_photo


def setup_test_data(conn):
    """
    Sets up a temporary user, trip, and daily schedule with a polyline in Munich.

    Args:
        conn: A SQLAlchemy connection object.

    Returns:
        tuple: (user_id, trip_id, ds_id)
    """
    user_id = str(uuid.uuid4())
    trip_id = str(uuid.uuid4())
    ds_id = str(uuid.uuid4())

    # 1. Create a test user
    conn.execute(
        text("""
            INSERT INTO users (id, email, display_name, vehicle_model)
            VALUES (:id, :email, :name, :vehicle)
        """),
        {
            "id": user_id,
            "email": f"memory_tester_{user_id[:8]}@volkswagen.com",
            "name": "VW Travel Memory Tester",
            "vehicle": "VW California Ocean 6.1"
        }
    )

    # 2. Create a test trip (June 10, 2026 to June 15, 2026)
    start_date = datetime(2026, 6, 10).date()
    end_date = datetime(2026, 6, 15).date()
    conn.execute(
        text("""
            INSERT INTO trips (id, user_id, title, origin_label, destination_label, start_date, end_date, status)
            VALUES (:id, :user_id, :title, :origin, :destination, :start_date, :end_date, :status)
        """),
        {
            "id": trip_id,
            "user_id": user_id,
            "title": "Bavarian Alps Road Trip",
            "origin": "Munich, Germany",
            "destination": "Zugspitze, Germany",
            "start_date": start_date,
            "end_date": end_date,
            "status": "active"
        }
    )

    # 3. Create a daily schedule for Day 1 (2026-06-10) near Munich
    # Encoded polyline for a route in Munich: connects (48.1351, 11.5820) and (48.1400, 11.5900)
    polyline = "_p~iH_c}hA_n`@_d|@"
    conn.execute(
        text("""
            INSERT INTO daily_schedules (id, trip_id, day_number, schedule_date, route_polyline)
            VALUES (:id, :trip_id, 1, :schedule_date, :polyline)
        """),
        {
            "id": ds_id,
            "trip_id": trip_id,
            "day_number": 1,
            "schedule_date": start_date,
            "polyline": polyline
        }
    )

    return user_id, trip_id, ds_id


def generate_mock_photos_set(tmp_dir):
    """
    Generates a set of mock photos representing different testing scenarios.

    Args:
        tmp_dir (str): Directory where photos will be generated.

    Returns:
        list: List of dicts containing mock photo generation info.
    """
    os.makedirs(tmp_dir, exist_ok=True)
    
    photos_to_create = [
        {
            "name": "photo_1_match.jpg",
            "lat": 48.9860,  # Near Regensburg polyline
            "lng": 12.1150,
            "date": "2026-06-10 12:00:00",  # During Trip, Day 1
            "color": (46, 204, 113),  # Green
            "desc": "Valid EXIF (Within 5km, Correct Date) -> Should Auto-Link",
            "has_exif": True
        },
        {
            "name": "photo_2_far_away.jpg",
            "lat": 52.5200,  # Berlin
            "lng": 13.4050,
            "date": "2026-06-10 14:00:00",  # During Trip
            "color": (231, 76, 60),  # Red
            "desc": "Wrong Location (Berlin, Too Far) -> Should NOT Link",
            "has_exif": True
        },
        {
            "name": "photo_3_wrong_date.jpg",
            "lat": 48.9860,  # Near Regensburg polyline
            "lng": 12.1150,
            "date": "2026-07-10 12:00:00",  # Wrong Date (July instead of June)
            "color": (241, 196, 15),  # Yellow
            "desc": "Wrong Date (Outside Trip Range) -> Should NOT Link",
            "has_exif": True
        },
        {
            "name": "photo_4_no_exif.jpg",
            "lat": None,
            "lng": None,
            "date": None,
            "color": (149, 165, 166),  # Grey
            "desc": "No EXIF Data -> Should NOT Link",
            "has_exif": False
        }
    ]

    for p in photos_to_create:
        filepath = os.path.join(tmp_dir, p["name"])
        p["filepath"] = filepath
        
        if p["has_exif"]:
            # Generate image with EXIF using tools.mock_photo helper
            generate_mock_photo(filepath, p["lat"], p["lng"], p["date"], color=p["color"])
        else:
            # Create a simple image without EXIF
            img = Image.new('RGB', (800, 600), color=p["color"])
            img.save(filepath, "jpeg")
            print(f"Successfully created mock photo without EXIF: {filepath}")

    return photos_to_create


def cleanup_test_data(user_id, photos_info, tmp_dir):
    """
    Cleans up the database records and physical files generated for testing.
    """
    print("\n🧹 Cleaning up test records and files...")
    
    # 1. Delete user from database (cascades to trips, schedules, photos)
    engine = get_engine()
    try:
        with engine.begin() as conn:
            conn.execute(text("DELETE FROM users WHERE id = :user_id"), {"user_id": user_id})
            print("  ✅ Database records removed successfully.")
    except Exception as e:
        print(f"  ⚠️ Database cleanup failed: {e}")

    # 2. Delete physical files (original photos and thumbnails)
    deleted_files = 0
    for p in photos_info:
        filepath = p.get("filepath")
        if filepath and os.path.exists(filepath):
            os.remove(filepath)
            deleted_files += 1

        # Look for thumbnail files
        if filepath:
            dir_name = os.path.dirname(filepath)
            base_name, ext = os.path.splitext(os.path.basename(filepath))
            thumb_path = os.path.join(dir_name, f"{base_name}_thumb{ext}")
            # Also check alternative .tmp dir
            project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            alt_thumb_path = os.path.join(project_root, ".tmp", f"{base_name}_thumb{ext}")
            
            for path in [thumb_path, alt_thumb_path]:
                if os.path.exists(path):
                    os.remove(path)
                    deleted_files += 1

    # Try removing the temp test directory
    try:
        if os.path.exists(tmp_dir) and not os.listdir(tmp_dir):
            os.rmdir(tmp_dir)
    except Exception:
        pass

    print(f"  ✅ Deleted {deleted_files} physical files.")


def run_pipeline_test(cleanup=False, interactive=True):
    """
    Executes the main pipeline verification test.
    """
    print("\n=======================================================")
    print("🚐 VW California Travel Memory Pipeline Verification")
    print("=======================================================")

    engine = get_engine()
    
    # 1. Setup DB test data
    print("\n[Step 1] Creating temporary database records...")
    with engine.begin() as conn:
        user_id, trip_id, ds_id = setup_test_data(conn)
    print(f"  User ID: {user_id}")
    print(f"  Trip ID: {trip_id}")
    print(f"  Daily Schedule ID: {ds_id}")

    # 2. Generate mock photos
    print("\n[Step 2] Generating mock photos with EXIF metadata...")
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    tmp_dir = os.path.join(project_root, ".tmp", "test_photos")
    photos_info = generate_mock_photos_set(tmp_dir)

    # 3. Process photos through store_photo pipeline
    print("\n[Step 3] Processing photos through store_photo pipeline...")
    results = []
    
    for p in photos_info:
        print(f"\n👉 Processing: {p['name']} ({p['desc']})")
        # Run store_photo
        res = store_photo(p["filepath"], user_id, trip_id)
        
        photo_record = res.get("photo", {})
        results.append({
            "name": p["name"],
            "desc": p["desc"],
            "status": res.get("status"),
            "exif_lat": photo_record.get("lat"),
            "exif_lng": photo_record.get("lng"),
            "captured_at": photo_record.get("captured_at"),
            "linked": res.get("linked", False),
            "day_number": photo_record.get("day_number"),
            "thumbnail_exists": os.path.exists(photo_record.get("thumbnail_url", "")) if photo_record.get("thumbnail_url") else False
        })

    # 4. Print Report
    print("\n=======================================================")
    print("                     TEST REPORT")
    print("=======================================================")
    print(f"{'Photo Name':<23} | {'Status':<7} | {'GPS Coordinates':<23} | {'Linked?':<7} | {'Day':<3} | {'Thumb?':<6}")
    print("-" * 80)
    
    all_matched_expectations = True
    
    for r in results:
        coords = f"{r['exif_lat']:.4f}, {r['exif_lng']:.4f}" if r["exif_lat"] is not None else "None"
        linked_str = "YES" if r["linked"] else "NO"
        day_str = str(r["day_number"]) if r["day_number"] is not None else "-"
        thumb_str = "YES" if r["thumbnail_exists"] else "NO"
        
        print(f"{r['name']:<23} | {r['status']:<7} | {coords:<23} | {linked_str:<7} | {day_str:<3} | {thumb_str:<6}")
        
        # Verify expectations
        if r["name"] == "photo_1_match.jpg":
            if not r["linked"] or r["day_number"] != 1:
                print("  ❌ ERROR: Photo 1 was expected to auto-link to Day 1 but did not!")
                all_matched_expectations = False
        elif r["name"] == "photo_2_far_away.jpg":
            if r["linked"]:
                print("  ❌ ERROR: Photo 2 was far away but auto-linked anyway!")
                all_matched_expectations = False
        elif r["name"] == "photo_3_wrong_date.jpg":
            if r["linked"]:
                print("  ❌ ERROR: Photo 3 had wrong date but auto-linked anyway!")
                all_matched_expectations = False
        elif r["name"] == "photo_4_no_exif.jpg":
            if r["linked"]:
                print("  ❌ ERROR: Photo 4 had no EXIF but auto-linked anyway!")
                all_matched_expectations = False
            if r["status"] != "warning":
                print(f"  ❌ ERROR: Photo 4 status expected 'warning', got '{r['status']}'")
                all_matched_expectations = False
                
    print("-" * 80)
    
    if all_matched_expectations:
        print("🎉 SUCCESS: All mock photos behaved EXACTLY as expected!")
    else:
        print("⚠️ FAILURE: Some mock photo results did not match expectations.")

    # 5. Cleanup decision
    do_cleanup = cleanup
    if interactive and sys.stdin.isatty():
        try:
            choice = input("\nDo you want to clean up the test database records and files? [Y/n]: ").strip().lower()
            do_cleanup = choice in ("", "y", "yes")
        except (KeyboardInterrupt, EOFError):
            do_cleanup = True
            
    if do_cleanup:
        cleanup_test_data(user_id, photos_info, tmp_dir)
    else:
        print(f"\n📌 Keeping test records. You can view them on the dashboard!")
        print(f"   Test User ID: {user_id}")
        print(f"   Test Trip ID: {trip_id}")
        print(f"   To manually clean up later, run this script with --cleanup")

    return all_matched_expectations


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Test and verify the Travel Memory photo pipeline.")
    parser.add_argument("--cleanup", action="store_true", help="Force cleanup of test data and files.")
    parser.add_argument("--no-interactive", action="store_true", help="Run without asking for confirmation.")
    
    args = parser.parse_args()
    
    # If no-interactive or cleanup flag is passed, we disable interactive mode
    is_interactive = not args.no_interactive and not args.cleanup
    should_cleanup = args.cleanup or args.no_interactive  # Cleanup by default in non-interactive tests
    
    success = run_pipeline_test(cleanup=should_cleanup, interactive=is_interactive)
    sys.exit(0 if success else 1)

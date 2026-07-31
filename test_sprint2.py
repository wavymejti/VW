import os
import json
import uuid
from dotenv import load_dotenv

# load env variables
load_dotenv()

from tools.plan_route import plan_route
from tools.suggest_attractions import suggest_attractions
from navigation.dispatcher import _handle_edit_waypoint
from tools.server import app

def run_tests():
    print("--- SPRINT 2 TESTS ---\n")
    
    origin = {"label": "Munich, Germany", "lat": 48.1351, "lng": 11.5820}
    destination = {"label": "Innsbruck, Austria", "lat": 47.2692, "lng": 11.4041}
    num_days = 2
    start_date = "2026-08-01"
    
    print("1. Testing plan_route (Camping options - Sprint 2.3)...")
    try:
        plan_result = plan_route(
            origin=origin,
            destination=destination,
            num_days=num_days,
            start_date=start_date,
            user_id="a1b2c3d4-e5f6-7890-abcd-ef1234567890"
        )
    except Exception as e:
        print(f"ERROR: plan_route threw an exception: {e}")
        return

    if plan_result.get("status") != "success":
        print("ERROR: plan_route failed:", plan_result)
        return
        
    trip_id = plan_result["trip"]["id"]
    schedules = plan_result.get("daily_schedules", [])
    print(f"Trip created: {trip_id}")
    
    options_found = False
    first_day_options = []
    for day in schedules:
        if "overnight_options" in day and len(day["overnight_options"]) > 0:
            options_found = True
            if not first_day_options:
                first_day_options = day["overnight_options"]
            print(f"Day {day['day_number']} has {len(day['overnight_options'])} overnight options.")
            
    if not options_found:
        print("WARNING: No overnight_options found in daily schedules.")
    else:
        print("SUCCESS: Kempingi (Sprint 2.3) - overnight_options present.")
        
    print("\n2. Testing suggest_attractions (Sprint 2.1)...")
    try:
        attractions_result = suggest_attractions(trip_id, preferences="castles, lakes", limit_per_day=2)
        if attractions_result.get("status") == "success":
            print("SUCCESS: suggest_attractions returned:", list(attractions_result["suggestions_by_day"].keys()))
            for day, suggestions in attractions_result["suggestions_by_day"].items():
                print(f" Day {day}: {len(suggestions)} attractions suggested.")
        else:
            print("ERROR: suggest_attractions failed:", attractions_result)
    except Exception as e:
        print(f"ERROR: suggest_attractions threw an exception: {e}")
        
    print("\n3. Testing /api/select_camping endpoint (Sprint 2.3)...")
    if first_day_options:
        selected_camping = first_day_options[0]
        app.config['TESTING'] = True
        app.secret_key = "test_key"
        
        try:
            with app.test_client() as client:
                with client.session_transaction() as sess:
                    sess['user_id'] = 'a1b2c3d4-e5f6-7890-abcd-ef1234567890'
                    
                response = client.post('/api/select_camping', json={
                    "trip_id": trip_id,
                    "day_number": 1,
                    "camping": selected_camping
                })
                
                if response.status_code == 200:
                    resp_data = response.get_json()
                    if resp_data.get("status") == "success":
                        print("SUCCESS: /api/select_camping worked.")
                    else:
                        print("ERROR: /api/select_camping returned error:", resp_data)
                else:
                    print("ERROR: /api/select_camping HTTP error:", response.status_code, response.get_data(as_text=True))
        except Exception as e:
            print(f"ERROR: /api/select_camping threw an exception: {e}")
    else:
        print("SKIPPED: /api/select_camping (no options available).")
        
    print("\n4. Testing _handle_edit_waypoint (Sprint 2.2)...")
    # To test removal, we need a waypoint. We can try deleting waypoint 1 (which would be between start and end).
    try:
        edit_args = {
            "trip_id": trip_id,
            "day_number": 1,
            "action": "remove",
            "waypoint_index": 1 # Let's try removing the second waypoint, not start/end.
        }
        edit_result = _handle_edit_waypoint(edit_args)
        if edit_result.get("status") == "success":
            print("SUCCESS: _handle_edit_waypoint worked:", edit_result["message"])
        else:
            print("ERROR/WARNING: _handle_edit_waypoint issue:", edit_result)
    except Exception as e:
        print(f"ERROR: _handle_edit_waypoint threw an exception: {e}")
        
    print("\n--- TESTS FINISHED ---")

if __name__ == "__main__":
    run_tests()

"""
Route planning tool for the VW California AI Trip Planner.

Generates a multi-day driving itinerary with waypoints,
campground stops, daily schedules, and precise route polylines.

See: architecture/routing_sop.md
"""

import uuid
from datetime import datetime, timedelta

from tools.db import get_engine
from tools.maps_client import get_client as get_maps_client
from tools.search_campings import search_campings

from sqlalchemy import text


def plan_route(
    origin,
    destination,
    num_days,
    start_date,
    max_daily_drive_hours=6.0,
    preferred_amenities=None,
    budget_per_night_eur=None,
    user_id=None,
    title=None,
):
    """
    Plan a multi-day route from origin to destination.

    Args:
        origin (dict): Origin with keys: label, lat, lng.
        destination (dict): Destination with keys: label, lat, lng.
        num_days (int): Number of travel days.
        start_date (str): Start date in YYYY-MM-DD format.
        max_daily_drive_hours (float): Max driving per day.
        preferred_amenities (list): Desired camping amenities.
        budget_per_night_eur (float): Max nightly budget.
        user_id (str): User UUID for persistence.
        title (str): Trip title.

    Returns:
        dict: Complete trip plan with daily schedules.
    """
    if preferred_amenities is None:
        preferred_amenities = []

    # Step 1: Get the total route via Google Maps
    total_route = _compute_total_route(origin, destination)

    if total_route["status"] == "error":
        return total_route

    total_duration_hours = total_route["duration_hours"]
    total_distance_km = total_route["distance_km"]
    legs = total_route.get("legs", [])

    # Validate feasibility
    if total_duration_hours > num_days * max_daily_drive_hours:
        return {
            "status": "error",
            "message": (
                f"Route requires ~{total_duration_hours:.1f}h of driving, "
                f"but {num_days} days × {max_daily_drive_hours}h = "
                f"{num_days * max_daily_drive_hours}h available. "
                "Consider adding more days or increasing daily hours."
            ),
        }

    # Step 2: Divide route into daily segments using actual steps
    total_duration_s = total_duration_hours * 3600
    intermediate_points = _interpolate_stops_along_route(
        legs, total_duration_s, num_days
    )

    # Step 3: Find campgrounds and precise daily routes
    daily_schedules = []
    start = datetime.strptime(start_date, "%Y-%m-%d")

    client = get_maps_client()

    for day_num in range(1, num_days + 1):
        day_date = start + timedelta(days=day_num - 1)

        # Determine start and end points for this day
        day_start = (
            origin if day_num == 1
            else intermediate_points[day_num - 2]
        )
        day_end = (
            destination if day_num == num_days
            else intermediate_points[day_num - 1]
        )

        # Find overnight camping (except last day at destination)
        overnight_camping = None
        if day_num < num_days:
            camping_results = search_campings(
                lat=day_end["lat"],
                lng=day_end["lng"],
                radius_km=30,
                amenities=preferred_amenities,
                max_cost_eur=budget_per_night_eur,
                vw_compatible=True,
                limit=1,
            )
            if camping_results.get("results"):
                overnight_camping = camping_results["results"][0]

        # Get exact directions for this day
        target_end = overnight_camping if overnight_camping else day_end
        try:
            day_directions = client.directions(
                origin=f"{day_start['lat']},{day_start['lng']}",
                destination=f"{target_end['lat']},{target_end['lng']}",
                mode="driving"
            )
            if day_directions:
                day_route = day_directions[0]
                day_legs = day_route.get("legs", [])
                day_distance_km = sum(l["distance"]["value"] for l in day_legs) / 1000
                day_duration_hours = sum(l["duration"]["value"] for l in day_legs) / 3600
                route_polyline = day_route["overview_polyline"]["points"]
            else:
                day_distance_km = total_distance_km / num_days
                day_duration_hours = total_duration_hours / num_days
                route_polyline = None
        except Exception as e:
            print(f"Failed to get daily route for day {day_num}: {e}")
            day_distance_km = total_distance_km / num_days
            day_duration_hours = total_duration_hours / num_days
            route_polyline = None

        # Build waypoints for this day
        waypoints = [
            {
                "order": 1,
                "type": "start",
                "label": day_start.get(
                    "label", f"Day {day_num} Start"
                ),
                "lat": day_start["lat"],
                "lng": day_start["lng"],
            },
        ]

        if overnight_camping:
            waypoints.append({
                "order": 2,
                "type": "camping",
                "label": overnight_camping["name"],
                "lat": overnight_camping["lat"],
                "lng": overnight_camping["lng"],
                "place_id": overnight_camping.get("place_id"),
            })
        else:
            waypoints.append({
                "order": 2,
                "type": "end",
                "label": day_end.get(
                    "label", f"Day {day_num} End"
                ),
                "lat": day_end["lat"],
                "lng": day_end["lng"],
            })

        schedule = {
            "id": str(uuid.uuid4()),
            "day_number": day_num,
            "date": day_date.strftime("%Y-%m-%d"),
            "driving_hours": round(day_duration_hours, 1),
            "driving_km": round(day_distance_km, 1),
            "waypoints": waypoints,
            "overnight_camping": overnight_camping,
            "route_polyline": route_polyline,
        }

        daily_schedules.append(schedule)

    # Step 4: Build trip object
    trip = {
        "id": str(uuid.uuid4()),
        "user_id": user_id,
        "title": title or (
            f"{origin['label']} to {destination['label']}"
        ),
        "origin": origin,
        "destination": destination,
        "start_date": start_date,
        "end_date": (
            start + timedelta(days=num_days - 1)
        ).strftime("%Y-%m-%d"),
        "status": "planned",
        "total_driving_hours": round(sum(d["driving_hours"] for d in daily_schedules), 1),
        "total_driving_km": round(sum(d["driving_km"] for d in daily_schedules), 1),
    }

    # Step 5: Persist to database if user_id provided
    if user_id:
        _persist_trip(trip, daily_schedules)

    return {
        "status": "success",
        "trip": trip,
        "daily_schedules": daily_schedules,
        "total_driving_hours": trip["total_driving_hours"],
        "total_driving_km": trip["total_driving_km"],
    }


def _compute_total_route(origin, destination):
    """
    Compute the total route between origin and destination
    using Google Maps Directions API.

    Returns:
        dict: Route info with distance_km, duration_hours, and legs.
    """
    try:
        client = get_maps_client()
        directions = client.directions(
            origin=f"{origin['lat']},{origin['lng']}",
            destination=(
                f"{destination['lat']},{destination['lng']}"
            ),
            mode="driving",
        )

        if not directions:
            return {
                "status": "error",
                "message": "No route found between origin "
                           "and destination.",
            }

        # Extract total distance and duration from the route
        route = directions[0]
        legs = route.get("legs", [])

        total_distance_m = sum(
            leg["distance"]["value"] for leg in legs
        )
        total_duration_s = sum(
            leg["duration"]["value"] for leg in legs
        )

        return {
            "status": "success",
            "distance_km": total_distance_m / 1000,
            "duration_hours": total_duration_s / 3600,
            "legs": legs,
        }

    except Exception as e:
        return {
            "status": "error",
            "message": f"Route computation failed: {e}",
        }


def _interpolate_stops_along_route(legs, total_duration_s, num_days):
    """
    Find intermediate stopping points by accumulating driving time 
    along actual route steps.

    Args:
        legs (list): Route legs from Google Maps Directions API.
        total_duration_s (int): Total route duration in seconds.
        num_days (int): Number of travel days.

    Returns:
        list: List of intermediate point dicts (num_days - 1 points).
    """
    if num_days <= 1:
        return []

    target_interval = total_duration_s / num_days
    points = []
    current_time = 0
    current_target = target_interval
    
    for leg in legs:
        for step in leg.get("steps", []):
            step_duration = step["duration"]["value"]
            current_time += step_duration
            
            if current_time >= current_target:
                # We reached or passed the target time for this day.
                points.append({
                    "label": f"Waypoint {len(points) + 1}",
                    "lat": step["end_location"]["lat"],
                    "lng": step["end_location"]["lng"],
                })
                current_target += target_interval
                
                if len(points) == num_days - 1:
                    return points
                    
    # Fallback if we didn't get enough points
    while len(points) < num_days - 1:
        points.append(points[-1] if points else {"label": "Fallback", "lat": 0, "lng": 0})
        
    return points


def _persist_trip(trip, daily_schedules):
    """
    Save trip and daily schedules to the database.

    Args:
        trip (dict): Trip data.
        daily_schedules (list): List of daily schedule dicts.
    """
    try:
        engine = get_engine()
        with engine.connect() as conn:
            # Insert trip
            conn.execute(
                text("""
                    INSERT INTO trips
                        (id, user_id, title, origin_label,
                         origin_lat, origin_lng,
                         destination_label, destination_lat,
                         destination_lng, start_date, end_date,
                         status)
                    VALUES
                        (:id, :user_id, :title,
                         :origin_label, :origin_lat, :origin_lng,
                         :dest_label, :dest_lat, :dest_lng,
                         :start_date, :end_date, :status)
                """),
                {
                    "id": trip["id"],
                    "user_id": trip["user_id"],
                    "title": trip["title"],
                    "origin_label": trip["origin"]["label"],
                    "origin_lat": trip["origin"]["lat"],
                    "origin_lng": trip["origin"]["lng"],
                    "dest_label": trip["destination"]["label"],
                    "dest_lat": trip["destination"]["lat"],
                    "dest_lng": trip["destination"]["lng"],
                    "start_date": trip["start_date"],
                    "end_date": trip["end_date"],
                    "status": trip["status"],
                },
            )

            # Insert daily schedules
            for schedule in daily_schedules:
                import json
                camping_id = None
                if schedule.get("overnight_camping"):
                    camping_id = schedule[
                        "overnight_camping"
                    ].get("id")

                conn.execute(
                    text("""
                        INSERT INTO daily_schedules
                            (id, trip_id, day_number,
                             schedule_date, driving_hours,
                             driving_km, waypoints,
                             overnight_camping_id, route_polyline)
                        VALUES
                            (:id, :trip_id, :day_number,
                             :schedule_date, :driving_hours,
                             :driving_km, :waypoints::jsonb,
                             :camping_id, :route_polyline)
                    """),
                    {
                        "id": schedule["id"],
                        "trip_id": trip["id"],
                        "day_number": schedule["day_number"],
                        "schedule_date": schedule["date"],
                        "driving_hours": schedule["driving_hours"],
                        "driving_km": schedule["driving_km"],
                        "waypoints": json.dumps(schedule["waypoints"]),
                        "camping_id": camping_id,
                        "route_polyline": schedule.get("route_polyline"),
                    },
                )

            conn.commit()
            print(f"  ✅ Trip '{trip['title']}' saved to DB")

    except Exception as e:
        print(f"  ⚠️  Failed to persist trip: {e}")


if __name__ == "__main__":
    # Example: Plan a 3-day trip from Munich to Split
    print("🗺️  Planning route: Munich → Split (3 days)...")
    result = plan_route(
        origin={
            "label": "Munich, Germany",
            "lat": 48.1351,
            "lng": 11.5820,
        },
        destination={
            "label": "Split, Croatia",
            "lat": 43.5081,
            "lng": 16.4402,
        },
        num_days=3,
        start_date="2026-07-01",
        preferred_amenities=["power", "showers"],
    )

    if result["status"] == "success":
        trip = result["trip"]
        print(f"\n  📋 {trip['title']}")
        print(f"  📅 {trip['start_date']} → {trip['end_date']}")
        print(f"  🚗 {result['total_driving_km']}km total, "
              f"{result['total_driving_hours']}h driving")
        print()
        for day in result["daily_schedules"]:
            print(f"  Day {day['day_number']} ({day['date']}):")
            for wp in day["waypoints"]:
                print(f"    → {wp['label']} ({wp['type']})")
            if day.get("overnight_camping"):
                print(f"    🏕️  Overnight: "
                      f"{day['overnight_camping']['name']}")
            print(f"    (Polyline included: {bool(day.get('route_polyline'))})")
            print()
    else:
        print(f"  ❌ {result['message']}")

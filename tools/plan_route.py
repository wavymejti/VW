"""
Route planning tool for the VW California AI Trip Planner.

Generates a multi-day driving itinerary with waypoints,
campground stops, daily schedules, and precise route polylines.

See: architecture/routing_sop.md
"""

import math
import uuid
from datetime import datetime, timedelta

from tools.db import get_engine
from tools.maps_client import get_client as get_maps_client
from tools.search_campings import search_campings
from tools.get_weather import get_weather_forecast

from sqlalchemy import text


def _haversine_distance(lat1, lon1, lat2, lon2):
    """Calculate great-circle distance between two points in kilometers."""
    r = 6371.0
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = (
        math.sin(dlat / 2) ** 2
        + math.cos(math.radians(lat1))
        * math.cos(math.radians(lat2))
        * math.sin(dlon / 2) ** 2
    )
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return r * c


def _normalize_waypoints(waypoints, client=None):
    """
    Normalize waypoints into a list of dicts with label, lat, lng.
    Geocodes via Google Maps API if lat/lng are missing.
    """
    if not waypoints:
        return []
    if isinstance(waypoints, (str, dict)):
        waypoints = [waypoints]

    normalized = []
    for item in waypoints:
        if not item:
            continue
        if isinstance(item, str):
            label = item.strip()
            lat, lng, place_id = None, None, None
            notes = None
            emoji = "📍"
            color = "#001E50"
            category_label = "Punkt na trasie"
        elif isinstance(item, dict):
            label = item.get("label") or item.get("name") or "Waypoint"
            lat = item.get("lat")
            lng = item.get("lng")
            place_id = item.get("place_id")
            notes = item.get("notes")
            emoji = item.get("emoji") or "📍"
            color = item.get("color") or "#001E50"
            category_label = item.get("category_label") or "Punkt na trasie"
        else:
            continue

        if (lat is None or lng is None) and client and label:
            try:
                res = client.geocode(label)
                if res:
                    loc = res[0]["geometry"]["location"]
                    lat, lng = loc["lat"], loc["lng"]
                    place_id = place_id or res[0].get("place_id")
                    if not label or label == "Waypoint":
                        label = res[0].get("formatted_address", label)
            except Exception as e:
                print(f"Failed to geocode waypoint '{label}': {e}")

        if lat is not None and lng is not None:
            normalized.append({
                "label": label,
                "lat": float(lat),
                "lng": float(lng),
                "place_id": place_id,
                "type": "attraction",
                "emoji": emoji,
                "color": color,
                "category_label": category_label,
                "notes": notes,
            })
    return normalized


def _ensure_coords(place, client=None):
    """
    Return {label, lat, lng} for a place given as a dict or a plain name.
    Geocodes via Google Maps when lat/lng are missing. Returns None if it can't.
    """
    if not place:
        return None
    if isinstance(place, str):
        place = {"label": place}
    if not isinstance(place, dict):
        return None
    label = place.get("label") or place.get("name")
    lat, lng = place.get("lat"), place.get("lng")
    if (lat is None or lng is None) and client and label:
        try:
            res = client.geocode(label)
            if res:
                loc = res[0]["geometry"]["location"]
                lat, lng = loc["lat"], loc["lng"]
        except Exception as e:
            print(f"Failed to geocode '{label}': {e}")
    if lat is None or lng is None:
        return None
    out = dict(place)
    out["label"] = label or f"{float(lat):.4f},{float(lng):.4f}"
    out["lat"], out["lng"] = float(lat), float(lng)
    return out


def _normalize_overnight_stops(overnight_stops, client=None):
    """
    Normalize the requested overnight places (in travel order).

    Returns:
        tuple: (resolved stops [{label, lat, lng}], labels that could not be located)
    """
    if not overnight_stops:
        return [], []
    if isinstance(overnight_stops, (str, dict)):
        overnight_stops = [overnight_stops]
    resolved, failed = [], []
    for item in overnight_stops:
        place = _ensure_coords(item, client)
        if place:
            resolved.append({"label": place["label"], "lat": place["lat"], "lng": place["lng"]})
        else:
            failed.append(item.get("label") if isinstance(item, dict) else str(item))
    return resolved, failed


def _apply_overnight_stops(points, stops):
    """
    Put the requested overnight places in place of the interpolated day ends.

    Each stop (kept in the given travel order) replaces the nearest still-free
    interpolated point, keeping days in order; leftover days stay interpolated.
    Requires len(points) >= len(stops).
    """
    if not stops:
        return points
    points = list(points)
    last = -1
    for i, stop in enumerate(stops):
        remaining = len(stops) - i - 1
        candidates = range(last + 1, len(points) - remaining)
        best = min(
            candidates,
            key=lambda k: _haversine_distance(
                points[k]["lat"], points[k]["lng"], stop["lat"], stop["lng"]
            ),
        )
        points[best] = {
            "label": stop["label"],
            "lat": stop["lat"],
            "lng": stop["lng"],
            "requested_overnight": True,
        }
        last = best
    return points


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
    notes=None,
    round_trip=False,
    waypoints=None,
    overnight_stops=None,
):
    """
    Plan a multi-day route from origin to destination.

    One travel day ends at each overnight stop, so num_days is at least
    len(overnight_stops) + 1 (a trip with one night on the way = 2 days).

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
        overnight_stops (list): Optional places to sleep, in travel order
            (dicts with label and optional lat/lng, or plain names).

    Returns:
        dict: Complete trip plan with daily schedules, plus `warnings`
            (things the user should be told, e.g. no campsite found).
    """
    if preferred_amenities is None:
        preferred_amenities = []

    client = get_maps_client()
    warnings = []

    origin = _ensure_coords(origin, client)
    destination = _ensure_coords(destination, client)
    if origin is None or destination is None:
        return {
            "status": "error",
            "message": "Could not locate the origin or the destination.",
        }

    try:
        num_days = max(1, int(num_days))
    except (TypeError, ValueError):
        return {"status": "error", "message": f"Invalid num_days: {num_days!r}."}

    requested_stops, failed_stops = _normalize_overnight_stops(overnight_stops, client)
    if failed_stops:
        warnings.append(
            "Could not locate the requested overnight place(s): "
            + ", ".join(failed_stops) + "."
        )
    min_days = len(requested_stops) + 1
    if num_days < min_days:
        warnings.append(
            f"num_days raised from {num_days} to {min_days} so that each of the "
            f"{len(requested_stops)} overnight stop(s) gets its own night."
        )
        num_days = min_days

    normalized_waypoints = _normalize_waypoints(waypoints, client)

    # Step 1: Get the total route via Google Maps
    total_route = _compute_total_route(origin, destination, round_trip, normalized_waypoints)

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
    route_end = origin if round_trip else destination
    intermediate_points = _interpolate_stops_along_route(
        legs, total_duration_s, num_days, origin, route_end
    )
    intermediate_points = _apply_overnight_stops(intermediate_points, requested_stops)

    # Pre-calculate nominal start and end for each day to assign waypoints
    day_nominal_segments = {}
    for d in range(1, num_days + 1):
        d_start = origin if d == 1 else intermediate_points[d - 2]
        d_end = (
            origin if (d == num_days and round_trip)
            else destination if (d == num_days and not round_trip)
            else intermediate_points[d - 1]
        )
        day_nominal_segments[d] = (d_start, d_end)

    day_waypoints_map = {d: [] for d in range(1, num_days + 1)}
    for wp in normalized_waypoints:
        best_day = 1
        min_detour = float("inf")
        for d, (s_loc, e_loc) in day_nominal_segments.items():
            s_lat, s_lng = s_loc["lat"], s_loc["lng"]
            e_lat, e_lng = e_loc["lat"], e_loc["lng"]
            if s_lat == e_lat and s_lng == e_lng:
                detour = 2 * _haversine_distance(s_lat, s_lng, wp["lat"], wp["lng"])
            else:
                detour = (
                    _haversine_distance(s_lat, s_lng, wp["lat"], wp["lng"])
                    + _haversine_distance(wp["lat"], wp["lng"], e_lat, e_lng)
                    - _haversine_distance(s_lat, s_lng, e_lat, e_lng)
                )
            if detour < min_detour:
                min_detour = detour
                best_day = d
        day_waypoints_map[best_day].append(wp)

    # Step 3: Find campgrounds and precise daily routes
    daily_schedules = []
    start = datetime.strptime(start_date, "%Y-%m-%d")

    previous_day_end = None

    for day_num in range(1, num_days + 1):
        day_date = start + timedelta(days=day_num - 1)

        # Determine start and end points for this day
        if day_num == 1:
            day_start = origin
        else:
            day_start = previous_day_end if previous_day_end else intermediate_points[day_num - 2]

        day_end = (
            origin if (day_num == num_days and round_trip)
            else destination if (day_num == num_days and not round_trip)
            else intermediate_points[day_num - 1]
        )

        day_wps = day_waypoints_map.get(day_num, [])

        # Find overnight camping (except last day at destination)
        overnight_camping = None
        overnight_options = []
        if day_num < num_days:
            for radius_km in (30, 50):
                camping_results = search_campings(
                    lat=day_end["lat"],
                    lng=day_end["lng"],
                    radius_km=radius_km,
                    amenities=preferred_amenities,
                    max_cost_eur=budget_per_night_eur,
                    vw_compatible=True,
                    limit=3,
                )
                if camping_results.get("results"):
                    overnight_options = camping_results["results"]
                    overnight_camping = overnight_options[0]
                    break
            if not overnight_camping:
                warnings.append(
                    f"Day {day_num}: no campsite found within 50 km of "
                    f"{day_end.get('label', 'the day end')}; the night is marked "
                    "at that point on the route — the user should pick a place to sleep."
                )

        # Get exact directions for this day
        target_end = overnight_camping if overnight_camping else day_end
        ordered_day_wps = list(day_wps)
        try:
            directions_kwargs = {
                "origin": f"{day_start['lat']},{day_start['lng']}",
                "destination": f"{target_end['lat']},{target_end['lng']}",
                "mode": "driving",
                "departure_time": max(datetime.now(), datetime.combine(day_date, datetime.min.time())),
                "traffic_model": "best_guess",
            }
            if day_wps:
                directions_kwargs["waypoints"] = [f"{w['lat']},{w['lng']}" for w in day_wps]
                directions_kwargs["optimize_waypoints"] = True

            day_directions = client.directions(**directions_kwargs)
            if day_directions:
                day_route = day_directions[0]
                day_legs = day_route.get("legs", [])
                day_distance_km = sum(l["distance"]["value"] for l in day_legs) / 1000
                day_duration_hours = sum(l["duration"]["value"] for l in day_legs) / 3600
                route_polyline = day_route["overview_polyline"]["points"]

                if day_wps and day_route.get("waypoint_order"):
                    wp_order = day_route["waypoint_order"]
                    ordered_day_wps = [day_wps[i] for i in wp_order if i < len(day_wps)]
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
        day_schedule_waypoints = [
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

        for wp in ordered_day_wps:
            day_schedule_waypoints.append({
                "order": len(day_schedule_waypoints) + 1,
                "type": "attraction",
                "label": wp.get("label", "Waypoint"),
                "lat": wp["lat"],
                "lng": wp["lng"],
                "place_id": wp.get("place_id"),
                "address": wp.get("address", ""),
                "rating": wp.get("rating"),
                "emoji": wp.get("emoji", "📍"),
                "color": wp.get("color", "#001E50"),
                "category_label": wp.get("category_label", "Punkt na trasie"),
                "notes": wp.get("notes"),
            })

        if overnight_camping:
            day_schedule_waypoints.append({
                "order": len(day_schedule_waypoints) + 1,
                "type": "camping",
                "label": overnight_camping["name"],
                "lat": overnight_camping["lat"],
                "lng": overnight_camping["lng"],
                "place_id": overnight_camping.get("place_id"),
            })
        else:
            day_schedule_waypoints.append({
                "order": len(day_schedule_waypoints) + 1,
                "type": "end",
                "label": day_end.get(
                    "label", f"Day {day_num} End"
                ),
                "lat": day_end["lat"],
                "lng": day_end["lng"],
            })

        # Fetch weather for the end location of the day
        weather = get_weather_forecast(
            day_end["lat"], day_end["lng"], day_date.strftime("%Y-%m-%d")
        )

        # Determine if this day is on the return leg
        is_return_leg = False
        if round_trip:
            is_return_leg = day_num > (num_days / 2)
        elif origin.get("lat") == destination.get("lat") and origin.get("lng") == destination.get("lng"):
            is_return_leg = day_num > (num_days / 2)

        schedule = {
            "id": str(uuid.uuid4()),
            "day_number": day_num,
            "date": day_date.strftime("%Y-%m-%d"),
            "driving_hours": round(day_duration_hours, 1),
            "driving_km": round(day_distance_km, 1),
            "waypoints": day_schedule_waypoints,
            "overnight_camping": overnight_camping,
            "overnight_options": overnight_options,
            "route_polyline": route_polyline,
            "weather": weather if weather["status"] == "success" else None,
            "is_return": is_return_leg
        }

        # Remember this day's actual end point to be the start point of the next day
        if overnight_camping:
            previous_day_end = {
                "label": overnight_camping["name"],
                "lat": overnight_camping["lat"],
                "lng": overnight_camping["lng"]
            }
        else:
            previous_day_end = day_end

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
        "num_days": num_days,
        "overnight_count": num_days - 1,
        "warnings": warnings,
    }


def _compute_total_route(origin, destination, round_trip=False, waypoints=None):
    """
    Compute the total route between origin and destination
    using Google Maps Directions API.

    Returns:
        dict: Route info with distance_km, duration_hours, and legs.
    """
    if waypoints is None:
        waypoints = []

    try:
        client = get_maps_client()
        normalized_wps = _normalize_waypoints(waypoints, client)
        wp_list = [f"{wp['lat']},{wp['lng']}" for wp in normalized_wps]
        
        if round_trip:
            # Add destination to waypoints as the turnaround point if it's different from origin
            if destination['label'] != origin['label']:
                wp_list.append(f"{destination['lat']},{destination['lng']}")
                
            directions = client.directions(
                origin=f"{origin['lat']},{origin['lng']}",
                destination=f"{origin['lat']},{origin['lng']}",
                waypoints=wp_list,
                mode="driving",
                departure_time="now",
                traffic_model="best_guess",
                optimize_waypoints=True if len(wp_list) > 1 else False
            )
        else:
            directions = client.directions(
                origin=f"{origin['lat']},{origin['lng']}",
                destination=f"{destination['lat']},{destination['lng']}",
                waypoints=wp_list,
                mode="driving",
                departure_time="now",
                traffic_model="best_guess",
                optimize_waypoints=True if len(wp_list) > 1 else False
            )

        if not directions:
            if normalized_wps:
                wp_names = ", ".join(w.get("label", "waypoint") for w in normalized_wps)
                return {
                    "status": "error",
                    "message": f"Nie można wyznaczyć trasy przejazdu przez punkt: {wp_names}. Upewnij się, że miejsce posiada bezpośredni dojazd samochodowy.",
                }
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


def _interpolate_stops_along_route(legs, total_duration_s, num_days, origin, destination):
    """
    Find intermediate stopping points by accumulating driving time 
    along actual route steps.

    Args:
        legs (list): Route legs from Google Maps Directions API.
        total_duration_s (int): Total route duration in seconds.
        num_days (int): Number of travel days.
        origin (dict): Origin coordinates.
        destination (dict): Destination coordinates.

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
    lat1, lng1 = origin["lat"], origin["lng"]
    lat2, lng2 = destination["lat"], destination["lng"]
    
    while len(points) < num_days - 1:
        idx = len(points) + 1
        fraction = idx / num_days
        interp_lat = lat1 + (lat2 - lat1) * fraction
        interp_lng = lng1 + (lng2 - lng1) * fraction
        points.append({
            "label": f"Fallback Waypoint {idx}",
            "lat": interp_lat,
            "lng": interp_lng
        })
        
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
                             :driving_km, CAST(:waypoints AS jsonb),
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

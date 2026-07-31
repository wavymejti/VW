"""
Intent dispatcher for the VW California AI Trip Planner.

Routes OpenAI function calls to the appropriate atomic tools
in the tools/ layer.

See: architecture/chat_orchestration_sop.md
"""

import json
import os
from datetime import datetime

from tools.search_campings import search_campings
from tools.plan_route import plan_route
from tools.extract_exif import store_photo
from tools.suggest_attractions import suggest_attractions


# Registry of tool functions callable by the AI
TOOL_REGISTRY = {
    "search_campings": search_campings,
    "plan_route": plan_route,
    "upload_photos": store_photo,
    "suggest_attractions": suggest_attractions,
    # modify_route, add_attraction, edit_waypoint are handled inline below
}


def dispatch(function_name, arguments):
    """
    Dispatch an OpenAI function call to the appropriate tool.

    Args:
        function_name (str): Name of the function to call.
        arguments (dict): Arguments extracted by the model.

    Returns:
        dict: Tool execution result.
    """
    # Inline handlers for mutation tools
    if function_name == "modify_route":
        return _handle_modify_route(arguments)
    if function_name == "add_attraction":
        return _handle_add_attraction(arguments)
    if function_name == "edit_waypoint":
        return _handle_edit_waypoint(arguments)

    if function_name not in TOOL_REGISTRY:
        return {
            "status": "error",
            "message": (
                f"Unknown function: '{function_name}'. "
                f"Available: {list(TOOL_REGISTRY.keys()) + ['modify_route', 'add_attraction', 'edit_waypoint']}"
            ),
        }

    tool_fn = TOOL_REGISTRY[function_name]

    try:
        result = tool_fn(**arguments)
        return result

    except TypeError as e:
        return {
            "status": "error",
            "message": (
                f"Invalid arguments for '{function_name}': {e}"
            ),
        }
    except Exception as e:
        return {
            "status": "error",
            "message": (
                f"Tool '{function_name}' failed: {e}"
            ),
        }


def _handle_modify_route(arguments):
    """
    Handle route modification by re-planning with amended parameters.

    Accepts exclude_places, force_overnight_change, and other overrides
    on top of the original trip parameters. Falls back to a fresh
    plan_route call with the updated context.

    Args:
        arguments (dict): May include trip_id, origin, destination,
            num_days, start_date, exclude_places, preferred_overnight,
            preferred_amenities, wild_camping, notes.

    Returns:
        dict: New trip data from plan_route.
    """
    try:
        from tools.db import get_engine
        from sqlalchemy import text

        trip_id = arguments.get("trip_id")
        exclude_places = arguments.get("exclude_places", [])
        preferred_overnight = arguments.get("preferred_overnight")
        notes = arguments.get("notes", "")

        # Fetch original trip parameters from DB if trip_id provided
        origin = arguments.get("origin")
        destination = arguments.get("destination")
        num_days = arguments.get("num_days")
        start_date = arguments.get("start_date")
        preferred_amenities = arguments.get("preferred_amenities")
        user_id = arguments.get("user_id")

        if trip_id and not all([origin, destination, num_days, start_date]):
            engine = get_engine()
            with engine.connect() as conn:
                row = conn.execute(
                    text(
                        "SELECT origin_label, origin_lat, origin_lng, "
                        "destination_label, destination_lat, destination_lng, "
                        "start_date, end_date, user_id "
                        "FROM trips WHERE id = :id"
                    ),
                    {"id": trip_id}
                ).fetchone()

                if row:
                    origin = origin or {
                        "label": row[0], "lat": float(row[1]), "lng": float(row[2])
                    }
                    destination = destination or {
                        "label": row[3], "lat": float(row[4]), "lng": float(row[5])
                    }
                    if not num_days and row[6] and row[7]:
                        num_days = (row[7] - row[6]).days + 1
                    start_date = start_date or str(row[6])
                    user_id = user_id or str(row[8])

        if not all([origin, destination, num_days, start_date]):
            try:
                engine = get_engine()
                with engine.connect() as conn:
                    row = conn.execute(
                        text("SELECT origin_label, origin_lat, origin_lng, destination_label, destination_lat, destination_lng, start_date, end_date, user_id, id FROM trips ORDER BY created_at DESC LIMIT 1")
                    ).fetchone()
                    if row:
                        origin = origin or {"label": row[0], "lat": float(row[1]), "lng": float(row[2])}
                        destination = destination or {"label": row[3], "lat": float(row[4]), "lng": float(row[5])}
                        if not num_days and row[6] and row[7]:
                            num_days = (row[7] - row[6]).days + 1
                        num_days = num_days or 3
                        start_date = start_date or (str(row[6]) if row[6] else datetime.now().strftime("%Y-%m-%d"))
                        user_id = user_id or str(row[8])
                        trip_id = trip_id or str(row[9])
            except Exception as ex:
                print(f"Fallback trip fetch failed: {ex}")

        if not all([origin, destination, num_days, start_date]):
            return {
                "status": "error",
                "message": (
                    "Insufficient parameters for route modification. "
                    "Origin, destination, num_days, and start_date are required."
                ),
            }

        # Build exclusion note for the routing engine
        extra_notes = []
        if exclude_places:
            extra_notes.append(f"Avoid these places: {', '.join(exclude_places)}")
        if preferred_overnight:
            extra_notes.append(f"Preferred overnight environment: {preferred_overnight}")
        if notes:
            extra_notes.append(notes)

        result = plan_route(
            origin=origin,
            destination=destination,
            num_days=num_days,
            start_date=start_date,
            preferred_amenities=preferred_amenities,
            user_id=user_id,
            notes=" | ".join(extra_notes) if extra_notes else None,
        )

        # Tag result as a route modification
        if result.get("status") == "success":
            result["mutation_type"] = "modify_route"
            result["excluded_places"] = exclude_places

        return result

    except Exception as e:
        return {"status": "error", "message": f"modify_route failed: {e}"}


def _handle_add_attraction(arguments):
    """
    Add a POI attraction to a specific day of the current trip
    using Google Maps Places API.

    Args:
        arguments (dict): trip_id, day_number, query (search string),
            lat (optional centre), lng (optional centre),
            is_overnight (optional boolean).

    Returns:
        dict: Added attraction details and updated day waypoints.
    """
    try:
        import googlemaps
        from tools.db import get_engine
        from sqlalchemy import text
        import uuid

        gmaps_key = os.getenv("GOOGLE_MAPS_API_KEY")
        if not gmaps_key:
            return {
                "status": "error",
                "message": "GOOGLE_MAPS_API_KEY not configured.",
            }

        trip_id = arguments.get("trip_id")
        day_number = arguments.get("day_number")
        query = arguments.get("query", "")
        lat = arguments.get("lat")
        lng = arguments.get("lng")
        is_overnight = arguments.get("is_overnight", False)

        if not trip_id or not day_number or not query:
            return {
                "status": "error",
                "message": "trip_id, day_number, and query are required.",
            }

        gmaps = googlemaps.Client(key=gmaps_key)

        # Use text search + optional location bias
        search_kwargs = {"query": query}
        if lat and lng:
            search_kwargs["location"] = (lat, lng)
            search_kwargs["radius"] = 80000  # 80 km bias radius

        places_result = gmaps.places(**search_kwargs)

        if not places_result.get("results"):
            return {
                "status": "error",
                "message": (
                    f"No attractions found for '{query}'. "
                    "Try a different search term."
                ),
            }

        # Pick the top result
        place = places_result["results"][0]
        attraction = {
            "name": place.get("name"),
            "place_id": place.get("place_id"),
            "lat": place["geometry"]["location"]["lat"],
            "lng": place["geometry"]["location"]["lng"],
            "address": place.get("formatted_address", ""),
            "rating": place.get("rating"),
        }

        # Update the daily_schedule waypoints in DB
        engine = get_engine()
        with engine.begin() as conn:
            schedule_row = conn.execute(
                text(
                    "SELECT id, waypoints, overnight_camping_id FROM daily_schedules "
                    "WHERE trip_id = :tid AND day_number = :day "
                    "LIMIT 1"
                ),
                {"tid": trip_id, "day": day_number}
            ).fetchone()

            if not schedule_row:
                return {
                    "status": "error",
                    "message": (
                        f"Day {day_number} not found for trip {trip_id}."
                    ),
                }

            schedule_id = schedule_row[0]
            existing_waypoints = schedule_row[1] or []

            new_waypoint = {
                "order": len(existing_waypoints),
                "type": "camping" if is_overnight else "attraction",
                "label": attraction["name"],
                "lat": attraction["lat"],
                "lng": attraction["lng"],
                "place_id": attraction["place_id"],
                "notes": f"Added by AI: {query}",
            }

            if is_overnight:
                # Replace the last waypoint (which is usually the overnight stop or end point)
                updated_waypoints = existing_waypoints[:-1] + [new_waypoint]
            else:
                # Insert new attraction before the last waypoint
                updated_waypoints = existing_waypoints[:-1] + [new_waypoint] + existing_waypoints[-1:]
            
            # Recalculate route and save to DB
            update_done = _recalculate_day_route(conn, schedule_id, updated_waypoints)
            if not update_done:
                for i, wp in enumerate(updated_waypoints):
                    wp["order"] = i

                conn.execute(
                    text(
                        "UPDATE daily_schedules SET waypoints = CAST(:wps AS jsonb) "
                        "WHERE id = :sid"
                    ),
                    {"wps": json.dumps(updated_waypoints), "sid": str(schedule_id)}
                )

        return {
            "status": "success",
            "mutation_type": "add_attraction",
            "trip_id": trip_id,
            "day_number": day_number,
            "attraction": attraction,
            "is_overnight": is_overnight,
            "message": (
                f"{'Replaced overnight stop with' if is_overnight else 'Added'} "
                f"'{attraction['name']}' on day {day_number}."
            ),
        }

    except Exception as e:
        return {"status": "error", "message": f"add_attraction failed: {e}"}


def _recalculate_day_route(conn, schedule_id, waypoints):
    """
    Recalculates the day route using Google Directions API and saves it to the database.
    Optimizes intermediate waypoints if there are any.
    Returns True if successfully updated.
    """
    import json
    from sqlalchemy import text
    try:
        from tools.maps_client import get_client
        client = get_client()
        
        origin_wp = waypoints[0]
        dest_wp = waypoints[-1]
        
        directions_kwargs = {
            "origin": f"{origin_wp['lat']},{origin_wp['lng']}",
            "destination": f"{dest_wp['lat']},{dest_wp['lng']}",
            "mode": "driving"
        }
        
        if len(waypoints) > 2:
            intermediates = waypoints[1:-1]
            directions_kwargs["waypoints"] = [f"{w['lat']},{w['lng']}" for w in intermediates]
            directions_kwargs["optimize_waypoints"] = True

        directions = client.directions(**directions_kwargs)
        
        if directions:
            route = directions[0]
            legs = route.get("legs", [])
            new_distance = sum(l["distance"]["value"] for l in legs) / 1000
            new_duration = sum(l["duration"]["value"] for l in legs) / 3600
            new_polyline = route["overview_polyline"]["points"]
            
            if len(waypoints) > 2:
                waypoint_order = route.get("waypoint_order", [])
                optimized_intermediates = [intermediates[i] for i in waypoint_order]
                waypoints = [origin_wp] + optimized_intermediates + [dest_wp]
                
            for i, wp in enumerate(waypoints):
                wp["order"] = i
                
            conn.execute(
                text(
                    "UPDATE daily_schedules SET "
                    "waypoints = CAST(:wps AS jsonb), "
                    "driving_km = :km, "
                    "driving_hours = :hours, "
                    "route_polyline = :poly "
                    "WHERE id = :sid"
                ),
                {
                    "wps": json.dumps(waypoints),
                    "km": round(new_distance, 1),
                    "hours": round(new_duration, 1),
                    "poly": new_polyline,
                    "sid": str(schedule_id)
                }
            )
            return True
    except Exception as e:
        print(f"Failed to recalculate route: {e}")
    return False


def _handle_edit_waypoint(arguments):
    """
    Edit, remove, or move a waypoint from the route.
    """
    try:
        import json
        from tools.db import get_engine
        from sqlalchemy import text

        trip_id = arguments.get("trip_id")
        day_number = arguments.get("day_number")
        action = arguments.get("action")
        wp_index = arguments.get("waypoint_index")
        
        if not all([trip_id, day_number, action, wp_index is not None]):
            return {"status": "error", "message": "trip_id, day_number, action, and waypoint_index are required."}
            
        engine = get_engine()
        with engine.begin() as conn:
            schedule_row = conn.execute(
                text(
                    "SELECT id, waypoints FROM daily_schedules "
                    "WHERE trip_id = :tid AND day_number = :day LIMIT 1"
                ),
                {"tid": trip_id, "day": day_number}
            ).fetchone()
            
            if not schedule_row:
                return {"status": "error", "message": f"Day {day_number} not found."}
                
            schedule_id = schedule_row[0]
            waypoints = schedule_row[1] or []
            
            if wp_index < 0 or wp_index >= len(waypoints):
                return {"status": "error", "message": f"Invalid waypoint_index {wp_index}."}
                
            if wp_index == 0 or wp_index == len(waypoints) - 1:
                return {"status": "error", "message": "Cannot edit start or end waypoints directly here yet."}
                
            wp_to_edit = waypoints[wp_index]

            if action == "remove":
                waypoints.pop(wp_index)
                update_done = _recalculate_day_route(conn, schedule_id, waypoints)
                if not update_done:
                    for i, wp in enumerate(waypoints):
                        wp["order"] = i
                    conn.execute(
                        text("UPDATE daily_schedules SET waypoints = CAST(:wps AS jsonb) WHERE id = :sid"),
                        {"wps": json.dumps(waypoints), "sid": str(schedule_id)},
                    )
                return {
                    "status": "success",
                    "message": f"Removed waypoint '{wp_to_edit.get('label')}' from day {day_number}.",
                }

            if action == "replace":
                # Replace the waypoint with a new POI supplied by the caller.
                new_label = arguments.get("label") or wp_to_edit.get("label", "Waypoint")
                new_wp = {
                    "order": wp_index,
                    "type": arguments.get("type", wp_to_edit.get("type", "attraction")),
                    "label": new_label,
                    "lat": arguments.get("lat", wp_to_edit.get("lat")),
                    "lng": arguments.get("lng", wp_to_edit.get("lng")),
                    "place_id": arguments.get("place_id", wp_to_edit.get("place_id")),
                    "notes": arguments.get("notes", "Replaced by AI"),
                }
                waypoints[wp_index] = new_wp
                update_done = _recalculate_day_route(conn, schedule_id, waypoints)
                if not update_done:
                    for i, wp in enumerate(waypoints):
                        wp["order"] = i
                    conn.execute(
                        text("UPDATE daily_schedules SET waypoints = CAST(:wps AS jsonb) WHERE id = :sid"),
                        {"wps": json.dumps(waypoints), "sid": str(schedule_id)},
                    )
                return {
                    "status": "success",
                    "message": f"Replaced waypoint with '{new_label}' on day {day_number}.",
                }

            if action == "move":
                target_day = arguments.get("target_day_number")
                if not target_day or target_day == day_number:
                    return {
                        "status": "error",
                        "message": "target_day_number is required and must differ from the source day.",
                    }

                # Remove from the source day.
                moved_wp = waypoints.pop(wp_index)
                source_updated = _recalculate_day_route(conn, schedule_id, waypoints)
                if not source_updated:
                    for i, wp in enumerate(waypoints):
                        wp["order"] = i
                    conn.execute(
                        text("UPDATE daily_schedules SET waypoints = CAST(:wps AS jsonb) WHERE id = :sid"),
                        {"wps": json.dumps(waypoints), "sid": str(schedule_id)},
                    )

                # Append to the target day.
                target_row = conn.execute(
                    text(
                        "SELECT id, waypoints FROM daily_schedules "
                        "WHERE trip_id = :tid AND day_number = :day LIMIT 1"
                    ),
                    {"tid": trip_id, "day": target_day},
                ).fetchone()
                if not target_row:
                    # Roll back the removal by re-inserting the waypoint.
                    waypoints.insert(wp_index, moved_wp)
                    for i, wp in enumerate(waypoints):
                        wp["order"] = i
                    conn.execute(
                        text("UPDATE daily_schedules SET waypoints = CAST(:wps AS jsonb) WHERE id = :sid"),
                        {"wps": json.dumps(waypoints), "sid": str(schedule_id)},
                    )
                    return {
                        "status": "error",
                        "message": f"Target day {target_day} not found.",
                    }

                target_id = target_row[0]
                target_wps = target_row[1] or []
                moved_wp["order"] = len(target_wps)
                target_wps.append(moved_wp)
                target_updated = _recalculate_day_route(conn, target_id, target_wps)
                if not target_updated:
                    for i, wp in enumerate(target_wps):
                        wp["order"] = i
                    conn.execute(
                        text("UPDATE daily_schedules SET waypoints = CAST(:wps AS jsonb) WHERE id = :sid"),
                        {"wps": json.dumps(target_wps), "sid": str(target_id)},
                    )
                return {
                    "status": "success",
                    "message": f"Moved '{moved_wp.get('label')}' from day {day_number} to day {target_day}.",
                }

            return {
                "status": "error",
                "message": f"Action '{action}' not supported.",
            }
            
    except Exception as e:
        return {"status": "error", "message": f"edit_waypoint failed: {e}"}


# ── OpenAI Tool Definitions ────────────────────────────────────
# These are the schema definitions passed to OpenAI's
# Function Calling so it knows what tools are available.
# ──────────────────────────────────────────────────────────────

OPENAI_TOOL_DEFINITIONS = [
    {
        "type": "function",
        "function": {
            "name": "search_campings",
            "description": (
                "Search for campgrounds near a given location. "
                "Filters by amenities, cost, and VW California "
                "vehicle compatibility."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "lat": {
                        "type": "number",
                        "description": "Latitude of search center.",
                    },
                    "lng": {
                        "type": "number",
                        "description": "Longitude of search center.",
                    },
                    "radius_km": {
                        "type": "number",
                        "description": "Search radius in kilometers. Default: 50.",
                    },
                    "amenities": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": (
                            "Required amenities: power, water, "
                            "wifi, showers, toilets, waste_disposal."
                        ),
                    },
                    "max_cost_eur": {
                        "type": "number",
                        "description": "Maximum cost per night in EUR.",
                    },
                    "vw_compatible": {
                        "type": "boolean",
                        "description": (
                            "Only show VW California compatible "
                            "campgrounds. Default: true."
                        ),
                    },
                },
                "required": ["lat", "lng"],
            },
        }
    },
    {
        "type": "function",
        "function": {
            "name": "plan_route",
            "description": (
                "Plan a multi-day driving route with campground stops. "
                "Generates daily schedules with waypoints, driving time "
                "estimates, and weather forecasts."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "origin": {
                        "type": "object",
                        "properties": {
                            "label": {"type": "string"},
                            "lat": {"type": "number"},
                            "lng": {"type": "number"},
                        },
                        "required": ["label", "lat", "lng"],
                        "description": "Starting location.",
                    },
                    "destination": {
                        "type": "object",
                        "properties": {
                            "label": {"type": "string"},
                            "lat": {"type": "number"},
                            "lng": {"type": "number"},
                        },
                        "required": ["label", "lat", "lng"],
                        "description": "Ending location. IMPORTANT: If round_trip is true, this MUST be the furthest turnaround point of the journey (e.g. Istanbul), NOT the starting location.",
                    },
                    "waypoints": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "label": {"type": "string"},
                                "lat": {"type": "number"},
                                "lng": {"type": "number"},
                            },
                            "required": ["label", "lat", "lng"],
                        },
                        "description": "Optional list of intermediate places to visit along the route (e.g., Medjugorje, Romania).",
                    },
                    "num_days": {
                        "type": "integer",
                        "description": "Number of travel days.",
                    },
                    "start_date": {
                        "type": "string",
                        "description": "Start date in YYYY-MM-DD.",
                    },
                    "round_trip": {
                        "type": "boolean",
                        "description": "Whether the trip is a round-trip returning to the origin.",
                    },
                    "max_daily_drive_hours": {
                        "type": "number",
                        "description": "Maximum driving hours per day. Default: 6.",
                    },
                    "preferred_amenities": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Preferred camping amenities.",
                    },
                    "budget_per_night_eur": {
                        "type": "number",
                        "description": "Maximum nightly budget in EUR.",
                    },
                    "notes": {
                        "type": "string",
                        "description": (
                            "Extra context: places to avoid, preferred "
                            "overnight environments, special requests."
                        ),
                    },
                },
                "required": ["origin", "destination", "num_days", "start_date"],
            },
        }
    },
    {
        "type": "function",
        "function": {
            "name": "modify_route",
            "description": (
                "Modify an existing trip route. Use when the user wants to "
                "remove or replace an overnight stop, avoid a specific town, "
                "or significantly restructure any day. Re-plans the full "
                "route with updated constraints."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "trip_id": {
                        "type": "string",
                        "description": "UUID of the active trip to modify.",
                    },
                    "exclude_places": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "List of place names to avoid.",
                    },
                    "preferred_overnight": {
                        "type": "string",
                        "description": (
                            "Preferred overnight environment description "
                            "(e.g. 'forest without mosquitoes', 'lakeside', "
                            "'mountain with views')."
                        ),
                    },
                    "notes": {
                        "type": "string",
                        "description": "Additional modification instructions.",
                    },
                    "origin": {
                        "type": "object",
                        "properties": {
                            "label": {"type": "string"},
                            "lat": {"type": "number"},
                            "lng": {"type": "number"},
                        },
                        "description": "Override origin (optional).",
                    },
                    "destination": {
                        "type": "object",
                        "properties": {
                            "label": {"type": "string"},
                            "lat": {"type": "number"},
                            "lng": {"type": "number"},
                        },
                        "description": "Override destination (optional).",
                    },
                    "num_days": {
                        "type": "integer",
                        "description": "Override number of days (optional).",
                    },
                    "start_date": {
                        "type": "string",
                        "description": "Override start date (optional).",
                    },
                },
                "required": ["trip_id"],
            },
        }
    },
    {
        "type": "function",
        "function": {
            "name": "add_attraction",
            "description": (
                "Add a point of interest (POI) such as an aquapark, museum, "
                "lake, or viewpoint to a specific day of the current trip. "
                "Can be added as a daytime stop or replace the overnight stop."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "trip_id": {
                        "type": "string",
                        "description": "UUID of the active trip.",
                    },
                    "day_number": {
                        "type": "integer",
                        "description": "Day number to add the attraction to (1-indexed).",
                    },
                    "query": {
                        "type": "string",
                        "description": (
                            "Natural language search query for the attraction "
                            "(e.g. 'large aquapark near Wolfsburg')."
                        ),
                    },
                    "lat": {
                        "type": "number",
                        "description": "Optional latitude hint for location bias.",
                    },
                    "lng": {
                        "type": "number",
                        "description": "Optional longitude hint for location bias.",
                    },
                    "is_overnight": {
                        "type": "boolean",
                        "description": "If true, this POI replaces the overnight stop for the day. If false, it's added as a daytime stop.",
                    },
                },
                "required": ["trip_id", "day_number", "query"],
            },
        }
    },
    {
        "type": "function",
        "function": {
            "name": "suggest_attractions",
            "description": (
                "Search for attractions (castles, lakes, restaurants) near the route. "
                "Ask the user for preferences if they haven't provided them."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "trip_id": {
                        "type": "string",
                        "description": "UUID of the active trip.",
                    },
                    "preferences": {
                        "type": "string",
                        "description": "User preferences for attractions (e.g. 'castles', 'nature', 'museums').",
                    },
                },
                "required": ["trip_id", "preferences"],
            },
        }
    },
    {
        "type": "function",
        "function": {
            "name": "edit_waypoint",
            "description": (
                "Edit, remove, or move a waypoint (attraction, camping, etc.) from the route."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "trip_id": {
                        "type": "string",
                        "description": "UUID of the active trip.",
                    },
                    "day_number": {
                        "type": "integer",
                        "description": "Day number where the waypoint currently is.",
                    },
                    "action": {
                        "type": "string",
                        "enum": ["remove", "replace", "move"],
                        "description": "The action to perform on the waypoint.",
                    },
                    "waypoint_index": {
                        "type": "integer",
                        "description": "The order index of the waypoint to edit (0 is start).",
                    },
                    "target_day_number": {
                        "type": "integer",
                        "description": "For 'move' action: the destination day number.",
                    },
                },
                "required": ["trip_id", "day_number", "action", "waypoint_index"],
            },
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_trip_summary",
            "description": (
                "Retrieve the current trip overview, including all daily "
                "schedules, campgrounds, and driving statistics."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "trip_id": {
                        "type": "string",
                        "description": "UUID of the trip.",
                    },
                },
                "required": ["trip_id"],
            },
        }
    },
]

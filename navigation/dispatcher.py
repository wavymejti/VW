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
from tools.generate_summary import get_trip_summary


# Registry of tool functions callable by the AI
TOOL_REGISTRY = {
    "search_campings": search_campings,
    "plan_route": plan_route,
    "upload_photos": store_photo,
    "suggest_attractions": suggest_attractions,
    "get_trip_summary": get_trip_summary,
    # modify_route, add_attraction, edit_waypoint are handled inline below
}


def _sanitize_trip_start_date(raw_date):
    """
    Make sure a trip starts today or later.

    A date in the past means the next occurrence of that day ("1 July" asked in
    November -> 1 July next year), unless it is only a few days back (a model
    slip for "today"), which becomes today. Older years (model priors such as
    2023) are moved forward the same way.
    """
    today = datetime.now().date()
    if not raw_date:
        return today.strftime("%Y-%m-%d")
    try:
        dt = datetime.strptime(str(raw_date)[:10], "%Y-%m-%d").date()
    except Exception:
        return today.strftime("%Y-%m-%d")
    if dt >= today:
        return dt.strftime("%Y-%m-%d")

    def _with_year(year):
        try:
            return dt.replace(year=year)
        except ValueError:  # 29 February
            return dt.replace(year=year, day=28)

    candidate = _with_year(today.year)
    if candidate < today:
        if (today - candidate).days <= 14:
            return today.strftime("%Y-%m-%d")
        candidate = _with_year(today.year + 1)
    return candidate.strftime("%Y-%m-%d")


def dispatch(function_name, arguments):
    """
    Dispatch an OpenAI function call to the appropriate tool.

    Args:
        function_name (str): Name of the function to call.
        arguments (dict): Arguments extracted by the model.

    Returns:
        dict: Tool execution result.
    """
    # Sanitize dates for trip planning tools to ensure year 2026
    if function_name == "plan_route" and isinstance(arguments, dict):
        arguments["start_date"] = _sanitize_trip_start_date(arguments.get("start_date"))

    if function_name == "search_campings" and isinstance(arguments, dict):
        try:
            lat, lng = float(arguments.get("lat")), float(arguments.get("lng"))
        except (TypeError, ValueError):
            lat = lng = 0.0
        if abs(lat) < 0.01 and abs(lng) < 0.01:
            return {"status": "error",
                    "message": "No location given (0, 0). Ask the user where to search."}

    # Inline handlers for mutation tools
    if function_name == "modify_route":
        return _handle_modify_route(arguments)
    if function_name == "add_attraction":
        return _handle_add_attraction(arguments)
    if function_name == "add_waypoint":
        return _handle_add_waypoint(arguments)
    if function_name == "set_overnight":
        return _handle_set_overnight(arguments)
    if function_name == "edit_waypoint":
        return _handle_edit_waypoint(arguments)
    if function_name == "find_route_stops":
        return _handle_find_route_stops(arguments)
    if function_name == "add_route_stop":
        return _handle_add_route_stop(arguments)

    if function_name not in TOOL_REGISTRY:
        return {
            "status": "error",
            "message": (
                f"Unknown function: '{function_name}'. "
                f"Available: {list(TOOL_REGISTRY.keys()) + ['modify_route', 'add_attraction', 'add_waypoint', 'edit_waypoint']}"
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


def _existing_stays(sched_rows, destination=None):
    """
    Rebuild `stays` and `rest_day_every` from a stored trip, so re-planning keeps them.

    Stay days are days whose waypoints are all of type "stay" (stay_kind "stay" or "rest").
    """
    from tools.plan_route import _haversine_distance

    stays, first_rest_after, driving = [], None, 0
    current = None
    for row in sched_rows:
        wps = row[1]
        if isinstance(wps, str):
            try:
                wps = json.loads(wps)
            except Exception:
                wps = []
        wps = wps or []
        if wps and all(w.get("type") == "stay" for w in wps):
            w = wps[0]
            if w.get("stay_kind") == "rest":
                if first_rest_after is None:
                    first_rest_after = driving
                current = None
                continue
            if current and abs(current["lat"] - w["lat"]) < 1e-6 and abs(current["lng"] - w["lng"]) < 1e-6:
                current["days"] += 1
            else:
                current = {"label": w.get("label"), "lat": w["lat"], "lng": w["lng"], "days": 1}
                if destination and destination.get("lat") is not None and _haversine_distance(
                        w["lat"], w["lng"], destination["lat"], destination["lng"]) <= 30:
                    current = {"label": None, "days": 1, "lat": w["lat"], "lng": w["lng"],
                               "_dest": True}
                stays.append(current)
        else:
            driving += 1
            current = None
    out = []
    for st in stays:
        if st.get("_dest"):
            out.append({"days": st["days"]})
        else:
            out.append({"label": st["label"], "lat": st["lat"], "lng": st["lng"], "days": st["days"]})
    return out, (first_rest_after or None)


# Parameters of modify_route that actually change a trip (notes alone don't).
MODIFY_CHANGE_KEYS = (
    "waypoints", "via_places", "include_places", "exclude_places", "round_trip",
    "overnight_stops", "origin", "destination", "num_days", "start_date",
    "max_daily_km", "max_daily_drive_hours", "preferred_amenities",
    "overnight_preferences", "preferred_overnight", "stays", "rest_day_every",
)


def _near(a, b, km):
    from tools.plan_route import _haversine_distance
    try:
        return _haversine_distance(float(a["lat"]), float(a["lng"]), float(b["lat"]), float(b["lng"])) <= km
    except (TypeError, ValueError, KeyError):
        return False


def _keep_trip_shape(route_stops, via_points, exclude_places, origin_changed, waypoints, stays):
    """
    A trip from the start form / a drawn line is re-planned with its route_stops and via_points,
    so its order and drawing survive a change made in the chat. Returns
    (route_stops, via_points, waypoints, stays) with:
    - excluded places removed from route_stops (and their attractions);
    - the drive-through stops dropped from the waypoints and the stays of multi-night
      stops dropped from the stays read back from the days: route_stops brings them back once;
    - the drawing dropped when the start or the end changes (the line no longer fits).
    """
    def excluded(label):
        return any(ex and ex.lower() in (label or "").lower() for ex in exclude_places or [])

    route_stops = [st for st in (route_stops or []) if not excluded(st.get("label"))]
    via_points = [] if origin_changed else list(via_points or [])
    attractions = [w for w in waypoints
                   if not (isinstance(w, dict) and any(_near(w, st, 2) for st in route_stops))]
    if stays:
        multi = [st for st in route_stops if (st.get("nights") or 0) >= 2]
        stays = [sd for sd in stays if not (sd.get("lat") is not None and any(_near(sd, st, 30) for st in multi))]
    return route_stops, via_points, attractions, stays


def _moved(asked, saved):
    """True when a start or an end asked for is a different place than the saved one."""
    for a, b in zip(asked, saved):
        if not a or not b:
            continue
        if isinstance(a, str):
            a = {"label": a}
        if a.get("lat") is not None:
            if not _near(a, b, 5):
                return True
        elif (a.get("label") or "").strip().lower() not in ((b.get("label") or "").lower(), ""):
            first = (a.get("label") or "").split(",")[0].strip().lower()
            if first and first not in (b.get("label") or "").lower():
                return True
    return False


def has_concrete_change(arguments):
    return any((arguments or {}).get(k) not in (None, "", []) for k in MODIFY_CHANGE_KEYS)


def _handle_find_route_stops(arguments):
    """Chat tool: where and when to stop for fuel / charging / lunch (Google Places, basic fields)."""
    from tools.trip_store import get_trip_data
    from tools.route_stops import plan_route_stops

    data = get_trip_data(arguments.get("trip_id")) if arguments.get("trip_id") else None
    schedules = (data or {}).get("daily_schedules") or arguments.get("schedules")
    if not schedules:
        return {"status": "error", "code": "not_saved", "message": "No planned route to search along."}
    result = plan_route_stops(schedules, arguments.get("kind"), arguments.get("vehicle") or "diesel",
                              arguments.get("departure") or "09:00", arguments.get("day_number"))
    if result.get("status") == "success":
        result["saved_trip"] = bool(data)
    return result


def _handle_add_route_stop(arguments):
    """Chat tool: put one place from find_route_stops on its day (saved trips)."""
    from navigation.route_stop_add import add_route_stop

    place = {k: arguments.get(k) for k in ("name", "lat", "lng", "place_id")}
    result = add_route_stop(arguments.get("trip_id"), arguments.get("day_number"), place,
                            arguments.get("kind"), arguments.get("eta"))
    if result.get("status") == "success":
        data = result.pop("trip_data") or {}
        # The map's summary reads the totals from the top level (as set_overnight returns them).
        result.update({"trip": data.get("trip"), "daily_schedules": data.get("daily_schedules"),
                       "total_driving_km": data.get("total_driving_km"),
                       "total_driving_hours": data.get("total_driving_hours"),
                       "trip_id": arguments.get("trip_id")})
    return result


def _handle_set_overnight(arguments):
    """Chat tool: change the campsite of one night, leaving the rest of the trip as it is."""
    from tools.trip_store import get_trip_data

    trip_id = arguments.get("trip_id")
    day_number = arguments.get("day_number")
    camp = arguments.get("campsite") or {
        k: arguments.get(k) for k in ("name", "lat", "lng", "place_id")}
    try:
        camp = {"name": camp.get("name") or camp.get("label") or "Campsite",
                "lat": float(camp["lat"]), "lng": float(camp["lng"]),
                "place_id": camp.get("place_id"), "id": camp.get("id")}
        day_number = int(day_number)
    except (TypeError, ValueError, KeyError):
        return {"status": "error",
                "message": "set_overnight needs trip_id, day_number and a campsite with name, lat and lng "
                           "(take them from search_campings results or the day's overnight options)."}
    if not trip_id or get_trip_data(trip_id) is None:
        return {"status": "error",
                "message": "This trip is not saved (the user may not be logged in). Use modify_route with "
                           f"overnight_stops [{{'label': '{camp['name']}', 'lat': {camp['lat']}, "
                           f"'lng': {camp['lng']}}}] instead."}
    result = apply_campsite_change(trip_id, day_number, camp)
    if result.get("status") != "success":
        result.pop("http_status", None)
        return result
    data = get_trip_data(trip_id) or {}
    return {
        "status": "success",
        "message": f"Night after day {result['day_number']} is now at {camp['name']}; the other nights are unchanged.",
        "trip_id": trip_id,
        "trip": data.get("trip"),
        "daily_schedules": data.get("daily_schedules"),
        "total_driving_km": data.get("total_driving_km"),
        "total_driving_hours": data.get("total_driving_hours"),
    }


def apply_campsite_change(trip_id, day_number, camping):
    """
    Put a chosen campsite on one night of a stored trip, without re-planning it.

    A stay day sleeps where the previous driving day ended, so that day is changed;
    the stay days after it move with it and the next driving day starts there.
    Shared by POST /api/select_camping (campsite modal) and the set_overnight chat tool.

    Returns:
        dict: {"status": "success", "day_number": n} or an error with "http_status".
    """
    from sqlalchemy import text
    from tools.db import get_engine

    def _is_stay(wps):
        if isinstance(wps, str):
            wps = json.loads(wps)
        return bool(wps) and all(w.get("type") == "stay" for w in wps)

    try:
        engine = get_engine()
        with engine.begin() as conn:
            schedule_row = conn.execute(
                text("SELECT id, waypoints FROM daily_schedules WHERE trip_id = :tid AND day_number = :day"),
                {"tid": trip_id, "day": day_number}
            ).fetchone()

            if not schedule_row:
                return {"status": "error", "message": "Day schedule not found (is the trip saved?)", "http_status": 404}

            # A stay day sleeps where the previous driving day ended: change that day.
            while _is_stay(schedule_row[1]) and int(day_number) > 1:
                day_number = int(day_number) - 1
                schedule_row = conn.execute(
                    text("SELECT id, waypoints FROM daily_schedules WHERE trip_id = :tid AND day_number = :day"),
                    {"tid": trip_id, "day": day_number}
                ).fetchone()
                if not schedule_row:
                    return {"status": "error", "message": "Day schedule not found (is the trip saved?)", "http_status": 404}

            schedule_id = schedule_row[0]
            waypoints = schedule_row[1] or []

            if not waypoints:
                return {"status": "error", "message": "No waypoints found for this day", "http_status": 400}

            # Replace the last waypoint (which is the overnight camping or destination)
            new_wp = {
                "order": len(waypoints) - 1,
                "type": "camping",
                "label": camping.get("name", "Camping"),
                "lat": camping.get("lat"),
                "lng": camping.get("lng"),
                "place_id": camping.get("place_id"),
                "notes": "User selected camping"
            }
            waypoints[-1] = new_wp

            # Update db and recalculate
            update_done = _recalculate_day_route(conn, schedule_id, waypoints)
            if not update_done:
                conn.execute(
                    text("UPDATE daily_schedules SET waypoints = CAST(:wps AS jsonb), overnight_camping_id = :cid WHERE id = :sid"),
                    {"wps": json.dumps(waypoints), "cid": camping.get("id"), "sid": str(schedule_id)}
                )

            # Stay days right after this day move to the new campsite too.
            next_number = int(day_number) + 1
            while True:
                stay_row = conn.execute(
                    text("SELECT id, waypoints FROM daily_schedules WHERE trip_id = :tid AND day_number = :day"),
                    {"tid": trip_id, "day": next_number}
                ).fetchone()
                if not stay_row or not _is_stay(stay_row[1]):
                    break
                stay_wps = stay_row[1] if not isinstance(stay_row[1], str) else json.loads(stay_row[1])
                stay_wps = [{**stay_wps[0],
                             "label": camping.get("name", "Camping"),
                             "lat": camping.get("lat"), "lng": camping.get("lng"),
                             "place_id": camping.get("place_id")}]
                conn.execute(
                    text("UPDATE daily_schedules SET waypoints = CAST(:wps AS jsonb), overnight_camping_id = :cid WHERE id = :sid"),
                    {"wps": json.dumps(stay_wps), "cid": camping.get("id"), "sid": str(stay_row[0])}
                )
                next_number += 1

            # Update start location of the next driving day if it exists
            next_day_row = conn.execute(
                text("SELECT id, waypoints FROM daily_schedules WHERE trip_id = :tid AND day_number = :day"),
                {"tid": trip_id, "day": next_number}
            ).fetchone()
            if next_day_row:
                next_sid = next_day_row[0]
                next_wps = next_day_row[1] or []
                if isinstance(next_wps, str):
                    next_wps = json.loads(next_wps)
                if next_wps:
                    next_wps[0] = {
                        "order": 0,
                        "type": "start",
                        "label": camping.get("name", "Start"),
                        "lat": camping.get("lat"),
                        "lng": camping.get("lng")
                    }
                    _recalculate_day_route(conn, next_sid, next_wps)

        return {"status": "success", "day_number": int(day_number)}
    except Exception as e:
        return {"status": "error", "message": str(e), "http_status": 500}


def _handle_modify_route(arguments):
    """
    Handle route modification by re-planning with amended parameters.

    Accepts exclude_places, waypoints/include_places, force_overnight_change,
    round_trip, and other overrides on top of the original trip parameters.
    Falls back to a fresh plan_route call with the updated context.

    Args:
        arguments (dict): May include trip_id, origin, destination,
            num_days, start_date, waypoints, exclude_places, preferred_overnight,
            preferred_amenities, wild_camping, notes, round_trip.

    Returns:
        dict: New trip data from plan_route.
    """
    try:
        from tools.db import get_engine
        from sqlalchemy import text
        import json

        trip_id = arguments.get("trip_id")
        exclude_places = arguments.get("exclude_places", []) or []
        preferred_overnight = arguments.get("preferred_overnight")
        overnight_stops = arguments.get("overnight_stops")
        max_daily_km = arguments.get("max_daily_km")
        overnight_preferences = arguments.get("overnight_preferences")
        stays = arguments.get("stays")
        rest_day_every = arguments.get("rest_day_every")
        if not overnight_preferences and preferred_overnight:
            # Older calls describe the surroundings only in free text: apply it to every night.
            overnight_preferences = [{"setting": preferred_overnight}]
        max_daily_drive_hours = arguments.get("max_daily_drive_hours")
        notes = arguments.get("notes", "")

        # The planner can't read free-text notes: without a concrete change it would
        # re-plan the same route and store a duplicate trip.
        if not has_concrete_change(arguments):
            return {
                "status": "error",
                "message": (
                    "Nothing to change: the planner does not read `notes`. Pass the change "
                    "as parameters — e.g. max_daily_km for a daily distance limit, num_days "
                    "for more/fewer days, overnight_stops for a town to sleep in, "
                    "overnight_preferences for surroundings (lake, forest...), "
                    "waypoints / exclude_places."
                ),
            }

        # Fetch original trip parameters from DB if trip_id provided
        origin = arguments.get("origin")
        destination = arguments.get("destination")
        asked_ends, saved_ends = (origin, destination), (None, None)
        num_days = arguments.get("num_days")
        start_date = arguments.get("start_date")
        preferred_amenities = arguments.get("preferred_amenities")
        user_id = arguments.get("user_id")
        round_trip = arguments.get("round_trip")

        # Extract newly requested waypoints / via places
        raw_waypoints = (
            arguments.get("waypoints")
            or arguments.get("via_places")
            or arguments.get("include_places")
            or []
        )
        if isinstance(raw_waypoints, (str, dict)):
            raw_waypoints = [raw_waypoints]

        existing_attractions = []

        if trip_id:
            try:
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
                        saved_ends = ({"label": row[0], "lat": float(row[1]), "lng": float(row[2])},
                                      {"label": row[3], "lat": float(row[4]), "lng": float(row[5])})
                        origin = origin or saved_ends[0]
                        destination = destination or saved_ends[1]
                        if not num_days and row[6] and row[7]:
                            num_days = (row[7] - row[6]).days + 1
                        start_date = start_date or str(row[6])
                        user_id = user_id or (str(row[8]) if row[8] else None)

                    # Inspect daily schedules to detect round_trip and preserve existing waypoints
                    sched_rows = conn.execute(
                        text(
                            "SELECT day_number, waypoints FROM daily_schedules "
                            "WHERE trip_id = :id ORDER BY day_number ASC"
                        ),
                        {"id": trip_id}
                    ).fetchall()

                    if sched_rows:
                        if round_trip is None:
                            # Check if last waypoint of the last day matches origin
                            last_day_wps = sched_rows[-1][1]
                            if isinstance(last_day_wps, str):
                                try:
                                    last_day_wps = json.loads(last_day_wps)
                                except Exception:
                                    last_day_wps = []
                            if last_day_wps:
                                last_wp = last_day_wps[-1]
                                if origin:
                                    is_match_label = (
                                        last_wp.get("label")
                                        and last_wp.get("label") == origin.get("label")
                                    )
                                    is_match_coords = (
                                        abs(float(last_wp.get("lat", 0)) - float(origin.get("lat", 0))) < 0.05
                                        and abs(float(last_wp.get("lng", 0)) - float(origin.get("lng", 0))) < 0.05
                                    )
                                    if is_match_label or is_match_coords:
                                        round_trip = True

                        if stays is None or rest_day_every is None:
                            got_stays, got_rest = _existing_stays(sched_rows, destination)
                            if stays is None and got_stays:
                                stays = got_stays
                            if rest_day_every is None and got_rest:
                                rest_day_every = got_rest

                        for sr in sched_rows:
                            wps = sr[1]
                            if isinstance(wps, str):
                                try:
                                    wps = json.loads(wps)
                                except Exception:
                                    wps = []
                            for wp in (wps or []):
                                if wp.get("type") in ("attraction", "waypoint"):
                                    wp_label = wp.get("label", "")
                                    # Filter out excluded places
                                    if any(ex.lower() in wp_label.lower() for ex in exclude_places if ex):
                                        continue
                                    existing_attractions.append(wp)
            except Exception as e:
                print(f"Error reading existing trip context in modify_route: {e}")

        if not all([origin, destination, num_days, start_date]):
            try:
                engine = get_engine()
                with engine.connect() as conn:
                    # Only the same user's latest trip — never another user's.
                    row = None
                    if user_id:
                        row = conn.execute(
                            text("SELECT origin_label, origin_lat, origin_lng, destination_label, destination_lat, destination_lng, start_date, end_date, user_id, id FROM trips WHERE user_id = :uid ORDER BY created_at DESC LIMIT 1"),
                            {"uid": user_id},
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

        # Stops from the start form and a drawn line: keep their order / shape (see _keep_trip_shape).
        route_stops = arguments.get("route_stops")
        via_points = arguments.get("via_points")
        if trip_id and route_stops is None and via_points is None:
            from tools.plan_route import load_plan_params
            saved = load_plan_params(trip_id)
            route_stops, via_points = saved.get("route_stops"), saved.get("via_points")
        origin_changed = bool(arguments.get("_origin_changed")) or _moved(asked_ends, saved_ends)

        if not all([origin, destination, num_days, start_date]):
            return {
                "status": "error",
                "message": (
                    "Insufficient parameters for route modification. "
                    "Origin, destination, num_days, and start_date are required."
                ),
            }

        if round_trip is None:
            if origin.get("label") == destination.get("label") or (
                origin.get("lat") == destination.get("lat") and origin.get("lng") == destination.get("lng")
            ):
                round_trip = True
            else:
                round_trip = False

        # Merge newly requested waypoints with existing waypoints
        all_waypoints = []
        seen_keys = set()
        for wp in raw_waypoints:
            lbl = (wp.get("label") or wp.get("name") if isinstance(wp, dict) else str(wp)).strip()
            if any(ex.lower() in lbl.lower() for ex in exclude_places if ex):
                continue
            all_waypoints.append(wp)
            seen_keys.add(lbl.lower())

        # Attractions of the trip planned in this conversation (anonymous trips and
        # trips that failed to save are not in the DB).
        if not existing_attractions:
            for wp in arguments.get("_conversation_waypoints") or []:
                lbl = (wp.get("label") or "")
                if not any(ex.lower() in lbl.lower() for ex in exclude_places if ex):
                    existing_attractions.append(wp)

        for wp in existing_attractions:
            lbl = wp.get("label", "").strip()
            if lbl.lower() not in seen_keys and not any(ex.lower() in lbl.lower() for ex in exclude_places if ex):
                all_waypoints.append(wp)
                seen_keys.add(lbl.lower())

        # Build exclusion note for the routing engine
        extra_notes = []
        if exclude_places:
            extra_notes.append(f"Avoid these places: {', '.join(exclude_places)}")
        if preferred_overnight:
            extra_notes.append(f"Preferred overnight environment: {preferred_overnight}")
        if notes:
            extra_notes.append(notes)

        if route_stops or via_points:
            route_stops, via_points, all_waypoints, stays = _keep_trip_shape(
                route_stops, via_points, exclude_places, origin_changed, all_waypoints, stays)

        start_date = _sanitize_trip_start_date(start_date)

        result = plan_route(
            origin=origin,
            destination=destination,
            num_days=num_days,
            start_date=start_date,
            preferred_amenities=preferred_amenities,
            user_id=user_id,
            notes=" | ".join(extra_notes) if extra_notes else None,
            round_trip=bool(round_trip),
            waypoints=all_waypoints,
            overnight_stops=overnight_stops,
            max_daily_km=max_daily_km,
            overnight_preferences=overnight_preferences,
            stays=stays,
            rest_day_every=rest_day_every,
            allow_far_waypoints=bool(arguments.get("allow_far_waypoints")),
            route_stops=route_stops or None,
            via_points=via_points or None,
            **({"max_daily_drive_hours": max_daily_drive_hours} if max_daily_drive_hours else {}),
        )

        # Tag result as a route modification
        if result.get("status") == "success":
            result["mutation_type"] = "modify_route"
            result["excluded_places"] = exclude_places
            result["waypoints"] = all_waypoints

        return result

    except Exception as e:
        return {"status": "error", "message": f"modify_route failed: {e}"}


def _handle_add_waypoint(arguments):
    """
    Handle adding a waypoint or via-point to the route.
    If day_number is specified, delegates to _handle_add_attraction.
    Otherwise delegates to _handle_modify_route with waypoints=[...].
    """
    day_number = arguments.get("day_number")
    label = arguments.get("label") or arguments.get("query") or arguments.get("name")
    trip_id = arguments.get("trip_id")
    lat = arguments.get("lat")
    lng = arguments.get("lng")

    if not trip_id or not label:
        return {"status": "error", "message": "trip_id and label are required for add_waypoint."}

    if day_number is not None:
        return _handle_add_attraction({
            "trip_id": trip_id,
            "day_number": day_number,
            "query": label,
            "lat": lat,
            "lng": lng,
            "is_overnight": False,
        })

    # Otherwise route modification with via point
    wp_dict = {"label": label}
    if lat is not None and lng is not None:
        wp_dict["lat"] = lat
        wp_dict["lng"] = lng

    mod_args = dict(arguments)
    mod_args["waypoints"] = [wp_dict]
    return _handle_modify_route(mod_args)



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

        from tools.maps_client import maps_allows, disabled_message
        if not maps_allows("places"):
            return {"status": "error", "message": disabled_message()}
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

        from tools.maps_client import places_text_basic
        if maps_allows("places_rich"):
            places_result = gmaps.places(**search_kwargs)
        else:
            # Basic fields only (no photos, ratings or contact data — cost switch)
            places_result = places_text_basic(query, lat, lng)

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

            types = place.get("types", [])
            from tools.suggest_attractions import CATEGORY_MAP
            cat_emoji, cat_color, cat_label = "⭐", "#F9A825", "Atrakcja"
            for t in types:
                if t in CATEGORY_MAP:
                    cat_emoji, cat_color, cat_label = CATEGORY_MAP[t]
                    break

            new_waypoint = {
                "order": len(existing_waypoints),
                "type": "camping" if is_overnight else "attraction",
                "label": attraction["name"],
                "lat": attraction["lat"],
                "lng": attraction["lng"],
                "place_id": attraction["place_id"],
                "address": attraction.get("address", ""),
                "rating": attraction.get("rating"),
                "category_label": cat_label,
                "emoji": cat_emoji,
                "color": cat_color,
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

        # Invalidate attractions cache on server
        try:
            from tools.server import _ATTRACTIONS_CACHE
            cache_keys = [k for k in list(_ATTRACTIONS_CACHE.keys()) if k.startswith(f"{trip_id}:")]
            for k in cache_keys:
                _ATTRACTIONS_CACHE.pop(k, None)
        except Exception:
            pass

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
            from tools.plan_route import thin_via
            waypoints = [waypoints[0], *thin_via(waypoints[1:-1]), waypoints[-1]]
            dest_wp = waypoints[-1]
            intermediates = waypoints[1:-1]
            # "via" points come from a line drawn on the map: pass through them in order.
            directions_kwargs["waypoints"] = [
                (f"via:{w['lat']},{w['lng']}" if w.get("type") == "via" else f"{w['lat']},{w['lng']}")
                for w in intermediates]
            if not any(w.get("type") == "via" for w in intermediates):
                directions_kwargs["optimize_waypoints"] = True

        directions = client.directions(**directions_kwargs)
        
        if directions:
            route = directions[0]
            legs = route.get("legs", [])
            new_distance = sum(l["distance"]["value"] for l in legs) / 1000
            new_duration = sum(l["duration"]["value"] for l in legs) / 3600
            new_polyline = route["overview_polyline"]["points"]
            
            if len(waypoints) > 2 and directions_kwargs.get("optimize_waypoints"):
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
                "Plan a NEW multi-day driving route with campground stops "
                "(also when a trip already exists but the user wants a different "
                "origin or destination). Each travel day except the last ends at a "
                "campsite, so the number of nights = num_days - 1. A trip that ends in a "
                "DIFFERENT city than it starts (Poznań -> Lausanne -> Warsaw) is one-way to the "
                "final city with the turnaround as a stay ({'label': 'Lausanne', 'days': N}) "
                "or an overnight stop — not a round trip. "
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
                        "description": (
                            "Optional list of intermediate places to visit along the route. Each one a "
                            "CONCRETE named place (e.g. 'Neuschwanstein Castle', 'Medjugorje') — never a "
                            "category or area ('largest castles', 'wooden churches in Saxony'). For a "
                            "category, plan the route first, then call suggest_attractions and add the "
                            "places the user picks. Places far off the route are skipped with a warning. "
                            "A place where the user wants to SLEEP goes to overnight_stops, not here (a place close to where a day ends becomes that night's place anyway)."
                        ),
                    },
                    "num_days": {
                        "type": "integer",
                        "description": (
                            "Number of trip days = number of nights + 1. "
                            "One night on the way (e.g. 'Poznań to Berlin with a stop "
                            "overnight in between') = 2. num_days = 1 means driving "
                            "straight through with NO overnight stop."
                        ),
                    },
                    "overnight_stops": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "label": {"type": "string", "description": "Town/area where the user wants to sleep."},
                                "lat": {"type": "number"},
                                "lng": {"type": "number"},
                            },
                            "required": ["label"],
                        },
                        "description": (
                            "Specific places where the user wants to spend a night, in travel order "
                            "(e.g. [{'label': 'Frankfurt (Oder)'}]). Each one ends a travel day and the "
                            "planner looks for a campsite near it. Leave empty if the user only said "
                            "'one night on the way' without a place — then just set num_days."
                        ),
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
                    "overnight_preferences": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "setting": {"type": "string", "description": "Wanted surroundings, e.g. 'by a lake', 'in a forest', 'by the sea', 'in the mountains'."},
                                "day_number": {"type": "integer", "description": "Night after this travel day (1 = first night). Omit for every night."},
                            },
                            "required": ["setting"],
                        },
                        "description": (
                            "Where the user wants to sleep in terms of surroundings, without naming a town "
                            "(e.g. 'on day 2 I want to sleep by a lake' -> [{'day_number': 2, 'setting': 'by a lake'}]). "
                            "The planner picks a matching campsite near that night's stop."
                        ),
                    },
                    "allow_far_waypoints": {
                        "type": "boolean",
                        "description": "Keep waypoints far off the direct route. Only after the user confirmed a big detour.",
                    },
                    "stays": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "label": {"type": "string", "description": "Place of the stay; omit for the destination (turnaround point of a round trip)."},
                                "days": {"type": "integer", "description": "Full days spent there without driving."},
                            },
                            "required": ["days"],
                        },
                        "description": (
                            "Days without driving, spent at one place, e.g. 'a week in Dubrovnik' -> "
                            "[{'label': 'Dubrovnik', 'days': 7}], '2 days in Paris' -> [{'label': 'Paris', 'days': 2}]. "
                            "They count INTO num_days: num_days = driving days + stay days + rest days. "
                            "In a round trip a stay at the destination splits the trip into outbound and return."
                        ),
                    },
                    "rest_day_every": {
                        "type": "integer",
                        "description": (
                            "Add one day off at the campsite after every N driving days. Set it ONLY "
                            "when the user asks for days off / a slow pace with breaks (e.g. 'a rest "
                            "day every 3 days' -> 3) — never from default assumptions, and not when "
                            "they want to just drive. Counts into num_days."
                        ),
                    },
                    "max_daily_km": {
                        "type": "number",
                        "description": (
                            "Maximum driving distance per day in km, when the user gives one "
                            "(e.g. 'max 500 km a day', 'about 400 km per day'). The planner adds "
                            "days if needed and splits the route into equal-distance days."
                        ),
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
            "name": "set_overnight",
            "description": (
                "Change the campsite of ONE night without re-planning the trip — the other nights, "
                "days and stops stay exactly as they are. Use it when the user wants to sleep "
                "somewhere else on a given night (a free spot, a campsite they picked, one from "
                "search_campings results or the day's overnight options). For a stay of several days "
                "the whole stay moves to the new campsite. Prefer this over modify_route for "
                "changing a night. For 'sleep near X': call search_campings near X first, then "
                "this in the same turn with the closest proper campsite, on the day whose route "
                "passes X."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "trip_id": {"type": "string", "description": "UUID of the active trip."},
                    "day_number": {
                        "type": "integer",
                        "description": "The travel day whose night changes (1 = the night after day 1).",
                    },
                    "campsite": {
                        "type": "object",
                        "properties": {
                            "name": {"type": "string"},
                            "lat": {"type": "number"},
                            "lng": {"type": "number"},
                            "place_id": {"type": "string"},
                        },
                        "required": ["name", "lat", "lng"],
                        "description": "The new place to sleep, with exact coordinates from search results.",
                    },
                },
                "required": ["trip_id", "day_number", "campsite"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "modify_route",
            "description": (
                "Modify an existing trip route. Use when the user wants to "
                "add a town/city/place to drive through or visit (e.g. 'Gardelegen'), "
                "remove or replace an overnight stop, avoid a specific town, "
                "or significantly restructure any day. Re-plans the full "
                "route with updated constraints. Do NOT use it for a trip to a "
                "different destination or from a different origin — that is a new "
                "trip: confirm with the user, then call plan_route."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "trip_id": {
                        "type": "string",
                        "description": "UUID of the active trip to modify.",
                    },
                    "waypoints": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "label": {"type": "string", "description": "Name of the place/town to pass through or visit."},
                                "lat": {"type": "number", "description": "Optional latitude."},
                                "lng": {"type": "number", "description": "Optional longitude."},
                            },
                            "required": ["label"],
                        },
                        "description": (
                            "Intermediate places to pass through or visit (e.g. [{'label': 'Gardelegen'}]). "
                            "CONCRETE named places only, never categories ('castles', 'wooden churches') — "
                            "use suggest_attractions to find those. Places already on the trip are kept "
                            "automatically; list only the ones to add."
                            " A place where the user wants to SLEEP goes to overnight_stops, not here (a place close to where a day ends becomes that night's place anyway)."
                        ),
                    },
                    "exclude_places": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "List of place names to avoid or remove.",
                    },
                    "round_trip": {
                        "type": "boolean",
                        "description": "Whether the trip is a round trip returning to origin. Default preserves previous trip setting.",
                    },
                    "preferred_overnight": {
                        "type": "string",
                        "description": (
                            "Deprecated free-text surroundings for every night; prefer "
                            "overnight_preferences (it can target one day)."
                        ),
                    },
                    "overnight_stops": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "label": {"type": "string", "description": "Town/area where the user wants to sleep."},
                                "lat": {"type": "number"},
                                "lng": {"type": "number"},
                            },
                            "required": ["label"],
                        },
                        "description": (
                            "Specific places where the user wants to spend a night, in travel order "
                            "(e.g. [{'label': 'Frankfurt (Oder)'}]). Each one ends a travel day and the "
                            "planner looks for a campsite near it. Leave empty if the user only said "
                            "'one night on the way' without a place — then just set num_days."
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
                        "description": (
                            "Override destination (optional). To END the trip in another city "
                            "(e.g. 'return to Warsaw instead of Poznań'): destination = that city, "
                            "round_trip = false, and the old turnaround (e.g. Lausanne) goes into stays."
                        ),
                    },
                    "overnight_preferences": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "setting": {"type": "string", "description": "Wanted surroundings, e.g. 'by a lake', 'in a forest', 'by the sea', 'in the mountains'."},
                                "day_number": {"type": "integer", "description": "Night after this travel day (1 = first night). Omit for every night."},
                            },
                            "required": ["setting"],
                        },
                        "description": (
                            "Where the user wants to sleep in terms of surroundings, without naming a town "
                            "(e.g. 'on day 2 I want to sleep by a lake' -> [{'day_number': 2, 'setting': 'by a lake'}]). "
                            "The planner picks a matching campsite near that night's stop."
                        ),
                    },
                    "allow_far_waypoints": {
                        "type": "boolean",
                        "description": "Keep waypoints far off the direct route. Only after the user confirmed a big detour.",
                    },
                    "stays": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "label": {"type": "string", "description": "Place of the stay; omit for the destination (turnaround point of a round trip)."},
                                "days": {"type": "integer", "description": "Full days spent there without driving."},
                            },
                            "required": ["days"],
                        },
                        "description": (
                            "Days without driving, spent at one place, e.g. 'a week in Dubrovnik' -> "
                            "[{'label': 'Dubrovnik', 'days': 7}], '2 days in Paris' -> [{'label': 'Paris', 'days': 2}]. "
                            "They count INTO num_days: num_days = driving days + stay days + rest days. "
                            "In a round trip a stay at the destination splits the trip into outbound and return."
                        ),
                    },
                    "rest_day_every": {
                        "type": "integer",
                        "description": (
                            "Add one day off at the campsite after every N driving days. Set it ONLY "
                            "when the user asks for days off / a slow pace with breaks (e.g. 'a rest "
                            "day every 3 days' -> 3) — never from default assumptions, and not when "
                            "they want to just drive. Counts into num_days."
                        ),
                    },
                    "max_daily_km": {
                        "type": "number",
                        "description": (
                            "Maximum driving distance per day in km, when the user gives one "
                            "(e.g. 'max 500 km a day', 'about 400 km per day'). The planner adds "
                            "days if needed and splits the route into equal-distance days."
                        ),
                    },
                    "num_days": {
                        "type": "integer",
                        "description": "Override number of trip days = nights + 1 (optional).",
                    },
                    "start_date": {
                        "type": "string",
                        "description": "Override start date (optional).",
                    },
                },
                "required": ["trip_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "add_waypoint",
            "description": (
                "Add an intermediate town, scenic pass, or waypoint to the route. "
                "Can specify day_number or let the routing engine find the optimal day."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "trip_id": {
                        "type": "string",
                        "description": "UUID of the active trip.",
                    },
                    "label": {
                        "type": "string",
                        "description": "Name of the town, place, or waypoint to add (e.g. 'Gardelegen').",
                    },
                    "day_number": {
                        "type": "integer",
                        "description": "Optional specific day number (1-indexed). If omitted, optimal day is chosen automatically.",
                    },
                    "lat": {
                        "type": "number",
                        "description": "Optional latitude.",
                    },
                    "lng": {
                        "type": "number",
                        "description": "Optional longitude.",
                    },
                },
                "required": ["trip_id", "label"],
            },
        },
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
            "name": "find_route_stops",
            "description": (
                "Where and when to stop along the planned route for fuel (kind 'fuel'), EV charging "
                "('ev_charging') or lunch ('restaurant'). Times assume departure at 09:00 and the "
                "vehicle's range. Leave vehicle out to use the van the user is remembered to travel in "
                "(diesel T6.1 if unknown); set it only when the user names another one. Returns per day the planned time, the reason "
                "and up to 3 places (Google Places) nearest to the route. Tell the user the time and "
                "the best option per stop; add one only when the user wants it (add_route_stop)."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "trip_id": {"type": "string"},
                    "kind": {"type": "string", "enum": ["fuel", "ev_charging", "restaurant"]},
                    "day_number": {"type": "integer", "description": "Only this day (optional)."},
                    "vehicle": {"type": "string", "enum": ["diesel", "phev", "ev"],
                                "description": "diesel = California T6.1, phev = California eHybrid, ev = ID. Buzz."},
                    "departure": {"type": "string", "description": "Departure time HH:MM (default 09:00)."},
                },
                "required": ["kind"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "add_route_stop",
            "description": (
                "Add a fuel / charging / lunch place from find_route_stops results to its day "
                "(exact name, lat, lng from the results; eta = the planned time). Saved trips only."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "trip_id": {"type": "string"},
                    "day_number": {"type": "integer"},
                    "kind": {"type": "string", "enum": ["fuel", "ev_charging", "restaurant"]},
                    "name": {"type": "string"},
                    "lat": {"type": "number"},
                    "lng": {"type": "number"},
                    "place_id": {"type": "string"},
                    "eta": {"type": "string", "description": "Planned time HH:MM."},
                },
                "required": ["day_number", "kind", "name", "lat", "lng"],
            },
        },
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

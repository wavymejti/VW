"""
Putting a fuel / charging / lunch stop on a day of a saved trip (Nov 2026).

The place (from tools/route_stops.py, Google Places) becomes a waypoint of the day at its
position along the route, with an emoji and the planned time; only that day is recalculated.
No Google Places search is made for it (unlike add_attraction).
"""

import json

from googlemaps.convert import decode_polyline

from tools.route_stops import KIND_EMOJI, KIND_LABELS

KIND_COLORS = {"fuel": "#B7472A", "ev_charging": "#00875A", "restaurant": "#8E44AD"}


def _km(a, b):
    from tools.plan_route import _haversine_distance
    return _haversine_distance(a["lat"], a["lng"], b["lat"], b["lng"])


def stop_waypoint(place, kind, eta=None):
    label = KIND_LABELS[kind] + (f" · ~{eta}" if eta else "")
    return {
        "type": "waypoint",
        "service": kind,
        "label": place.get("name") or KIND_LABELS[kind],
        "lat": float(place["lat"]),
        "lng": float(place["lng"]),
        "emoji": KIND_EMOJI[kind],
        "color": KIND_COLORS[kind],
        "category_label": label,
        "notes": f"Planned {KIND_LABELS[kind].lower()}" + (f" around {eta}" if eta else ""),
        "planned_time": eta,
        "place_id": place.get("place_id") or place.get("osm_id"),
    }


def insert_in_order(waypoints, new_wp, polyline):
    """The day's waypoints with new_wp placed among the stops by its position along the route."""
    line = decode_polyline(polyline) if polyline else []

    def pos(w):
        if not line:
            return 0
        return min(range(len(line)), key=lambda i: _km(line[i], w))

    start, end, inner = waypoints[0], waypoints[-1], list(waypoints[1:-1])
    inner.append(new_wp)
    inner.sort(key=pos)
    return [start, *inner, end]


def add_route_stop(trip_id, day_number, place, kind, eta=None):
    """
    Returns:
        dict: {"status": "success", "message", "trip_data"} or {"status": "error", "message"}.
    """
    from sqlalchemy import text
    from tools.db import get_engine
    from tools.trip_store import get_trip_data
    from navigation.dispatcher import _recalculate_day_route

    if kind not in KIND_LABELS:
        return {"status": "error", "message": f"Unknown stop type '{kind}'."}
    try:
        float(place["lat"]), float(place["lng"])
    except (TypeError, ValueError, KeyError):
        return {"status": "error", "message": "The stop needs lat and lng."}
    if not trip_id or get_trip_data(trip_id) is None:
        return {"status": "error", "code": "not_saved",
                "message": "This trip isn't saved (log in), so stops can't be added to it."}

    engine = get_engine()
    with engine.begin() as conn:
        row = conn.execute(text(
            "SELECT id, waypoints, route_polyline FROM daily_schedules "
            "WHERE trip_id = :tid AND day_number = :day"), {"tid": trip_id, "day": int(day_number)}).fetchone()
        if not row:
            return {"status": "error", "message": f"Day {day_number} not found."}
        wps = row[1] if isinstance(row[1], list) else json.loads(row[1] or "[]")
        if len(wps) < 2 or all(w.get("type") == "stay" for w in wps):
            return {"status": "error", "message": f"Day {day_number} has no driving."}
        new_wp = stop_waypoint(place, kind, eta)
        if any((w.get("place_id") or w.get("osm_id")) == new_wp["place_id"] for w in wps if new_wp["place_id"]):
            return {"status": "error", "message": f"{new_wp['label']} is already on day {day_number}."}
        wps = insert_in_order(wps, new_wp, row[2])
        if not _recalculate_day_route(conn, str(row[0]), wps):
            return {"status": "error", "message": "The day's route could not be recalculated."}

    return {"status": "success",
            "message": f"{KIND_EMOJI[kind]} {new_wp['label']} added to day {day_number}"
                       + (f" (around {eta})." if eta else "."),
            "trip_data": get_trip_data(trip_id)}

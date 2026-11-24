"""
Changing part of a saved route with a line drawn on the map (touch screens, Nov 2026).

The line starts and ends on the route; the stretch between those two points follows the line
instead. Everything else stays: days, campsites, stops. The drawn points become hidden "via"
waypoints of the days the stretch runs through, and only those days are recalculated
(_recalculate_day_route already passes "via" points through in order).
"""

import json

from googlemaps.convert import decode_polyline

# How far (km) the line's start and end may be from the route to count as "on the route".
SNAP_KM = 20.0
# A day longer than this after the change gets a warning.
LONG_DAY_HOURS = 8.0


class ReshapeError(ValueError):
    """The line can't change this route; `code` says why, the message is for the user."""

    def __init__(self, code, message):
        super().__init__(message)
        self.code = code


def _km(a_lat, a_lng, b_lat, b_lng):
    from tools.plan_route import _haversine_distance
    return _haversine_distance(a_lat, a_lng, b_lat, b_lng)


def _is_stay(waypoints):
    return bool(waypoints) and all(w.get("type") == "stay" for w in waypoints)


def _route_points(days):
    """All points of the driving days' polylines: (lat, lng, km from the trip start, day index)."""
    pts, km, prev = [], 0.0, None
    for i, day in enumerate(days):
        if _is_stay(day["waypoints"]) or not day.get("route_polyline"):
            continue
        for p in decode_polyline(day["route_polyline"]):
            if prev is not None:
                km += _km(prev["lat"], prev["lng"], p["lat"], p["lng"])
            pts.append((p["lat"], p["lng"], km, i))
            prev = p
    return pts


def _project(pts, lat, lng):
    """Nearest route point: (distance km, km along the trip, day index)."""
    best = None
    for p_lat, p_lng, km, day in pts:
        d = _km(lat, lng, p_lat, p_lng)
        if best is None or d < best[0]:
            best = (d, km, day)
    return best


def plan_reshape(days, stroke):
    """
    Work out the new waypoints of the days the drawn stretch runs through.

    Args:
        days (list): the trip's days in order, each {"waypoints": [...], "route_polyline": str}.
        stroke (list): the drawn line in drawing order, [{"lat", "lng"}], ends included.

    Returns:
        dict: {"days": {day index: new waypoints}, "from_day": i, "to_day": j}
    Raises:
        ReshapeError
    """
    stroke = [{"lat": float(p["lat"]), "lng": float(p["lng"])} for p in stroke or []]
    if len(stroke) < 2:
        raise ReshapeError("too_short", "Draw a longer line.")
    pts = _route_points(days)
    if not pts:
        raise ReshapeError("no_route", "This trip has no driving route to change.")

    a = _project(pts, stroke[0]["lat"], stroke[0]["lng"])
    b = _project(pts, stroke[-1]["lat"], stroke[-1]["lng"])
    if a[0] > SNAP_KM or b[0] > SNAP_KM:
        raise ReshapeError("off_route", "To change part of the route, start and end the line on the route.")
    if a[1] > b[1]:  # drawn against the direction of travel
        stroke, a, b = stroke[::-1], b, a
    if b[1] - a[1] < 2:
        raise ReshapeError("too_short", "The line starts and ends at the same place on the route.")

    # Each drawn point gets a place along the trip in proportion to how far along the line it is.
    lengths = [0.0]
    for p, q in zip(stroke, stroke[1:]):
        lengths.append(lengths[-1] + _km(p["lat"], p["lng"], q["lat"], q["lng"]))
    total = lengths[-1] or 1.0
    targets = [a[1] + (b[1] - a[1]) * (l / total) for l in lengths]

    ranges = {}
    for _, _, km, day in pts:
        lo, hi = ranges.get(day, (km, km))
        ranges[day] = (min(lo, km), max(hi, km))

    def day_for(km):
        inside = [d for d, (lo, hi) in ranges.items() if lo <= km <= hi]
        if inside:
            return min(inside)
        return min(ranges, key=lambda d: min(abs(km - ranges[d][0]), abs(km - ranges[d][1])))

    new_via = {}
    for p, km in zip(stroke, targets):
        new_via.setdefault(day_for(km), []).append((km, {"type": "via", "label": "via",
                                                        "lat": p["lat"], "lng": p["lng"]}))
    affected = set(new_via) | {d for d, (lo, hi) in ranges.items() if hi >= a[1] and lo <= b[1]}

    changed = {}
    for d in sorted(affected):
        wps = days[d]["waypoints"]
        start, end, inner = wps[0], wps[-1], wps[1:-1]
        items = []
        for w in inner:
            pos = _project(pts, w["lat"], w["lng"])[1]
            if w.get("type") == "via" and a[1] <= pos <= b[1]:
                continue  # an older drawing of this stretch
            items.append((pos, w))  # stops the user picked stay on the day
        items += new_via.get(d, [])
        items.sort(key=lambda x: x[0])
        changed[d] = [start, *[w for _, w in items], end]
    return {"days": changed, "from_day": a[2], "to_day": b[2]}


def reshape_route(trip_id, stroke):
    """
    Change the stretch of a saved trip between the drawn line's ends to follow the line.

    Returns:
        dict: {"status": "success", "message", "warnings", "days_changed", "trip_data"}
              or {"status": "error", "code", "message"}.
    """
    from sqlalchemy import text
    from tools.db import get_engine
    from tools.trip_store import get_trip_data
    from navigation.dispatcher import _recalculate_day_route

    if not trip_id or get_trip_data(trip_id) is None:
        return {"status": "error", "code": "not_saved",
                "message": "This trip isn't saved, so part of it can't be changed. Plan it along the line instead."}
    engine = get_engine()
    with engine.begin() as conn:
        rows = conn.execute(text(
            "SELECT id, day_number, waypoints, route_polyline FROM daily_schedules "
            "WHERE trip_id = :tid ORDER BY day_number"), {"tid": trip_id}).fetchall()
        days = [{"id": str(r[0]), "day_number": r[1],
                 "waypoints": r[2] if isinstance(r[2], list) else json.loads(r[2] or "[]"),
                 "route_polyline": r[3]} for r in rows]
        try:
            plan = plan_reshape(days, stroke)
        except ReshapeError as e:
            return {"status": "error", "code": e.code, "message": str(e)}
        for i, wps in plan["days"].items():
            if not _recalculate_day_route(conn, days[i]["id"], [dict(w) for w in wps]):
                raise RuntimeError(f"Directions failed for day {days[i]['day_number']}")

    data = get_trip_data(trip_id) or {}
    numbers = [days[i]["day_number"] for i in sorted(plan["days"])]
    warnings = []
    for d in data.get("daily_schedules") or []:
        if d.get("day_number") in numbers and (d.get("driving_hours") or 0) > LONG_DAY_HOURS:
            warnings.append(f"Day {d['day_number']} is now about {d['driving_hours']:.1f} h of driving.")
    span = f"day {numbers[0]}" if len(numbers) == 1 else f"days {numbers[0]}–{numbers[-1]}"
    message = (f"The route now follows your line on {span}; the campsites and the other days "
               "are unchanged.")
    return {"status": "success", "message": message, "warnings": warnings,
            "days_changed": numbers, "trip_data": data}

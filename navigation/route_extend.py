"""
Extending a saved trip with a line drawn on the map (touch screens, Nov 2026).

The line starts where the trip ends and goes on to a new destination: new days are planned
along the line (its points as pass-through "via" points) and added after the last day.
The days already planned stay as they are; the last night gets a campsite if the trip
used to end there without one.
"""

import json
import uuid
from datetime import date, timedelta

from navigation.route_reshape import SNAP_KM, _km

MAX_VIA = 20


def _as_date(value):
    if isinstance(value, date):
        return value
    return date.fromisoformat(str(value)[:10])


def extend_route(trip_id, stroke, end_label=None, extra_days=None, dest_days=0):
    """
    Args:
        trip_id (str): a saved trip.
        stroke (list): the drawn line [{"lat", "lng"}], from the trip's end to the new destination.
        end_label (str): name of the new destination (reverse geocoded by the frontend).
        extra_days (int | None): days to add; None = estimated from the distance.
        dest_days (int): full days at the new destination (part of extra_days).

    Returns:
        dict: {"status": "success", "message", "warnings", "days_added", "trip_data"}
              or {"status": "error", "code", "message"}.
    """
    from sqlalchemy import text
    from tools.db import get_engine
    from tools.trip_store import get_trip_data
    from tools.search_campings import search_campings
    from tools.plan_route import plan_route, _pick_campsite, _json_default
    from navigation.dispatcher import apply_campsite_change
    from navigation.plan_form import estimate_days

    data = get_trip_data(trip_id) if trip_id else None
    if not data or not data.get("daily_schedules"):
        return {"status": "error", "code": "not_saved",
                "message": "This trip isn't saved, so it can't be extended. Plan it along the line instead."}
    stroke = [{"lat": float(p["lat"]), "lng": float(p["lng"])} for p in stroke or []]
    if len(stroke) < 2:
        return {"status": "error", "code": "too_short", "message": "Draw a longer line."}

    days = data["daily_schedules"]
    last = days[-1]
    end_wp = (last.get("waypoints") or [{}])[-1]
    if end_wp.get("lat") is None:
        return {"status": "error", "code": "no_route", "message": "This trip has no end point to extend from."}
    if _km(stroke[0]["lat"], stroke[0]["lng"], end_wp["lat"], end_wp["lng"]) > SNAP_KM:
        return {"status": "error", "code": "off_end",
                "message": "To extend the trip, start the line where the trip ends."}

    warnings = []
    night = {"label": end_wp.get("label") or "End", "lat": end_wp["lat"], "lng": end_wp["lng"]}
    if end_wp.get("type") == "end":
        # The trip used to end here without a night: it needs a campsite before going on.
        found = search_campings(lat=end_wp["lat"], lng=end_wp["lng"], radius_km=30,
                                vw_compatible=True, limit=6)
        camp, _ = _pick_campsite(found.get("results") or [])
        if camp:
            res = apply_campsite_change(trip_id, last["day_number"], camp)
            if res.get("status") == "success":
                night = {"label": camp["name"], "lat": camp["lat"], "lng": camp["lng"]}
        else:
            warnings.append(f"No campsite found near {night['label']} for the night before the new part.")

    destination = {"label": (end_label or "").strip()[:120] or "New destination",
                   "lat": stroke[-1]["lat"], "lng": stroke[-1]["lng"]}
    via = stroke[1:-1][:MAX_VIA]
    dest_days = max(0, int(dest_days or 0))
    if extra_days in (None, ""):
        extra_days = estimate_days(night, destination, [], False, dest_days, via_points=via)
    extra_days = max(1, min(int(extra_days), 60))
    start = _as_date(last.get("date")) + timedelta(days=1)

    leg = plan_route(
        origin=night, destination=destination, num_days=extra_days,
        start_date=start.isoformat(), via_points=via,
        stays=[{"label": None, "days": dest_days}] if dest_days else None,
    )
    if leg.get("status") != "success":
        return {"status": "error", "code": "plan_failed",
                "message": leg.get("message") or "The new part could not be planned."}
    warnings += leg.get("warnings") or []

    offset = int(last["day_number"])
    new_days = leg["daily_schedules"]
    trip = data.get("trip") or {}
    engine = get_engine()
    with engine.begin() as conn:
        for d in new_days:
            camp = d.get("overnight_camping") or {}
            camp_id = camp.get("id")
            try:
                camp_id = str(uuid.UUID(str(camp_id))) if camp_id else None
            except ValueError:
                camp_id = None
            conn.execute(text("""
                INSERT INTO daily_schedules
                    (id, trip_id, day_number, schedule_date, driving_hours, driving_km,
                     waypoints, overnight_camping_id, route_polyline)
                VALUES (:id, :trip_id, :day_number, :date, :hours, :km,
                        CAST(:wps AS jsonb), :camp_id, :poly)
            """), {
                "id": str(uuid.uuid4()), "trip_id": trip_id,
                "day_number": offset + int(d["day_number"]), "date": d["date"],
                "hours": d["driving_hours"], "km": d["driving_km"],
                "wps": json.dumps(d["waypoints"], default=_json_default),
                "camp_id": camp_id, "poly": d.get("route_polyline"),
            })
        origin_label = (trip.get("origin") or {}).get("label") or trip.get("origin_label") or "Start"
        conn.execute(text("""
            UPDATE trips SET destination_label = :label, destination_lat = :lat,
                destination_lng = :lng, end_date = :end, title = :title, updated_at = NOW()
            WHERE id = :id
        """), {"label": destination["label"], "lat": destination["lat"], "lng": destination["lng"],
               "end": new_days[-1]["date"], "title": f"{origin_label} to {destination['label']}",
               "id": trip_id})

    first, last_new = offset + 1, offset + len(new_days)
    span = f"day {first}" if first == last_new else f"days {first}–{last_new}"
    message = (f"The trip now goes on along your line to {destination['label']}: {span} added; "
               "the days before are unchanged.")
    return {"status": "success", "message": message, "warnings": warnings,
            "days_added": list(range(first, last_new + 1)), "trip_data": get_trip_data(trip_id)}

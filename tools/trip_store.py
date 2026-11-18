"""
Reading a stored trip in the shape the frontend uses (trip + daily schedules + photos).

Shared by the Flask endpoints and the chat tools, so both return the same data.
"""

import json

from sqlalchemy import text

from tools.db import get_engine
from tools.search_campings import search_campings


def _sanitize_for_json(obj):
    import decimal
    if isinstance(obj, decimal.Decimal):
        return float(obj)
    if isinstance(obj, dict):
        return {k: _sanitize_for_json(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_sanitize_for_json(item) for item in obj]
    return obj


def _get_trip_data(trip_id):
    """Fetch trip and schedules from DB to return to frontend."""
    import json
    engine = get_engine()
    with engine.connect() as conn:
        trip_row = conn.execute(
            text("SELECT id, user_id, title, origin_label, origin_lat, origin_lng, destination_label, destination_lat, destination_lng, start_date, end_date, status FROM trips WHERE id = :tid"),
            {"tid": trip_id}
        ).fetchone()

        if not trip_row:
            return None

        trip = {
            "id": str(trip_row[0]),
            "user_id": str(trip_row[1]) if trip_row[1] else None,
            "title": trip_row[2],
            "origin": {"label": trip_row[3], "lat": float(trip_row[4]) if trip_row[4] is not None else 0.0, "lng": float(trip_row[5]) if trip_row[5] is not None else 0.0},
            "destination": {"label": trip_row[6], "lat": float(trip_row[7]) if trip_row[7] is not None else 0.0, "lng": float(trip_row[8]) if trip_row[8] is not None else 0.0},
            "start_date": str(trip_row[9]) if trip_row[9] else "",
            "end_date": str(trip_row[10]) if trip_row[10] else "",
            "status": trip_row[11]
        }

        schedules_rows = conn.execute(
            text("SELECT id, day_number, schedule_date, driving_hours, driving_km, waypoints, route_polyline FROM daily_schedules WHERE trip_id = :tid ORDER BY day_number ASC"),
            {"tid": trip_id}
        ).fetchall()

        is_round_trip = (
            (trip.get("origin", {}).get("label") and trip.get("destination", {}).get("label") and trip["origin"]["label"] == trip["destination"]["label"]) or
            (trip.get("origin", {}).get("lat") == trip.get("destination", {}).get("lat") and trip.get("origin", {}).get("lng") == trip.get("destination", {}).get("lng"))
        )

        schedules = []
        num_schedules = len(schedules_rows)
        for r in schedules_rows:
            wps = r[5] if isinstance(r[5], list) else json.loads(r[5] or "[]")
            # Stay / rest days sleep at the campsite of their single "stay" waypoint.
            overnight = next((w for w in reversed(wps) if w.get("type") in ("camping", "stay")), None)
            day_num = r[1]
            is_return = is_round_trip and num_schedules > 1 and (day_num > (num_schedules / 2))
            
            overnight_opts = []
            if day_num < num_schedules:
                target_point = overnight or (wps[-1] if wps else None)
                if target_point and target_point.get("lat") and target_point.get("lng"):
                    c_res = search_campings(
                        lat=target_point["lat"],
                        lng=target_point["lng"],
                        radius_km=30,
                        limit=3
                    )
                    if c_res.get("results"):
                        overnight_opts = c_res["results"]

            schedules.append({
                "id": str(r[0]),
                "day_number": day_num,
                "date": str(r[2]) if r[2] else "",
                "driving_hours": float(r[3]) if r[3] is not None else 0.0,
                "driving_km": float(r[4]) if r[4] is not None else 0.0,
                "waypoints": wps,
                "overnight_camping": overnight,
                "overnight_options": overnight_opts,
                "route_polyline": r[6],
                "is_return": is_return
            })

        # Fetch photos associated with this trip
        photo_rows = conn.execute(
            text("""
                SELECT id, file_url, thumbnail_url, lat, lng,
                       caption, original_filename, tagged_day_schedule_id, created_at
                FROM photos
                WHERE trip_id = :trip_id
                ORDER BY created_at ASC
            """),
            {"trip_id": trip_id}
        ).fetchall()

        photos = []
        seen_keys = set()
        for pr in photo_rows:
            p_url = pr[1]
            p_fname = pr[6]
            dedup_key = p_url or p_fname or str(pr[0])
            if dedup_key in seen_keys:
                continue
            seen_keys.add(dedup_key)
            photos.append({
                "id": str(pr[0]),
                "file_url": pr[1],
                "thumbnail_url": pr[2],
                "lat": float(pr[3]) if pr[3] is not None else None,
                "lng": float(pr[4]) if pr[4] is not None else None,
                "caption": pr[5],
                "original_filename": pr[6],
                "tagged_day_schedule_id": str(pr[7]) if pr[7] else None,
                "created_at": str(pr[8]) if pr[8] else None,
            })

        result_payload = {
            "trip": trip,
            "daily_schedules": schedules,
            "photos": photos,
            "total_driving_hours": sum(float(s["driving_hours"] or 0) for s in schedules),
            "total_driving_km": sum(float(s["driving_km"] or 0) for s in schedules)
        }

        return _sanitize_for_json(result_payload)


get_trip_data = _get_trip_data

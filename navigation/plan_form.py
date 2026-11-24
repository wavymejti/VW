"""
The start form ("Plan a trip"): turns the form into plan_route arguments.

Modes:
- direct:      A -> B (the planner picks the nights)
- p2p:         A -> stop 1 -> stop 2 -> ... -> B, in the given order
- turnaround:  A -> stops there -> B -> stops back -> A

Each stop has `nights`: 0 = pass through, 1 = one night there, n = n nights (a stay).
Free text was not reliably understood for a first route (Nov 2026 tests), so the first
plan comes from structured fields and the chat takes over from there.
"""

import math
from datetime import date, timedelta

MODES = ("direct", "p2p", "turnaround")
MAX_STOPS = 10
MAX_NIGHTS = 30
KM_PER_DRIVING_DAY = 450  # with ~1.25 road factor on straight lines: about 5-6 h at the wheel
ROAD_FACTOR = 1.25


class FormError(ValueError):
    """A form the planner can't use; the message is shown to the user."""


def _place(raw, what):
    if isinstance(raw, str):
        raw = {"label": raw}
    if not isinstance(raw, dict):
        raise FormError(f"Please enter the {what}.")
    label = (raw.get("label") or raw.get("name") or "").strip()[:120]
    if not label:
        raise FormError(f"Please enter the {what}.")
    place = {"label": label}
    try:
        if raw.get("lat") is not None and raw.get("lng") is not None:
            lat, lng = float(raw["lat"]), float(raw["lng"])
            if -90 <= lat <= 90 and -180 <= lng <= 180 and (abs(lat) > 0.01 or abs(lng) > 0.01):
                place["lat"], place["lng"] = lat, lng
    except (TypeError, ValueError):
        pass
    return place


def _nights(value):
    try:
        return max(0, min(MAX_NIGHTS, int(value or 0)))
    except (TypeError, ValueError):
        return 0


def _stops(raw_list, leg):
    stops = []
    for raw in (raw_list or [])[:MAX_STOPS]:
        label = (raw.get("label") if isinstance(raw, dict) else raw) or ""
        if not str(label).strip():
            continue  # an empty "+ Add stop" row
        stop = _place(raw, "stop")
        stop["nights"] = _nights(raw.get("nights") if isinstance(raw, dict) else 0)
        stop["leg"] = leg
        stops.append(stop)
    return stops


def _km(a, b):
    r = math.pi / 180
    h = (math.sin((b["lat"] - a["lat"]) * r / 2) ** 2
         + math.cos(a["lat"] * r) * math.cos(b["lat"] * r) * math.sin((b["lng"] - a["lng"]) * r / 2) ** 2)
    return 2 * 6371 * math.asin(math.sqrt(h))


def estimate_days(origin, destination, stops, round_trip, dest_nights=0):
    """
    A sensible trip length when the form leaves it empty: driving days from the straight-line
    distance (x road factor), at least one per night on the way, plus the stay days.
    Needs coordinates; without them the planner geocodes and we guess from the stops alone.
    """
    out = [s for s in stops if s["leg"] != "back"]
    back = [s for s in stops if s["leg"] == "back"]
    path = [origin] + out + [destination] + (back + [origin] if round_trip else [])
    if all("lat" in p for p in path):
        km = sum(_km(a, b) for a, b in zip(path, path[1:])) * ROAD_FACTOR
        driving = max(1, math.ceil(km / KM_PER_DRIVING_DAY))
    else:
        driving = 2 if round_trip else 1
    nights_on_way = sum(1 for s in stops if s["nights"] >= 1) + (1 if round_trip and dest_nights == 1 else 0)
    driving = max(driving, nights_on_way + 1)
    stay_days = sum(s["nights"] - 1 for s in stops if s["nights"] >= 2)
    if round_trip and dest_nights >= 2:
        stay_days += dest_nights - 1
    return driving + stay_days


def _stop_text(s):
    if s["nights"] == 0:
        return s["label"]
    return f"{s['label']} ({s['nights']} night{'s' if s['nights'] > 1 else ''})"


def form_to_plan_args(form, today=None):
    """
    Returns:
        tuple: (plan_route arguments, a one-line English summary used as the user's message)
    Raises:
        FormError: when the form can't be planned (missing start/destination, bad mode).
    """
    form = form or {}
    mode = (form.get("mode") or "direct").strip().lower()
    if mode not in MODES:
        raise FormError("Choose Direct, Point-to-point or Turnaround.")
    origin = _place(form.get("origin"), "starting point")
    destination = _place(form.get("destination"), "destination")
    round_trip = mode == "turnaround"

    stops = [] if mode == "direct" else _stops(form.get("stops"), "out")
    if round_trip:
        stops += _stops(form.get("back_stops"), "back")
    dest_nights = _nights(form.get("dest_nights")) if round_trip else 0

    today = today or date.today()
    start = today + timedelta(days=1)
    raw_date = (form.get("start_date") or "").strip()
    if raw_date:
        try:
            start = date.fromisoformat(raw_date[:10])
        except ValueError:
            raise FormError("The start date should look like 2027-05-10.")
        if start < today:
            raise FormError("The start date is in the past.")

    try:
        num_days = int(form.get("num_days")) if form.get("num_days") not in (None, "") else None
    except (TypeError, ValueError):
        num_days = None
    if num_days is not None and not 1 <= num_days <= 60:
        raise FormError("A trip can be 1 to 60 days long.")
    auto_days = num_days is None
    if auto_days:
        num_days = estimate_days(origin, destination, stops, round_trip, dest_nights)

    route_stops = [s for s in stops if s["leg"] == "out"]
    if round_trip and dest_nights == 1:
        route_stops.append({**destination, "nights": 1, "leg": "turn"})
    route_stops += [s for s in stops if s["leg"] == "back"]

    args = {
        "origin": origin,
        "destination": destination,
        "num_days": num_days,
        "start_date": start.isoformat(),
        "round_trip": round_trip,
    }
    if route_stops:
        args["route_stops"] = route_stops
    if round_trip and dest_nights >= 2:
        args["stays"] = [{"label": None, "days": dest_nights - 1}]

    out = [s for s in stops if s["leg"] == "out"]
    back = [s for s in stops if s["leg"] == "back"]
    if mode == "direct":
        route = f"{origin['label']} → {destination['label']} (direct)"
    elif mode == "p2p":
        route = " → ".join([origin["label"], *map(_stop_text, out), destination["label"]]) + " (point-to-point)"
    else:
        dest_text = destination["label"] + (f" ({dest_nights} night{'s' if dest_nights > 1 else ''})"
                                            if dest_nights else "")
        route = " → ".join([origin["label"], *map(_stop_text, out), dest_text,
                            *map(_stop_text, back), origin["label"]]) + " (turnaround)"
    days_text = f"{num_days} days" + (" (estimated)" if auto_days else "")
    summary = f"Plan a trip: {route}, starting {start.isoformat()}, {days_text}."
    return args, summary

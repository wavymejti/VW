"""
Where and when to stop for fuel, charging or lunch along a trip (Nov 2026).

For each driving day the route (polyline) gets a clock: departure (default 09:00), driving
time in proportion to distance, and short breaks. Target points:
- fuel:        when ~75% of the tank range is used (the tank carries over between days);
- ev_charging: when the battery reaches ~20% (full every morning, fast charge to 80%);
- restaurant:  lunch, where the clock reaches ~12:45 (days that end before 12:30 get none).
Places near the targets come from Google Places API (New) with basic "Pro" fields only
(tools/google_stops.py), ranked by how far they are off the route. See architecture/routing_sop.md.
"""

from datetime import datetime, timedelta

from googlemaps.convert import decode_polyline

from tools import google_stops

VEHICLES = {
    "diesel": {"label": "California T6.1 (diesel)", "fuel_range_km": 800, "ev_range_km": None},
    "phev": {"label": "California eHybrid (PHEV)", "fuel_range_km": 750, "ev_range_km": None},
    "ev": {"label": "ID. Buzz (electric)", "fuel_range_km": None, "ev_range_km": 380},
}
DEFAULT_VEHICLE = "diesel"
DEFAULT_DEPARTURE = "09:00"
FUEL_RESERVE = 0.25          # refuel with a quarter of the tank left
EV_LOW, EV_CHARGE_TO = 0.20, 0.80
LUNCH_AT = (12, 45)
LUNCH_EARLIEST = (12, 30)
BREAK_EVERY_H, BREAK_MIN = 2.0, 15
SEARCH_RADIUS_M, WIDER_RADIUS_M = 5000, 15000
LUNCH_MIN_LEFT_H = 0.5        # lunch this close to the day's end -> eat at the destination
CANDIDATES_PER_TARGET = 3
FALLBACK_KMH = 75.0

KIND_LABELS = {"fuel": "Fuel stop", "ev_charging": "Charging stop", "restaurant": "Lunch"}
KIND_EMOJI = {"fuel": "⛽", "ev_charging": "🔌", "restaurant": "🍽️"}


def _km(a, b):
    from tools.plan_route import _haversine_distance
    return _haversine_distance(a["lat"], a["lng"], b["lat"], b["lng"])


def _day_line(day):
    """Route points of a day with km from the day's start (about one point per km)."""
    raw = decode_polyline(day["route_polyline"])
    line, total, prev = [], 0.0, None
    for p in raw:
        if prev is not None:
            total += _km(prev, p)
        if not line or total - line[-1]["km"] >= 1.0 or p is raw[-1]:
            line.append({"lat": p["lat"], "lng": p["lng"], "km": total})
        prev = p
    return line


def _point_at(line, km):
    for a, b in zip(line, line[1:]):
        if b["km"] >= km:
            f = (km - a["km"]) / ((b["km"] - a["km"]) or 1)
            return {"lat": a["lat"] + (b["lat"] - a["lat"]) * f, "lng": a["lng"] + (b["lng"] - a["lng"]) * f}
    return {"lat": line[-1]["lat"], "lng": line[-1]["lng"]}


def _departure(value):
    try:
        h, m = (int(x) for x in str(value or DEFAULT_DEPARTURE).split(":")[:2])
        return h, m
    except ValueError:
        return 9, 0


class DayClock:
    """Clock along one day: driving at the day's average speed plus a break every 2 h."""

    def __init__(self, day, line, departure):
        self.line = line
        self.length = line[-1]["km"] if line else 0.0
        hours = float(day.get("driving_hours") or 0) or self.length / FALLBACK_KMH
        self.kmh = (self.length / hours) if hours else FALLBACK_KMH
        h, m = _departure(departure)
        self.start = datetime(2000, 1, 1, h, m)

    def driving_h(self, km):
        return km / self.kmh if self.kmh else 0.0

    def clock(self, km):
        d = self.driving_h(km)
        breaks = int(d // BREAK_EVERY_H) * BREAK_MIN
        return self.start + timedelta(hours=d, minutes=breaks)

    def km_at_clock(self, hh, mm):
        """Km into the day when the clock shows hh:mm (None if the day is over by then)."""
        target = datetime(2000, 1, 1, hh, mm)
        if target <= self.start:
            return 0.0
        lo, hi = 0.0, self.length
        if self.clock(hi) < target:
            return None
        for _ in range(40):
            mid = (lo + hi) / 2
            if self.clock(mid) < target:
                lo = mid
            else:
                hi = mid
        return hi


def _fmt_duration(h):
    mins = int(round(h * 60))
    return f"{mins // 60} h {mins % 60:02d} min" if mins >= 60 else f"{mins} min"


def _driving_days(schedules, day_number=None):
    out = []
    for day in sorted(schedules, key=lambda d: int(d["day_number"])):
        wps = day.get("waypoints") or []
        if not day.get("route_polyline") or (wps and all(w.get("type") == "stay" for w in wps)):
            continue
        line = _day_line(day)
        if len(line) < 2:
            continue
        out.append((day, line))
    if day_number is not None:
        out = [(d, l) for d, l in out if int(d["day_number"]) == int(day_number)]
    return out


def find_targets(schedules, kind, vehicle=DEFAULT_VEHICLE, departure=DEFAULT_DEPARTURE, day_number=None):
    """Where (and when) to stop: [{"day_number", "km", "point", "eta", "after_driving"}]."""
    spec = VEHICLES.get(vehicle) or VEHICLES[DEFAULT_VEHICLE]
    days = _driving_days(schedules)  # all days: the tank carries over
    targets = []

    def add(day, line, clock, km, reason):
        targets.append({
            "day_number": int(day["day_number"]),
            "date": str(day.get("date") or ""),
            "km": round(km, 1),
            "point": _point_at(line, km),
            "eta": clock.clock(km).strftime("%H:%M"),
            "after_driving": _fmt_duration(clock.driving_h(km)),
            "reason": reason,
        })

    if kind == "fuel":
        rng = spec["fuel_range_km"] or VEHICLES["diesel"]["fuel_range_km"]
        usable = rng * (1 - FUEL_RESERVE)
        used = 0.0
        for day, line in days:
            clock = DayClock(day, line, departure)
            pos = 0.0
            while used + (clock.length - pos) > usable:
                km = pos + (usable - used)
                add(day, line, clock, km, f"about {int(FUEL_RESERVE * 100)}% of the tank left")
                pos, used = km, 0.0
            used += clock.length - pos
    elif kind == "ev_charging":
        rng = spec["ev_range_km"] or VEHICLES["ev"]["ev_range_km"]
        for day, line in days:
            clock = DayClock(day, line, departure)
            first = rng * (1 - EV_LOW)               # full in the morning (charged at the campsite)
            step = rng * (EV_CHARGE_TO - EV_LOW)     # fast charge to 80% on the way
            km = first
            while km < clock.length - 10:
                add(day, line, clock, km, f"battery at about {int(EV_LOW * 100)}%")
                km += step
    elif kind == "restaurant":
        for day, line in days:
            clock = DayClock(day, line, departure)
            if clock.clock(clock.length) < datetime(2000, 1, 1, *LUNCH_EARLIEST):
                continue  # arrives before lunch: eat at the campsite
            km = clock.km_at_clock(*LUNCH_AT)
            if km is not None and clock.driving_h(clock.length - km) >= LUNCH_MIN_LEFT_H:
                add(day, line, clock, km, "lunchtime")
    else:
        raise ValueError(f"Unknown kind: {kind}")

    if day_number is not None:
        targets = [t for t in targets if t["day_number"] == int(day_number)]
    return targets


def _off_route_km(place, line):
    return min(_km(place, p) for p in line)


def _search(kind, targets):
    """Places near the targets: 5 km first, then 15 km around the targets left empty."""
    found = google_stops.find_places(kind, [t["point"] for t in targets], SEARCH_RADIUS_M)
    missing = [t for t in targets if not any(_km(t["point"], p) <= SEARCH_RADIUS_M / 1000 + 0.5 for p in found)]
    if missing:
        found += google_stops.find_places(kind, [t["point"] for t in missing], WIDER_RADIUS_M)
    return found


def plan_route_stops(schedules, kind, vehicle=DEFAULT_VEHICLE, departure=DEFAULT_DEPARTURE,
                     day_number=None):
    """
    Targets with up to CANDIDATES_PER_TARGET places each (nearest to the route first).

    Returns:
        dict: {"status": "success", "kind", "vehicle", "departure", "targets": [...]}
              or {"status": "error", "message"}.
    """
    if kind not in KIND_LABELS:
        return {"status": "error", "message": f"Unknown stop type '{kind}' (fuel, ev_charging, restaurant)."}
    targets = find_targets(schedules, kind, vehicle, departure, day_number)
    base = {"status": "success", "kind": kind, "vehicle": vehicle if vehicle in VEHICLES else DEFAULT_VEHICLE,
            "vehicle_label": (VEHICLES.get(vehicle) or VEHICLES[DEFAULT_VEHICLE])["label"],
            "departure": "%02d:%02d" % _departure(departure), "targets": targets}
    if not targets:
        base["message"] = {"fuel": "No fuel stop needed on these days.",
                           "ev_charging": "No charging stop needed on these days.",
                           "restaurant": "These days end before lunchtime."}[kind]
        return base

    lines = {int(d["day_number"]): l for d, l in _driving_days(schedules)}
    if not google_stops.available():
        return {"status": "error", "message": "Place search needs Google Places (GOOGLE_MAPS_API_KEY and "
                                              "GOOGLE_MAPS_MODE basic or full)."}
    try:
        found = _search(kind, targets)
    except google_stops.GooglePlacesError as e:
        print(f"[route_stops] {e}")
        return {"status": "error", "message": "Place search is not available right now. Try again in a moment."}

    for t in targets:
        line = lines[t["day_number"]]
        near = [p for p in found if _km(t["point"], p) <= WIDER_RADIUS_M / 1000]
        ranked = []
        for p in near:
            off = _off_route_km(p, line)
            key = (round(off, 1), 0 if p["name"] not in ("Fuel station", "EV charger", "Restaurant") else 1)
            ranked.append((key, {**p, "off_route_km": round(off, 1)}))
        ranked.sort(key=lambda x: x[0])
        seen, cands = set(), []
        for _, p in ranked:
            if p["place_id"] in seen:
                continue
            seen.add(p["place_id"])
            cands.append(p)
            if len(cands) == CANDIDATES_PER_TARGET:
                break
        t["candidates"] = cands
    return base


def schedules_from_rows(rows):
    """Chat session rows (day_number, waypoints, polyline) of an unsaved trip -> schedules."""
    return [{"day_number": d, "waypoints": w or [], "route_polyline": p} for d, w, p in rows or []]

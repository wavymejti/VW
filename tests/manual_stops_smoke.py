"""
Manual smoke test: route stops against the REAL Google Places API (basic fields only).
Not run by pytest. Each run costs about 10 Nearby Search Pro calls (free up to 5,000 a month).

    .venv/bin/python tests/manual_stops_smoke.py

Synthetic 2-day trip Poznań -> Hannover -> Köln along the A2/A1 corridor.
Prints fuel / EV / lunch stops with candidates.
"""
import os, sys, time, json
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from googlemaps.convert import encode_polyline
from tools import google_stops, route_stops as rs


def seg(pts, n=60):
    out = []
    for a, b in zip(pts, pts[1:]):
        out += [{"lat": a[0] + (b[0] - a[0]) * i / n, "lng": a[1] + (b[1] - a[1]) * i / n} for i in range(n)]
    out.append({"lat": pts[-1][0], "lng": pts[-1][1]})
    return encode_polyline(out)


DAY1 = [(52.400, 16.900), (52.330, 16.120), (52.350, 15.300), (52.340, 14.550), (52.390, 14.060), (52.330, 13.600),
        (52.400, 13.100), (52.300, 12.500), (52.250, 11.700), (52.200, 11.100), (52.290, 10.500), (52.380, 9.800)]
DAY2 = [(52.380, 9.800), (52.250, 9.100), (52.100, 8.600), (51.900, 8.000), (51.600, 7.500), (51.350, 7.300),
        (51.100, 7.050), (50.940, 6.960)]
TRIP = [
    {"day_number": 1, "date": "2027-05-10", "driving_hours": 5.5, "route_polyline": seg(DAY1),
     "waypoints": [{"type": "start"}, {"type": "camping"}]},
    {"day_number": 2, "date": "2027-05-11", "driving_hours": 3.5, "route_polyline": seg(DAY2),
     "waypoints": [{"type": "start"}, {"type": "camping"}]},
]

for kind, veh in [("fuel", "diesel"), ("ev_charging", "ev"), ("restaurant", "diesel")]:
    google_stops._cache.clear()
    t0 = time.time()
    res = rs.plan_route_stops(TRIP, kind, veh, "09:00")
    print(f"\n== {kind} ({veh})  {res.get('status')}  {time.time() - t0:.1f}s  {res.get('message', '')}")
    for t in res.get("targets", []):
        print(f"  day {t['day_number']}  km {t['km']}  {t['eta']}  ({t['after_driving']})  {t['reason']}"
              f"  @ {t['point']['lat']:.4f},{t['point']['lng']:.4f}")
        for c in t.get("candidates", []):
            extra = {k: c[k] for k in ("address", "primary_type", "fast_food")
                                       if c.get(k) not in (None, [], False)}
            print(f"     - {c['name']}  [{c['off_route_km']} km off route]  {json.dumps(extra, ensure_ascii=False)}")
        if not t.get("candidates"):
            print("     (no candidates)")

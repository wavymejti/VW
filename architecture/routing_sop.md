# Route Planning SOP

> Standard Operating Procedure for multi-day route planning.
> **Golden Rule**: Update this SOP before updating code in `tools/plan_route.py`.

---

## Purpose

Generate a multi-day driving itinerary with waypoints, campgrounds, and
daily schedules respectful of user driving limits.

## Trigger

- User says: "Plan a 5-day trip from Munich to Croatia"
- OpenAI model extracts intent → `plan_route` function call

## Input Schema

```json
{
  "origin": {"label": "string", "lat": "number", "lng": "number"},
  "destination": {"label": "string", "lat": "number", "lng": "number"},
  "num_days": "integer",
  "max_daily_drive_hours": "number (from user preferences, default: 6)",
  "preferred_amenities": ["string"],
  "budget_per_night_eur": "number | null"
}
```

## Processing Steps

1. **Validate inputs** — origin/destination exist, num_days > 0.
2. **Calculate total route** — call Google Maps Routes API (`ComputeRoutes`)
   for origin → destination to get total distance and duration.
3. **Divide into daily segments** — split total driving by `max_daily_drive_hours`.
   Ensure each day's driving does not exceed the limit.
   A day end within `SNAP_MAX_KM` (60 km, at most a quarter of an average day) of a
   waypoint moves onto that waypoint, so the night is spent where the user visits
   (`night_near` on the day). Overnight stops, stays and the turnaround never move;
   each waypoint takes at most one night.
4. **Find overnight campings** — for each day's endpoint, call `search_campings`
   to find a suitable campground near the stopping point.
5. **Compute daily routes** — for each day, call Routes API with that day's
   waypoints (start → attractions → camping).
6. **Build DailySchedule objects** — assemble waypoints, driving stats, polylines.
7. **Persist to database** — create Trip and DailySchedule records.
8. **Return** — full trip plan with all days.

## Drawn routes (`via_points`)

A line drawn with a finger on the map (touch screens) arrives as `via_points`: pass-through
points sent to Directions as `via:lat,lng` (no stop, no extra leg), in drawing order, with
no waypoint optimisation. Each day gets the via points between its start and end; they are
stored on the day as waypoints of type `via` (never shown) so a recalculation of the day
(`_recalculate_day_route`) still follows the drawing.

## Re-planning keeps the trip's shape (`modify_route`)

`plan_route` returns how the route was shaped in `trip.plan_params`
(`{"route_stops": [...], "via_points": [...]}`, stops resolved to coordinates). Saved trips
keep it in `trips.plan_params` (JSONB, migration 009, also added on first use); the chat
session keeps it in `last_plan` for unsaved trips. `modify_route` / `add_waypoint` pass it to
`plan_route` again, so a change asked in the chat (daily limit, more days, an extra place)
keeps the form's stop order and the drawn line. To avoid doubling: drive-through stops are
dropped from the waypoints read back from the days, multi-night stops from the read-back
stays; an excluded place is removed from `route_stops`; the drawn line is dropped when the
start or the end changes.

## Changing part of a saved route (`POST /api/reshape_route`)

A drawn line whose two ends lie within 20 km of the saved route changes only that stretch
(`navigation/route_reshape.py`): the drawn points get a place along the trip in proportion
to how far along the line they are, become `via` waypoints of the days that stretch runs
through (older `via` points of the stretch are dropped, stops are kept), and only those
days are recalculated. Campsites and the other days stay; a day over 8 h gets a warning.
Saved (logged-in) trips only; the chat gets a system note about the change.

## Extending a saved trip (`POST /api/extend_route`)

A drawn line that starts within 20 km of the trip's end and ends away from the route adds
days (`navigation/route_extend.py`): if the last day ended without a night, a campsite near
the end is put on it first; then `plan_route` plans the new part from there (start = the day
after the last day, the line's points as `via_points`, optional days at the new destination)
and its days are appended. The trip's destination, end date and title follow the new end.

## Fuel, EV charging and lunch stops (`/api/route_stops`, `find_route_stops`)

`tools/route_stops.py` gives every driving day a clock (departure, default 09:00; driving at
the day's average speed; a 15 min break every 2 h) and picks target points: fuel when ~75%
of the tank range is used (the tank carries over days; T6.1 diesel 800 km, eHybrid 750 km),
charging when the battery reaches 20% (full each morning, fast charge to 80%; ID. Buzz
380 km), lunch where the clock reaches 12:45. Places come from Google Places API (New),
Nearby Search with basic "Pro" fields only (`tools/google_stops.py`, one call per stop point,
cached 24 h; no hours, ratings, EV/fuel options, which are billed as Enterprise/Atmosphere). A chosen
stop can be asked for by name, brand or cuisine (`query`, e.g. "McDonald's", "Shell"): then
Text Search (New) with the same Pro fields runs instead of Nearby Search (5, 15, then 30 km
around the stop point); a name found in some results keeps only those, a cuisine keeps all. A
place can show a street-level photo from Mapillary (`tools/mapillary_client.py`,
`POST /api/place_photo`; free, CC BY-SA credit shown; only with `MAPILLARY_TOKEN`): a panorama or
an image facing the place, nearer and newer first, within 60 m, then 150 m. Attractions
without a photo get one the same way (`kind: "attraction"`, `tools/place_photos.py`): first a
Wikimedia Commons photo with coordinates within 300 m (a file naming the place wins; unnamed
ones only within 120 m; maps, logos, SVGs skipped), then Mapillary. The frontend marks
placeholder images with `data-photo-lat/lng/name` and fills them once they are on screen. A chosen
place is added as a `waypoint` with `service`, emoji and `planned_time` at its position on
the day (`navigation/route_stop_add.py`); only that day is recalculated. Attractions are
re-fetched only when the trip's shape changes (day ends, 10 km steps of day length), not
when such a stop is added.

## Output Schema

```json
{
  "trip": "Trip object",
  "daily_schedules": ["DailySchedule objects"],
  "total_driving_hours": "number",
  "total_driving_km": "number"
}
```

## Constraints

- Daily driving MUST NOT exceed `max_daily_drive_hours`.
- Each overnight stop MUST have a campground (auto-selected or user-chosen).
- A day with places to visit lists `campsite_km_from_stops`; replies call a campsite
  "near X" only when it is within ~15 km of X.
- Route waypoints must be geographically logical (no backtracking).

## Error Handling

| Error | Action |
|---|---|
| Route impossible | Suggest increasing days or relaxing constraints |
| No camping at midpoint | Widen search radius up to 100km |
| Routes API failure | Return error, suggest manual planning |
| Trip exceeds budget | Warn user, suggest cheaper alternatives |

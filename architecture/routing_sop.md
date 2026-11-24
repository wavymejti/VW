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

## Changing part of a saved route (`POST /api/reshape_route`)

A drawn line whose two ends lie within 20 km of the saved route changes only that stretch
(`navigation/route_reshape.py`): the drawn points get a place along the trip in proportion
to how far along the line they are, become `via` waypoints of the days that stretch runs
through (older `via` points of the stretch are dropped, stops are kept), and only those
days are recalculated. Campsites and the other days stay; a day over 8 h gets a warning.
Saved (logged-in) trips only; the chat gets a system note about the change.

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

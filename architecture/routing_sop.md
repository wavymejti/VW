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
4. **Find overnight campings** — for each day's endpoint, call `search_campings`
   to find a suitable campground near the stopping point.
5. **Compute daily routes** — for each day, call Routes API with that day's
   waypoints (start → attractions → camping).
6. **Build DailySchedule objects** — assemble waypoints, driving stats, polylines.
7. **Persist to database** — create Trip and DailySchedule records.
8. **Return** — full trip plan with all days.

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
- Route waypoints must be geographically logical (no backtracking).

## Error Handling

| Error | Action |
|---|---|
| Route impossible | Suggest increasing days or relaxing constraints |
| No camping at midpoint | Widen search radius up to 100km |
| Routes API failure | Return error, suggest manual planning |
| Trip exceeds budget | Warn user, suggest cheaper alternatives |

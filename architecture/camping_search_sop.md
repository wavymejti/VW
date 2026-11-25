# Camping Search SOP

> Standard Operating Procedure for searching campgrounds.
> **Golden Rule**: Update this SOP before updating code in `tools/search_campings.py`.

---

## Purpose

Find campgrounds matching user filters near a location or along a route.

## Trigger

- User says: "Find a camping with power and showers near Bled"
- Gemini extracts intent → `search_campings` function call

## Input Schema

```json
{
  "lat": "number (center latitude)",
  "lng": "number (center longitude)",
  "radius_km": "number (default: 50)",
  "amenities": ["power", "water", "wifi", "showers"],
  "max_cost_eur": "number | null",
  "vw_compatible": "boolean (default: true)",
  "limit": "integer (default: 10)"
}
```

## Processing Steps

1. **Validate inputs** — ensure lat/lng are valid, radius is positive.
2. **Query database** — use PostGIS `ST_DWithin()` on `campings` table.
3. **Apply filters** — amenities, cost, VW compatibility.
4. **Fallback to external sources** — if DB returns < 3 results, query in parallel:
   - Google Places API `searchNearby` with type `campground`;
   - park4night via its unofficial app endpoint
     `guest.park4night.com/services/V4.1/lieuxGetFilter.php?latitude=&longitude=`
     (`tools/park4night_client.py`, only when `PARK4NIGHT_ENABLED=1`).
     The endpoint returns ~200 places nearest to the point; radius and limit
     are applied locally, day-only parking / service areas are skipped.
     Required amenities are filtered locally; price and VW filters are not
     applied (no structured data). Timeout `PARK4NIGHT_TIMEOUT` (default 10 s);
     on error → []. In-process cache per ~1 km grid cell for 6 h.
     Phone / e-mail fields are never read or stored.
5. **Cache new results** — insert external results into `campings` table
   (`source` = `google_maps` | `park4night`, park4night `place_id` = `p4n:<id>`).
6. **Sort** — DB results by distance, then rating; external results appended
   nearest-first (distance computed with haversine).
7. **Return** — list of Camping objects matching the schema.

## Output Schema

```json
{
  "results": [Camping],
  "total_found": "integer",
  "source": "string (database | google_maps | mixed)"
}
```

## Error Handling

| Error | Action |
|---|---|
| Invalid coordinates | Return error message, ask user to clarify location |
| No results in DB | Fall back to Google Maps API |
| Google Maps API failure | Return DB results only, warn user |
| park4night failure or timeout | Ignore park4night, return other results |
| Zero results anywhere | Suggest widening radius or relaxing filters |

## park4night — legal note

POC only. park4night has no public API (the app endpoint is undocumented and
may change at any time) and its terms grant no licence to its content or database. Before production, VW must agree data access with
park4night (AppMobilEdition). park4night spots carry `source: park4night`,
`spot_type` and `external_url` (badge with a link in the camping modal).

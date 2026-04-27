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
4. **Fallback to Google Maps** — if DB returns < 3 results, call Places API
   `searchNearby` with type `campground` to discover new sites.
5. **Cache new results** — insert Google Maps results into `campings` table.
6. **Sort** — by distance (nearest first), then by rating.
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
| Zero results anywhere | Suggest widening radius or relaxing filters |

# Trip Summary Export SOP

> Standard Operating Procedure for generating shareable trip summaries.
> **Golden Rule**: Update this SOP before updating code in `tools/generate_summary.py`.

---

## Purpose

Generate a visual summary of a completed trip (video, slideshow, or PDF)
combining the map route, photos, and optional background music.

## Trigger

- User completes a trip and requests a summary export.
- Or user explicitly asks: "Generate a summary of my trip."

## Input Schema

```json
{
  "trip_id": "uuid",
  "format": "string (video | image_slideshow | pdf)",
  "include_map_animation": "boolean (default: true)",
  "include_photos": "boolean (default: true)",
  "music_track": "string | null"
}
```

## Processing Steps

1. **Fetch trip data** — load Trip, DailySchedules, and Photos from DB.
2. **Collect assets**:
   - Route polylines for map animation
   - Photo files linked to the trip
   - Waypoint labels and stats (driving hours, km)
3. **Generate based on format**:
   - **Video**: Animate route on map → overlay photos at locations → add music.
   - **Image slideshow**: Create a sequence of map + photo slides.
   - **PDF**: Layout trip stats, map screenshot, photo grid.
4. **Save output** — write to `.tmp/` for processing, then move to final storage.
5. **Create TripSummary record** — persist metadata in database.
6. **Return file URL** — provide download/share link.

## Output Schema

```json
{
  "summary": "TripSummary object",
  "file_url": "string",
  "file_size_mb": "number"
}
```

## Error Handling

| Error | Action |
|---|---|
| No photos for trip | Generate map-only summary, warn user |
| Trip has no schedules | Cannot generate, ask user to plan trip first |
| File generation fails | Retry once, then inform user |
| Music file missing | Generate without music, notify user |

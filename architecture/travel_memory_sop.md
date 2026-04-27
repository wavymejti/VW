# Travel Memory SOP

> Standard Operating Procedure for the Travel Memory (photo) feature.
> **Golden Rule**: Update this SOP before updating code in `tools/extract_exif.py`.

---

## Purpose

Process user-uploaded photos, extract GPS/EXIF metadata, and link them
to trip locations on the map.

## Trigger

- User uploads photos via the Travel Memory interface.
- System processes each photo automatically.

## Processing Steps

1. **Receive file upload** — validate file type (JPEG, PNG, HEIC, TIFF).
2. **Extract EXIF metadata** — use `Pillow` or `exifread`:
   - GPS coordinates (DMS → Decimal Degrees conversion)
   - Capture timestamp
   - Camera make/model
   - Orientation
   - Original filename
3. **Validate GPS data** — ensure coordinates are within valid ranges
   (lat: -90 to 90, lng: -180 to 180).
4. **Generate thumbnail** — resize to max 400px width for gallery display.
5. **Store file** — save original and thumbnail to filesystem/cloud.
6. **Store metadata** — insert Photo record into database with PostGIS location.
7. **Auto-link to trip** — if photo GPS/timestamp falls within a trip's
   date range and near its route, link via `trip_id` and `tagged_day_schedule_id`.
8. **Reverse geocode** — optionally call Google Maps Geocoding API to get
   a human-readable location label for the caption.

## Auto-Linking Logic

```
For each photo:
  1. Find trips where photo.captured_at BETWEEN trip.start_date AND trip.end_date
  2. For matching trips, check daily_schedules
  3. Use ST_DWithin(photo.location, route_segment, 5000)  -- 5km threshold
  4. If match found → set trip_id and tagged_day_schedule_id
```

## Output Schema

```json
{
  "photo": "Photo object (with id, location, caption)",
  "linked_trip": "Trip object | null",
  "linked_day": "DailySchedule object | null"
}
```

## Error Handling

| Error | Action |
|---|---|
| No EXIF data | Ask user to manually pin photo on map |
| Invalid GPS | Ask user to confirm location |
| File too large | Compress or reject (max 20MB) |
| Unsupported format | Inform user of supported formats |

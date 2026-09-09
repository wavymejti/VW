# Trip Summary Export SOP (Cinematic California Recap)

> Standard Operating Procedure for generating shareable trip summaries.
> **Golden Rule**: Update this SOP before updating code in `tools/generate_summary.py`.
> Last updated: 2026-09-08 (Cinematic California Recap Upgrade)

---

## 1. Purpose

Generate an engaging, cinematic visual summary of a completed or planned trip:
- **Video (MP4)**: Fast-paced, dynamic travel movie (20–40s) combining real terrain map animation (25 FPS), an animated VW California van sprite with real-time HUD odometer, full-screen travel memory photos, and looped soundtrack.
- **Image Slideshow**: High-resolution curated highlight slides (Intro, Key Route Frames, Photo Memories, Campings, Outro).
- **PDF Report**: Executive multi-page trip dossier with statistics, daily itinerary, and photo gallery.

---

## 2. Trigger

- User clicks "Generuj wideo / Podsumowanie" on a planned or completed trip.
- Or user explicitly asks the AI in chat: "Stwórz film z mojej podróży."

---

## 3. Input Schema

```json
{
  "trip_id": "uuid",
  "format": "string (video | image_slideshow | pdf)",
  "include_map_animation": "boolean (default: true)",
  "include_photos": "boolean (default: true)",
  "music_track": "string | null (e.g. 'acoustic_sunset', 'vanlife_chill', 'none')",
  "lang": "string (pl | de | en, default: 'pl')"
}
```

---

## 4. Processing Steps (Video Pipeline)

1. **Fetch trip data**: Load Trip, DailySchedules (with polylines & campings), and Photos from PostgreSQL.
2. **Terrain & Cartography Layer**:
   - For each day, calculate bounding box and optimal `zoom` level.
   - Fetch real terrain map from **Google Static Maps API** (`size=640x360&scale=2&maptype=terrain`).
   - Cache map images locally in `.tmp/summaries/maps/`.
   - Fallback gracefully to stylized dark cartographic canvas if offline or API unavailable.
3. **Web Mercator Coordinate Projection**:
   - Map route $(lat, lng)$ coordinates directly to pixel $(x, y)$ using closed-form Web Mercator equations to ensure pixel-perfect route alignment with terrain features.
4. **Cinematic Route Animation (25 FPS)**:
   - Interpolate progressive line coordinates for each day (~50–75 frames per day).
   - Draw glowing cyan route line (`#00E1D9`) with soft glow outline.
   - Draw VW California campervan sprite with pop-up roof, rotated to match the direction of travel (azimuth angle).
   - Render HUD elements: live digital odometer (`145 km / 320 km`), day badge (`DZIEŃ 1`), and route progress bar.
5. **Cinematic Highlights & Photo Memories**:
   - Render Intro slide with trip title, dates, VW branding, and exact photo memory count badge.
   - Deduplicate uploaded photo files by `file_url` to avoid repeating identical images from multi-upload actions.
   - Include **all photos whose pins appear on the map** (GPS coordinates) along each day's route.
   - Render cyan photo pin markers on the map animation at exact coordinate locations.
   - Calculate dynamic slide duration (`_get_photo_slide_duration` between 0.8s and 2.8s) based on total photo count so high-volume albums remain brisk and engaging.
   - Render full-screen photo memory slides with ambient blurred backdrop, white frame, glassmorphic caption card, and Sniffer branding.
   - For overnight stops: display campsite highlight card.
   - Render Outro slide with cumulative stats (total km, driving hours, memories collected).
6. **FFmpeg Assembly & Audio Mixing**:
   - Write concat list with differential durations:
     - Map animation frames: `duration 0.04` (25 FPS smooth motion)
     - Photo slides: dynamic duration `0.8` to `2.8` seconds
     - Intro/outro slides: `duration 2.5` to `3.0` seconds
   - Apply pixel format `-vf format=yuv420p` for maximum browser compatibility.
   - Mix background music with `-stream_loop -1 -filter:a volume=0.25 -shortest`.
7. **Persist & Return**:
   - Insert record in `trip_summaries` table.
   - Return relative URL accessible via `/summaries/<filename>`.

---

## 5. Output Schema

```json
{
  "status": "success",
  "summary": {
    "id": "uuid",
    "trip_id": "uuid",
    "format": "video",
    "file_url": "/summaries/summary_a0000001.mp4"
  },
  "file_url": "/summaries/summary_a0000001.mp4",
  "all_slides": ["/summaries/summary_slide_1.png", "..."],
  "slide_count": 8
}
```

---

## 6. Error Handling & Fallbacks

| Error | Action |
|---|---|
| Google Static Maps API error / offline | Fallback to built-in vector cartographic dark navy map. |
| No photos for trip | Generate route animation and campsite summary cards, inform user. |
| FFmpeg binary missing | Log error, return friendly message and offer image slideshow as fallback. |
| Music file missing or 'none' | Render video cleanly without audio track. |
| Corrupted photo / HEIC decode error | Skip broken photo, continue rendering remaining assets. |

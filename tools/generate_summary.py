"""
Trip summary export tool for the VW California AI Trip Planner.

Generates shareable trip summaries in different formats:
- PDF report with map screenshot, photos, and stats
- Image slideshow of trip highlights
- Video animation (placeholder — requires ffmpeg)

See: architecture/summary_export_sop.md
"""

import os
import uuid
import json
from datetime import datetime

from sqlalchemy import text
from PIL import Image, ImageDraw, ImageFont

from tools.db import get_engine


# Output directory for generated summaries
OUTPUT_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    ".tmp",
    "summaries",
)


def get_trip_summary(trip_id):
    """
    Retrieve the full trip data needed for summary generation.

    Args:
        trip_id (str): UUID of the trip.

    Returns:
        dict: Aggregated trip data including schedules,
              campings, and photos.
    """
    try:
        engine = get_engine()
        with engine.connect() as conn:
            # Fetch trip
            trip_row = conn.execute(
                text("SELECT * FROM trips WHERE id = :id"),
                {"id": trip_id},
            ).fetchone()

            if not trip_row:
                return {
                    "status": "error",
                    "message": f"Trip not found: {trip_id}",
                }

            trip_keys = [
                "id", "user_id", "title", "description",
                "origin_label", "origin_lat", "origin_lng",
                "destination_label", "destination_lat",
                "destination_lng", "start_date", "end_date",
                "status", "created_at", "updated_at",
            ]
            trip = dict(zip(trip_keys, trip_row))
            trip["id"] = str(trip["id"])
            trip["user_id"] = str(trip["user_id"])

            # Fetch daily schedules
            sched_rows = conn.execute(
                text(
                    "SELECT id, day_number, schedule_date, "
                    "driving_hours, driving_km, waypoints, "
                    "overnight_camping_id "
                    "FROM daily_schedules "
                    "WHERE trip_id = :tid "
                    "ORDER BY day_number"
                ),
                {"tid": trip_id},
            ).fetchall()

            schedules = []
            total_hours = 0
            total_km = 0
            for row in sched_rows:
                sched = {
                    "id": str(row[0]),
                    "day_number": row[1],
                    "date": str(row[2]) if row[2] else None,
                    "driving_hours": float(row[3] or 0),
                    "driving_km": float(row[4] or 0),
                    "waypoints": row[5] if row[5] else [],
                    "overnight_camping_id": (
                        str(row[6]) if row[6] else None
                    ),
                }
                total_hours += sched["driving_hours"]
                total_km += sched["driving_km"]
                schedules.append(sched)

            # Fetch photos linked to this trip
            photo_rows = conn.execute(
                text(
                    "SELECT id, file_url, thumbnail_url, "
                    "lat, lng, caption, original_filename "
                    "FROM photos WHERE trip_id = :tid"
                ),
                {"tid": trip_id},
            ).fetchall()

            photos = []
            for row in photo_rows:
                photos.append({
                    "id": str(row[0]),
                    "file_url": row[1],
                    "thumbnail_url": row[2],
                    "lat": float(row[3]) if row[3] else None,
                    "lng": float(row[4]) if row[4] else None,
                    "caption": row[5],
                    "filename": row[6],
                })

            return {
                "status": "success",
                "trip": trip,
                "daily_schedules": schedules,
                "photos": photos,
                "total_driving_hours": round(total_hours, 1),
                "total_driving_km": round(total_km, 1),
                "num_days": len(schedules),
                "num_photos": len(photos),
            }

    except Exception as e:
        return {
            "status": "error",
            "message": f"Failed to fetch trip data: {e}",
        }


def generate_summary(
    trip_id,
    format="image_slideshow",
    include_map_animation=True,
    include_photos=True,
    music_track=None,
):
    """
    Generate a visual trip summary export.

    Args:
        trip_id (str): UUID of the trip.
        format (str): Output format
            ('video', 'image_slideshow', 'pdf').
        include_map_animation (bool): Include route animation.
        include_photos (bool): Include trip photos.
        music_track (str): Optional background music path.

    Returns:
        dict: Summary metadata with file URL.
    """
    # Fetch trip data
    trip_data = get_trip_summary(trip_id)

    if trip_data["status"] != "success":
        return trip_data

    # Ensure output directory exists
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    # Generate based on format
    if format == "image_slideshow":
        result = _generate_slideshow(trip_data)
    elif format == "pdf":
        result = _generate_pdf_report(trip_data)
    elif format == "video":
        result = _generate_video_placeholder(trip_data)
    else:
        return {
            "status": "error",
            "message": (
                f"Unsupported format: '{format}'. "
                "Use: image_slideshow, pdf, or video."
            ),
        }

    if result["status"] != "success":
        return result

    # Store summary record in database
    summary_id = str(uuid.uuid4())
    _persist_summary(
        summary_id=summary_id,
        trip_id=trip_id,
        user_id=trip_data["trip"]["user_id"],
        format=format,
        file_url=result["file_url"],
        music_track=music_track,
        include_map_animation=include_map_animation,
        include_photos=include_photos,
    )

    return {
        "status": "success",
        "summary": {
            "id": summary_id,
            "trip_id": trip_id,
            "format": format,
            "file_url": result["file_url"],
        },
        "file_url": result["file_url"],
    }


def _generate_slideshow(trip_data):
    """
    Generate an image slideshow summary of the trip.

    Creates a series of PNG slides:
    - Title slide with trip name and dates
    - Day-by-day slides with waypoints and stats
    - Final summary slide with totals

    Returns:
        dict: Result with file_url to the first slide.
    """
    trip = trip_data["trip"]
    schedules = trip_data["daily_schedules"]

    slides = []

    # ── Slide 1: Title ─────────────────────────────────────
    title_slide = _create_slide(
        title=trip["title"],
        subtitle=(
            f"{trip.get('start_date', '')} → "
            f"{trip.get('end_date', '')}"
        ),
        body=(
            f"{trip_data['num_days']} days · "
            f"{trip_data['total_driving_km']}km · "
            f"{trip_data['total_driving_hours']}h driving"
        ),
        color_bg=(0, 30, 80),
        color_text=(255, 255, 255),
    )
    slides.append(title_slide)

    # ── Day Slides ─────────────────────────────────────────
    for day in schedules:
        waypoint_labels = [
            wp.get("label", "Unknown")
            for wp in day.get("waypoints", [])
            if isinstance(wp, dict)
        ]
        route_text = " → ".join(waypoint_labels) if waypoint_labels else "No waypoints"

        day_slide = _create_slide(
            title=f"Day {day['day_number']}",
            subtitle=day.get("date", ""),
            body=(
                f"🚗 {day['driving_hours']}h · "
                f"{day['driving_km']}km\n\n"
                f"{route_text}"
            ),
            color_bg=(244, 246, 249),
            color_text=(0, 30, 80),
        )
        slides.append(day_slide)

    # ── Final Slide ────────────────────────────────────────
    final_slide = _create_slide(
        title="Trip Complete! 🚐",
        subtitle=trip["title"],
        body=(
            f"Total distance: {trip_data['total_driving_km']}km\n"
            f"Total driving: {trip_data['total_driving_hours']}h\n"
            f"Days: {trip_data['num_days']}\n"
            f"Photos: {trip_data['num_photos']}"
        ),
        color_bg=(0, 14, 38),
        color_text=(255, 255, 255),
    )
    slides.append(final_slide)

    # Save slides
    slide_paths = []
    trip_slug = trip["id"][:8]
    for i, slide in enumerate(slides):
        path = os.path.join(
            OUTPUT_DIR,
            f"summary_{trip_slug}_slide_{i + 1}.png",
        )
        slide.save(path)
        slide_paths.append(path)

    return {
        "status": "success",
        "file_url": slide_paths[0],
        "all_slides": slide_paths,
        "slide_count": len(slides),
    }


def _generate_pdf_report(trip_data):
    """
    Generate a PDF-style report as a tall image.

    For a full PDF, a library like reportlab or weasyprint
    would be used. This creates a visual summary image.

    Returns:
        dict: Result with file_url.
    """
    trip = trip_data["trip"]
    trip_slug = trip["id"][:8]

    # Create a tall summary image (report-style)
    report = _create_slide(
        title=trip["title"],
        subtitle=(
            f"{trip.get('start_date', '')} → "
            f"{trip.get('end_date', '')}"
        ),
        body=(
            f"📏 Total Distance: "
            f"{trip_data['total_driving_km']}km\n"
            f"⏱️ Total Driving: "
            f"{trip_data['total_driving_hours']}h\n"
            f"📅 Days: {trip_data['num_days']}\n"
            f"📷 Photos: {trip_data['num_photos']}\n\n"
            "--- Daily Breakdown ---\n"
            + "\n".join(
                f"Day {d['day_number']}: "
                f"{d['driving_hours']}h, {d['driving_km']}km"
                for d in trip_data["daily_schedules"]
            )
        ),
        color_bg=(255, 255, 255),
        color_text=(0, 30, 80),
        height=800,
    )

    path = os.path.join(
        OUTPUT_DIR, f"report_{trip_slug}.png"
    )
    report.save(path)

    return {
        "status": "success",
        "file_url": path,
    }


def _generate_video_placeholder(trip_data):
    """
    Placeholder for video generation.

    Full video generation requires ffmpeg and is planned
    for a future iteration.

    Returns:
        dict: Result with placeholder message.
    """
    # For now, generate a slideshow and note video is planned
    slideshow = _generate_slideshow(trip_data)

    return {
        "status": "success",
        "file_url": slideshow.get("file_url", ""),
        "message": (
            "Video generation requires ffmpeg. "
            "Slideshow generated as fallback."
        ),
    }


def _create_slide(
    title, subtitle="", body="",
    color_bg=(0, 30, 80), color_text=(255, 255, 255),
    width=1200, height=675,
):
    """
    Create a single summary slide as a PIL Image.

    Args:
        title (str): Main heading text.
        subtitle (str): Secondary text below title.
        body (str): Body text content.
        color_bg (tuple): RGB background color.
        color_text (tuple): RGB text color.
        width (int): Slide width in pixels.
        height (int): Slide height in pixels.

    Returns:
        PIL.Image: The rendered slide.
    """
    img = Image.new("RGB", (width, height), color=color_bg)
    draw = ImageDraw.Draw(img)

    # Use default font (system fonts may not be available)
    try:
        font_title = ImageFont.truetype(
            "/System/Library/Fonts/Helvetica.ttc", 48
        )
        font_subtitle = ImageFont.truetype(
            "/System/Library/Fonts/Helvetica.ttc", 24
        )
        font_body = ImageFont.truetype(
            "/System/Library/Fonts/Helvetica.ttc", 20
        )
    except (OSError, IOError):
        font_title = ImageFont.load_default()
        font_subtitle = ImageFont.load_default()
        font_body = ImageFont.load_default()

    # Draw title
    y_pos = height // 4
    draw.text(
        (60, y_pos), title, fill=color_text, font=font_title
    )

    # Draw subtitle
    if subtitle:
        y_pos += 60
        # Muted color for subtitle
        sub_color = tuple(
            min(255, c + 60) if sum(color_bg) < 384
            else max(0, c - 60)
            for c in color_text
        )
        draw.text(
            (60, y_pos), subtitle,
            fill=sub_color, font=font_subtitle,
        )

    # Draw body text
    if body:
        y_pos += 50
        for line in body.split("\n"):
            draw.text(
                (60, y_pos), line,
                fill=color_text, font=font_body,
            )
            y_pos += 28

    # VW watermark
    watermark = "VW California Trip Planner"
    draw.text(
        (60, height - 40), watermark,
        fill=tuple(
            min(255, c + 80) if sum(color_bg) < 384
            else max(0, c - 80)
            for c in color_text
        ),
        font=font_subtitle,
    )

    return img


def _persist_summary(
    summary_id, trip_id, user_id, format,
    file_url, music_track, include_map_animation,
    include_photos,
):
    """
    Save trip summary metadata to the database.

    Args:
        summary_id (str): UUID for the summary record.
        trip_id (str): Trip UUID.
        user_id (str): User UUID.
        format (str): Export format.
        file_url (str): Path to generated file.
        music_track (str): Optional music track name.
        include_map_animation (bool): Map animation flag.
        include_photos (bool): Photos inclusion flag.
    """
    try:
        engine = get_engine()
        with engine.connect() as conn:
            conn.execute(
                text("""
                    INSERT INTO trip_summaries
                        (id, trip_id, user_id, format,
                         file_url, music_track,
                         include_map_animation,
                         include_photos)
                    VALUES
                        (:id, :trip_id, :user_id, :format,
                         :file_url, :music_track,
                         :include_map, :include_photos)
                """),
                {
                    "id": summary_id,
                    "trip_id": trip_id,
                    "user_id": user_id,
                    "format": format,
                    "file_url": file_url,
                    "music_track": music_track,
                    "include_map": include_map_animation,
                    "include_photos": include_photos,
                },
            )
            conn.commit()
            print(f"  ✅ Summary saved: {summary_id[:8]}...")

    except Exception as e:
        print(f"  ⚠️  Failed to persist summary: {e}")


if __name__ == "__main__":
    import sys

    # Default: generate for the seed trip
    trip_id = (
        sys.argv[1] if len(sys.argv) > 1
        else "a0000001-0000-0000-0000-000000000001"
    )
    format = sys.argv[2] if len(sys.argv) > 2 else "image_slideshow"

    print(f"📊 Generating trip summary ({format})...")
    result = generate_summary(trip_id, format=format)

    if result["status"] == "success":
        print(f"  ✅ Summary generated!")
        print(f"  📁 File: {result['file_url']}")
    else:
        print(f"  ❌ {result.get('message', 'Unknown error')}")

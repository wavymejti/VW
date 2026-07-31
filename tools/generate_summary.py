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
import subprocess
import requests
from datetime import datetime
from io import BytesIO

from sqlalchemy import text
from PIL import Image, ImageDraw, ImageFont

# Google Maps polyline decoder
import googlemaps.convert

from tools.db import get_engine

# ReportLab imports for PDF generation
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.units import mm, cm, inch
from reportlab.lib.colors import HexColor, white, black
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Image as RLImage,
    Table, TableStyle, PageBreak, KeepTogether, Frame, PageTemplate
)
from reportlab.platypus.flowables import HRFlowable
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont


# Output directory for generated summaries
OUTPUT_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    ".tmp",
    "summaries",
)

# Animation settings
ANIMATION_FRAMES_PER_DAY = 30  # Number of frames per day's route animation
MAP_IMAGE_SIZE = (1280, 720)  # Width, height for map animation frames
MAP_PADDING = 50  # Padding around the route on the map image


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

            # Fetch daily schedules with camping info
            sched_rows = conn.execute(
                text("""
                    SELECT 
                        ds.id, ds.day_number, ds.schedule_date, 
                        ds.driving_hours, ds.driving_km, ds.waypoints, 
                        ds.overnight_camping_id,
                        ds.route_polyline,
                        c.name as camping_name,
                        c.photos as camping_photos
                    FROM daily_schedules ds
                    LEFT JOIN campings c ON ds.overnight_camping_id = c.id
                    WHERE ds.trip_id = :tid 
                    ORDER BY ds.day_number
                """),
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
                    "route_polyline": row[7] if row[7] else None,
                    "camping_name": row[8],
                    "camping_photos": row[9] if row[9] else [],
                }
                total_hours += sched["driving_hours"]
                total_km += sched["driving_km"]
                schedules.append(sched)

            # Fetch photos linked to this trip
            photo_rows = conn.execute(
                text(
                    "SELECT id, file_url, thumbnail_url, "
                    "lat, lng, caption, original_filename, tagged_day_schedule_id "
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
                    "tagged_day_schedule_id": str(row[7]) if row[7] else None,
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


def _open_photo_image(photo_path):
    """Safely open JPEG, PNG, or HEIC image files."""
    if not photo_path or not os.path.exists(photo_path):
        return None
    try:
        if photo_path.lower().endswith('.heic'):
            try:
                import pillow_heif
                heif_file = pillow_heif.read_heif(photo_path)
                return Image.frombytes(
                    heif_file.mode,
                    heif_file.size,
                    heif_file.data,
                    "raw",
                )
            except Exception as ex:
                print(f"  ⚠️ HEIC read failed for {photo_path}: {ex}")
                return None
        return Image.open(photo_path)
    except Exception as e:
        print(f"  ⚠️ Failed to open image {photo_path}: {e}")
        return None


def _generate_route_animation_frames(trip_data):
    """
    Generate map animation frames for the trip route.

    - Decodes Google Maps route polylines for each day
    - Interpolates N frames (ANIMATION_FRAMES_PER_DAY) between route points
    - Renders each frame with progressive route line & live photo popups at vehicle position
    """
    schedules = trip_data["daily_schedules"]
    trip = trip_data["trip"]
    photos = trip_data.get("photos", [])

    frames = []

    for day in schedules:
        route_polyline = day.get("route_polyline")
        if not route_polyline:
            continue

        day_number = day["day_number"]
        day_id = day.get("id")

        # Find photos for this day
        day_photos = [
            p for p in photos
            if (day_id and p.get("tagged_day_schedule_id") == day_id) or p.get("day_number") == day_number
        ]
        if not day_photos and photos:
            total_days = len(schedules)
            photos_per_day = max(1, len(photos) // total_days)
            start_idx = (day_number - 1) * photos_per_day
            day_photos = photos[start_idx : start_idx + photos_per_day]

        try:
            # Decode polyline to get list of lat/lng points
            decoded_points = googlemaps.convert.decode_polyline(route_polyline)
            if len(decoded_points) < 2:
                continue

            points = [(p['lat'], p['lng']) for p in decoded_points]

            # Calculate bounding box
            lats = [p[0] for p in points]
            lngs = [p[1] for p in points]
            min_lat, max_lat = min(lats), max(lats)
            min_lng, max_lng = min(lngs), max(lngs)

            lat_padding = (max_lat - min_lat) * 0.1
            lng_padding = (max_lng - min_lng) * 0.1
            min_lat -= lat_padding
            max_lat += lat_padding
            min_lng -= lng_padding
            max_lng += lng_padding

            def haversine(lat1, lng1, lat2, lng2):
                from math import radians, sin, cos, sqrt, atan2
                R = 6371000
                lat1, lng1, lat2, lng2 = map(radians, [lat1, lng1, lat2, lng2])
                dlat = lat2 - lat1
                dlng = lng2 - lng1
                a = sin(dlat/2)**2 + cos(lat1) * cos(lat2) * sin(dlng/2)**2
                c = 2 * atan2(sqrt(a), sqrt(1-a))
                return R * c

            distances = [0]
            total_distance = 0
            for i in range(1, len(points)):
                dist = haversine(points[i-1][0], points[i-1][1], points[i][0], points[i][1])
                total_distance += dist
                distances.append(total_distance)

            # Map day photos to progress milestones along the route
            photo_milestones = []
            for idx, photo in enumerate(day_photos):
                photo_lat = photo.get("lat")
                photo_lng = photo.get("lng")
                if photo_lat and photo_lng and total_distance > 0:
                    best_dist = float('inf')
                    best_prog = 0.5
                    for i, (plat, plng) in enumerate(points):
                        d = (plat - photo_lat)**2 + (plng - photo_lng)**2
                        if d < best_dist:
                            best_dist = d
                            best_prog = distances[i] / total_distance
                    photo_milestones.append((best_prog, photo))
                else:
                    prog = (idx + 1) / (len(day_photos) + 1)
                    photo_milestones.append((prog, photo))

            # Generate frames
            for frame_idx in range(ANIMATION_FRAMES_PER_DAY):
                progress = (frame_idx + 1) / ANIMATION_FRAMES_PER_DAY
                target_distance = total_distance * progress

                segment_idx = 0
                for i in range(1, len(distances)):
                    if distances[i] >= target_distance:
                        segment_idx = i - 1
                        break
                else:
                    segment_idx = len(points) - 2

                if segment_idx < len(points) - 1:
                    seg_start_dist = distances[segment_idx]
                    seg_end_dist = distances[segment_idx + 1]
                    seg_length = seg_end_dist - seg_start_dist

                    if seg_length > 0:
                        local_progress = (target_distance - seg_start_dist) / seg_length
                        local_progress = max(0, min(1, local_progress))
                    else:
                        local_progress = 0

                    lat1, lng1 = points[segment_idx]
                    lat2, lng2 = points[segment_idx + 1]
                    interp_lat = lat1 + (lat2 - lat1) * local_progress
                    interp_lng = lng1 + (lng2 - lng1) * local_progress
                    draw_points = points[:segment_idx + 1] + [(interp_lat, interp_lng)]
                else:
                    draw_points = points

                # Determine active photo overlay for current vehicle position
                active_photo = None
                for prog, photo in photo_milestones:
                    if abs(progress - prog) < 0.15:
                        active_photo = photo
                        break

                img = _render_map_frame(
                    draw_points,
                    points,
                    (min_lat, max_lat, min_lng, max_lng),
                    day_number,
                    progress,
                    MAP_IMAGE_SIZE[0],
                    MAP_IMAGE_SIZE[1],
                    active_photo=active_photo
                )

                frames.append(img)

                # Pause for 6 extra frames when van arrives right at the photo spot
                if active_photo:
                    for prog, _ in photo_milestones:
                        if abs(progress - prog) < 0.025:
                            for _ in range(6):
                                frames.append(img)
                            break

        except Exception as e:
            print(f"  ⚠️  Failed to generate animation frames for day {day_number}: {e}")
            continue

    return frames


def _render_map_frame(current_points, all_points, bbox, day_number, progress, width, height, active_photo=None):
    """
    Render a single map animation frame with progressive route line & photo popups.
    """
    img = Image.new("RGB", (width, height), color=(0, 30, 80))
    draw = ImageDraw.Draw(img)

    min_lat, max_lat, min_lng, max_lng = bbox

    def lat_lng_to_xy(lat, lng):
        x_norm = (lng - min_lng) / (max_lng - min_lng) if max_lng != min_lng else 0.5
        y_norm = (lat - min_lat) / (max_lat - min_lat) if max_lat != min_lat else 0.5
        y_norm = 1 - y_norm
        x = MAP_PADDING + x_norm * (width - 2 * MAP_PADDING)
        y = MAP_PADDING + y_norm * (height - 2 * MAP_PADDING)
        return (x, y)

    # Draw full route line (faint)
    if len(all_points) >= 2:
        full_xy = [lat_lng_to_xy(lat, lng) for lat, lng in all_points]
        for i in range(len(full_xy) - 1):
            draw.line([full_xy[i], full_xy[i+1]], fill=(0, 60, 120), width=2)

    # Draw progressive route line (bright)
    if len(current_points) >= 2:
        current_xy = [lat_lng_to_xy(lat, lng) for lat, lng in current_points]
        for i in range(len(current_xy) - 1):
            progress_factor = i / (len(current_xy) - 1) if len(current_xy) > 1 else 0
            r = int(0 + 255 * progress_factor)
            g = int(180 + 75 * progress_factor)
            b = 255
            draw.line([current_xy[i], current_xy[i+1]], fill=(r, g, b), width=4)

    # Start marker
    if all_points:
        start_xy = lat_lng_to_xy(all_points[0][0], all_points[0][1])
        draw.ellipse([start_xy[0]-8, start_xy[1]-8, start_xy[0]+8, start_xy[1]+8],
                     fill=(0, 255, 100), outline=(255, 255, 255), width=2)

    # Vehicle position marker (yellow dot)
    if current_points:
        current_xy = lat_lng_to_xy(current_points[-1][0], current_points[-1][1])
        pulse_size = 8 + 4 * abs((progress * 4) % 2 - 1)
        draw.ellipse([current_xy[0]-pulse_size, current_xy[1]-pulse_size,
                      current_xy[0]+pulse_size, current_xy[1]+pulse_size],
                     fill=(255, 200, 0), outline=(255, 255, 255), width=2)

    # End marker
    if len(all_points) > 1:
        end_xy = lat_lng_to_xy(all_points[-1][0], all_points[-1][1])
        draw.ellipse([end_xy[0]-8, end_xy[1]-8, end_xy[0]+8, end_xy[1]+8],
                     fill=(255, 50, 50), outline=(255, 255, 255), width=2)

    # Render Photo Popup Overlay at Vehicle Position (yellow dot)
    if active_photo and current_points:
        photo_path = active_photo.get("file_url")
        photo_img = _open_photo_image(photo_path)
        if photo_img:
            try:
                curr_xy = lat_lng_to_xy(current_points[-1][0], current_points[-1][1])

                thumb = photo_img.copy()
                thumb.thumbnail((160, 105), Image.Resampling.LANCZOS)

                card_w = thumb.width + 16
                card_h = thumb.height + 26

                card_x = int(curr_xy[0] - card_w / 2)
                card_y = int(curr_xy[1] - card_h - 25)

                card_x = max(15, min(width - card_w - 15, card_x))
                card_y = max(15, min(height - card_h - 15, card_y))

                # Connector line
                conn_target = (card_x + card_w // 2, card_y + card_h)
                draw.line([curr_xy, conn_target], fill=(255, 200, 0), width=3)

                # Card frame & border
                draw.rectangle(
                    [card_x - 3, card_y - 3, card_x + card_w + 3, card_y + card_h + 3],
                    fill=(0, 14, 38), outline=(255, 255, 255), width=2
                )

                img.paste(thumb, (card_x + 8, card_y + 8))

                caption = active_photo.get("caption") or os.path.basename(photo_path)
                if len(caption) > 18:
                    caption = caption[:16] + ".."
                
                try:
                    font_cap = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", 13)
                except Exception:
                    font_cap = ImageFont.load_default()

                draw.text((card_x + 8, card_y + thumb.height + 10), caption, fill=(255, 255, 255), font=font_cap)
            except Exception as ex:
                print(f"  ⚠️ Photo popup overlay error: {ex}")

    # Labels
    try:
        font_title = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", 36)
        font_subtitle = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", 20)
        font_progress = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", 18)
    except (OSError, IOError):
        font_title = ImageFont.load_default()
        font_subtitle = ImageFont.load_default()
        font_progress = ImageFont.load_default()

    draw.text((20, 20), f"Dzień {day_number}", fill=(255, 255, 255), font=font_title)

    # Progress bar
    bar_width = width - 40
    bar_height = 8
    bar_x = 20
    bar_y = height - 40
    draw.rectangle([bar_x, bar_y, bar_x + bar_width, bar_y + bar_height],
                   fill=(0, 60, 120), outline=(100, 100, 100))
    draw.rectangle([bar_x, bar_y, bar_x + bar_width * progress, bar_y + bar_height],
                   fill=(0, 180, 255))

    progress_text = f"{int(progress * 100)}%"
    draw.text((width - 80, bar_y - 25), progress_text, fill=(200, 200, 200), font=font_progress)

    watermark = "VW California Trip Planner"
    draw.text((20, height - 30), watermark, fill=(100, 100, 100), font=font_subtitle)

    return img


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
        result = _generate_slideshow(trip_data, include_map_animation)
    elif format == "pdf":
        result = _generate_pdf_report(trip_data, include_photos)
    elif format == "video":
        result = _generate_video(trip_data, music_track=music_track)
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

    res_dict = {
        "status": "success",
        "summary": {
            "id": summary_id,
            "trip_id": trip_id,
            "format": format,
            "file_url": result["file_url"],
        },
        "file_url": result["file_url"],
    }
    if "all_slides" in result:
        res_dict["all_slides"] = result["all_slides"]
    if "slide_count" in result:
        res_dict["slide_count"] = result["slide_count"]
    return res_dict


def _generate_slideshow(trip_data, include_map_animation=True):
    """
    Generate an image slideshow summary of the trip.

    Creates a series of PNG slides:
    - Title slide with trip name and dates
    - Map animation frames (if include_map_animation and route_polyline exists)
    - Day-by-day slides with waypoints and stats
    - Final summary slide with totals

    Returns:
        dict: Result with file_url to the first slide.
    """
    trip = trip_data["trip"]
    schedules = trip_data["daily_schedules"]

    slides = []

    # Slide 1: Title
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

    # Map Animation Frames (if enabled)
    if include_map_animation:
        print("  🗺️  Generating map animation frames...")
        animation_frames = _generate_route_animation_frames(trip_data)
        slides.extend(animation_frames)
        print(f"  ✅ Generated {len(animation_frames)} animation frames")

    # Day Slides & Chronological Photo Memory Slides
    all_photos = trip_data.get("photos", [])

    for day in schedules:
        waypoint_labels = [
            wp.get("label", "Unknown")
            for wp in day.get("waypoints", [])
            if isinstance(wp, dict)
        ]
        route_text = " → ".join(waypoint_labels) if waypoint_labels else "Brak punktów"

        day_body = (
            f"Jazda: {day['driving_hours']}h · "
            f"Dystans: {day['driving_km']}km\n\n"
            f"{route_text}"
        )
        if day.get("camping_name"):
            day_body += f"\n\nNocleg: {day['camping_name']}"

        day_photos = [
            p for p in all_photos
            if p.get("tagged_day_schedule_id") == day["id"] or p.get("day_number") == day["day_number"]
        ]
        day_photo_path = day_photos[0]["file_url"] if day_photos else (
            _download_image(day["camping_photos"][0]) if day.get("camping_photos") else None
        )

        day_slide = _create_slide(
            title=f"Dzień {day['day_number']}",
            subtitle=day.get("date", ""),
            body=day_body,
            color_bg=(244, 246, 249),
            color_text=(0, 30, 80),
            image_path=day_photo_path
        )
        slides.append(day_slide)

        # Append dedicated photo slides for this specific day right after the day slide
        for photo in day_photos:
            photo_path = photo.get("file_url")
            if photo_path and os.path.exists(photo_path):
                caption = photo.get("caption") or photo.get("filename") or f"Dzień {day['day_number']} — Wspomnienie"
                photo_slide = _create_slide(
                    title=f"📷 Wspomnienie — Dzień {day['day_number']}",
                    subtitle=caption,
                    body=f"Wpis z Travel Memory · {trip.get('title', '')}",
                    color_bg=(0, 14, 38),
                    color_text=(255, 255, 255),
                    image_path=photo_path
                )
                slides.append(photo_slide)

    # Final Slide
    # Try to find a photo for the final summary slide
    final_photo_path = None
    if trip_data["photos"]:
        final_photo_path = trip_data["photos"][0]["file_url"]

    final_slide = _create_slide(
        title="Wyjazd zakończony!",
        subtitle=trip["title"],
        body=(
            f"Całkowity dystans: {trip_data['total_driving_km']}km\n"
            f"Czas za kierownicą: {trip_data['total_driving_hours']}h\n"
            f"Liczba dni: {trip_data['num_days']}\n"
            f"Zebrane wspomnienia: {len(trip_data['photos'])} zdjęć"
        ),
        color_bg=(0, 14, 38),
        color_text=(255, 255, 255),
        image_path=final_photo_path
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
def _generate_pdf_report(trip_data, include_photos=True):
    """
    Generate a proper PDF report using reportlab.

    Creates a multi-page PDF with:
    - Title page with trip name, dates, and overview stats
    - Statistics summary page
    - Daily breakdown with waypoints and camping info
    - Photo gallery (if include_photos=True and photos exist)

    Returns:
        dict: Result with file_url to the PDF.
    """
    trip = trip_data["trip"]
    schedules = trip_data["daily_schedules"]
    photos = trip_data["photos"]
    trip_slug = trip["id"][:8]

    # Output PDF path
    pdf_path = os.path.join(OUTPUT_DIR, f"report_{trip_slug}.pdf")

    # Create PDF document
    doc = SimpleDocTemplate(
        pdf_path,
        pagesize=A4,
        rightMargin=2*cm,
        leftMargin=2*cm,
        topMargin=2*cm,
        bottomMargin=2*cm,
    )

    # Define colors
    VW_DARK_BLUE = HexColor("#001E50")
    VW_MEDIUM_BLUE = HexColor("#003D8F")
    VW_LIGHT_BLUE = HexColor("#E4F0FA")
    VW_GOLD = HexColor("#FFB800")
    WHITE = white
    BLACK = black
    LIGHT_GRAY = HexColor("#F4F6F9")
    DARK_GRAY = HexColor("#333333")

    # Define styles
    styles = getSampleStyleSheet()

    title_style = ParagraphStyle(
        'VWTitle',
        parent=styles['Title'],
        fontName='Helvetica-Bold',
        fontSize=28,
        textColor=VW_DARK_BLUE,
        spaceAfter=6,
        alignment=TA_CENTER,
    )

    subtitle_style = ParagraphStyle(
        'VWSubtitle',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=16,
        textColor=VW_MEDIUM_BLUE,
        spaceAfter=12,
        alignment=TA_CENTER,
    )

    heading_style = ParagraphStyle(
        'VWHeading',
        parent=styles['Heading1'],
        fontName='Helvetica-Bold',
        fontSize=18,
        textColor=VW_DARK_BLUE,
        spaceBefore=18,
        spaceAfter=10,
        borderWidth=0,
        borderPadding=0,
    )

    subheading_style = ParagraphStyle(
        'VWSubHeading',
        parent=styles['Heading2'],
        fontName='Helvetica-Bold',
        fontSize=14,
        textColor=VW_MEDIUM_BLUE,
        spaceBefore=12,
        spaceAfter=6,
    )

    body_style = ParagraphStyle(
        'VWBody',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=11,
        textColor=DARK_GRAY,
        spaceAfter=6,
        leading=15,
    )

    body_bold_style = ParagraphStyle(
        'VWBodyBold',
        parent=body_style,
        fontName='Helvetica-Bold',
    )

    small_style = ParagraphStyle(
        'VWSmall',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=9,
        textColor=HexColor("#666666"),
        spaceAfter=4,
        leading=12,
    )

    caption_style = ParagraphStyle(
        'VWCaption',
        parent=styles['Normal'],
        fontName='Helvetica-Oblique',
        fontSize=9,
        textColor=HexColor("#888888"),
        spaceAfter=8,
        alignment=TA_CENTER,
    )

    stat_label_style = ParagraphStyle(
        'VWStatLabel',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=10,
        textColor=HexColor("#666666"),
        alignment=TA_CENTER,
    )

    stat_value_style = ParagraphStyle(
        'VWStatValue',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=24,
        textColor=VW_DARK_BLUE,
        alignment=TA_CENTER,
    )

    # Build story (content)
    story = []

    # ============================================================
    # PAGE 1: TITLE PAGE
    # ============================================================
    story.append(Spacer(1, 4*cm))

    # VW Logo placeholder / Brand
    brand_text = Paragraph("VW California Trip Planner", ParagraphStyle(
        'Brand', parent=styles['Normal'], fontName='Helvetica-Bold',
        fontSize=14, textColor=VW_MEDIUM_BLUE, alignment=TA_CENTER
    ))
    story.append(brand_text)
    story.append(Spacer(1, 1*cm))

    # Trip title
    story.append(Paragraph(trip["title"], title_style))
    story.append(Spacer(1, 0.5*cm))

    # Dates
    start_date = trip.get('start_date', '')
    end_date = trip.get('end_date', '')
    if start_date and end_date:
        date_text = f"{start_date} \u2192 {end_date}"
    elif start_date:
        date_text = f"From {start_date}"
    elif end_date:
        date_text = f"Until {end_date}"
    else:
        date_text = "Dates not specified"
    story.append(Paragraph(date_text, subtitle_style))
    story.append(Spacer(1, 2*cm))

    # Horizontal rule
    story.append(HRFlowable(width="60%", thickness=2, color=VW_GOLD, spaceAfter=2*cm))

    # Key stats boxes
    stats_data = [
        [
            Paragraph(f"{trip_data['total_driving_km']:.0f}", stat_value_style),
            Paragraph(f"{trip_data['total_driving_hours']:.1f}", stat_value_style),
            Paragraph(f"{trip_data['num_days']}", stat_value_style),
            Paragraph(f"{trip_data['num_photos']}", stat_value_style),
        ],
        [
            Paragraph("Total km", stat_label_style),
            Paragraph("Driving hours", stat_label_style),
            Paragraph("Days", stat_label_style),
            Paragraph("Photos", stat_label_style),
        ],
    ]

    stats_table = Table(stats_data, colWidths=[4.5*cm]*4)
    stats_table.setStyle(TableStyle([
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('TOPPADDING', (0, 0), (-1, 0), 4),
        ('BOTTOMPADDING', (0, 1), (-1, 1), 4),
    ]))
    story.append(stats_table)
    story.append(Spacer(1, 2*cm))

    # Origin / Destination
    if trip.get('origin_label') or trip.get('destination_label'):
        route_data = []
        if trip.get('origin_label'):
            route_data.append(['\U0001F4CD Start:', trip['origin_label']])
        if trip.get('destination_label'):
            route_data.append(['\U0001F3C1 Destination:', trip['destination_label']])

        route_table = Table(route_data, colWidths=[3*cm, 12*cm])
        route_table.setStyle(TableStyle([
            ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, -1), 11),
            ('TEXTCOLOR', (0, 0), (0, -1), VW_DARK_BLUE),
            ('TEXTCOLOR', (1, 0), (1, -1), DARK_GRAY),
            ('TOPPADDING', (0, 0), (-1, -1), 4),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ]))
        story.append(route_table)

    story.append(PageBreak())

    # ============================================================
    # PAGE 2: STATISTICS SUMMARY
    # ============================================================
    story.append(Paragraph("Trip Statistics", heading_style))
    story.append(HRFlowable(width="100%", thickness=1, color=VW_MEDIUM_BLUE, spaceAfter=12))

    # Summary stats table
    summary_data = [
        ['Metric', 'Value'],
        ['Total Distance', f"{trip_data['total_driving_km']:.1f} km"],
        ['Total Driving Time', f"{trip_data['total_driving_hours']:.1f} hours"],
        ['Number of Days', str(trip_data['num_days'])],
        ['Total Photos', str(trip_data['num_photos'])],
        ['Average km/day', f"{trip_data['total_driving_km'] / max(trip_data['num_days'], 1):.1f} km"],
        ['Average hours/day', f"{trip_data['total_driving_hours'] / max(trip_data['num_days'], 1):.1f} h"],
    ]

    if trip_data['num_days'] > 0:
        summary_data.append(['Longest Day (km)', f"{max((d['driving_km'] for d in schedules), default=0):.1f} km"])
        summary_data.append(['Longest Day (hours)', f"{max((d['driving_hours'] for d in schedules), default=0):.1f} h"])

    summary_table = Table(summary_data, colWidths=[8*cm, 8*cm])
    summary_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), VW_DARK_BLUE),
        ('TEXTCOLOR', (0, 0), (-1, 0), WHITE),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 12),
        ('FONTNAME', (0, 1), (0, -1), 'Helvetica'),
        ('FONTNAME', (1, 1), (1, -1), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 1), (-1, -1), 11),
        ('TEXTCOLOR', (0, 1), (-1, -1), DARK_GRAY),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('ALIGN', (1, 0), (1, -1), 'RIGHT'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('GRID', (0, 0), (-1, -1), 0.5, HexColor("#DDDDDD")),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [WHITE, LIGHT_GRAY]),
        ('TOPPADDING', (0, 0), (-1, -1), 8),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
        ('LEFTPADDING', (0, 0), (-1, -1), 12),
        ('RIGHTPADDING', (0, 0), (-1, -1), 12),
    ]))
    story.append(summary_table)
    story.append(Spacer(1, 1*cm))

    # Camping summary
    campings = [d for d in schedules if d.get('camping_name')]
    if campings:
        story.append(Paragraph("Overnight Campings", subheading_style))
        camping_data = [['Day', 'Date', 'Camping']]
        for d in campings:
            camping_data.append([
                str(d['day_number']),
                d.get('date', ''),
                d['camping_name']
            ])

        camping_table = Table(camping_data, colWidths=[2*cm, 3*cm, 11*cm])
        camping_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), VW_DARK_BLUE),
            ('TEXTCOLOR', (0, 0), (-1, 0), WHITE),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, -1), 10),
            ('TEXTCOLOR', (0, 1), (-1, -1), DARK_GRAY),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('GRID', (0, 0), (-1, -1), 0.5, HexColor("#DDDDDD")),
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [WHITE, LIGHT_GRAY]),
            ('TOPPADDING', (0, 0), (-1, -1), 6),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
            ('LEFTPADDING', (0, 0), (-1, -1), 8),
        ]))
        story.append(camping_table)

    story.append(PageBreak())

    # ============================================================
    # PAGE 3+: DAILY BREAKDOWN
    # ============================================================
    story.append(Paragraph("Daily Itinerary", heading_style))
    story.append(HRFlowable(width="100%", thickness=1, color=VW_MEDIUM_BLUE, spaceAfter=12))

    for day in schedules:
        # Day header
        day_title = f"Day {day['day_number']}"
        if day.get('date'):
            day_title += f" \u2014 {day['date']}"
        story.append(Paragraph(day_title, subheading_style))

        # Waypoints
        waypoint_labels = [
            wp.get("label", "Unknown")
            for wp in day.get("waypoints", [])
            if isinstance(wp, dict)
        ]
        if waypoint_labels:
            route_text = " \u2192 ".join(waypoint_labels)
            story.append(Paragraph(f"<b>Route:</b> {route_text}", body_style))

        # Driving stats
        stats_text = f"<b>Drive:</b> {day['driving_hours']}h \u00b7 <b>Distance:</b> {day['driving_km']}km"
        story.append(Paragraph(stats_text, body_style))

        # Camping
        if day.get("camping_name"):
            story.append(Paragraph(f"<b>Camping:</b> {day['camping_name']}", body_style))

        # Photos for this day
        if include_photos:
            day_photos = [p for p in photos if p.get("tagged_day_schedule_id") == day["id"]]
            if day_photos:
                story.append(Spacer(1, 6))
                story.append(Paragraph(f"<b>Photos ({len(day_photos)})</b>", body_style))
                for photo in day_photos[:3]:  # Limit to 3 photos per day
                    caption = photo.get('caption') or photo.get('filename') or 'Photo'
                    story.append(Paragraph(f"\u2022 {caption}", small_style))

        story.append(Spacer(1, 8))

    story.append(PageBreak())

    # ============================================================
    # PHOTO GALLERY (if include_photos and photos exist)
    # ============================================================
    if include_photos and photos:
        story.append(Paragraph("Photo Gallery", heading_style))
        story.append(HRFlowable(width="100%", thickness=1, color=VW_MEDIUM_BLUE, spaceAfter=12))

        # Group photos by day
        photos_by_day = {}
        untagged_photos = []
        for photo in photos:
            day_id = photo.get("tagged_day_schedule_id")
            if day_id:
                if day_id not in photos_by_day:
                    photos_by_day[day_id] = []
                photos_by_day[day_id].append(photo)
            else:
                untagged_photos.append(photo)

        # Photos by day
        for day in schedules:
            day_id = day["id"]
            if day_id in photos_by_day and photos_by_day[day_id]:
                story.append(Paragraph(f"Day {day['day_number']}", subheading_style))
                day_photos = photos_by_day[day_id]
                for photo in day_photos:
                    caption = photo.get('caption') or photo.get('filename') or 'Photo'
                    story.append(Paragraph(f"\u2022 {caption}", body_style))
                story.append(Spacer(1, 8))

        # Untagged photos
        if untagged_photos:
            story.append(Paragraph("Additional Photos", subheading_style))
            for photo in untagged_photos:
                caption = photo.get('caption') or photo.get('filename') or 'Photo'
                story.append(Paragraph(f"\u2022 {caption}", body_style))

    # Build PDF
    doc.build(story)

    return {
        "status": "success",
        "file_url": pdf_path,
    }




def _generate_video(trip_data, music_track=None):
    """
    Generate an MP4 video summary using ffmpeg.
    
    Args:
        trip_data (dict): Trip data dictionary.
        music_track (str): Optional background music track path.
        
    Returns:
        dict: Result with file_url.
    """
    # First generate the individual slides
    slideshow = _generate_slideshow(trip_data)
    if slideshow["status"] != "success":
        return slideshow

    slides = slideshow.get("all_slides", [])
    if not slides:
        return {"status": "error", "message": "No slides generated."}

    trip = trip_data["trip"]
    trip_slug = trip["id"][:8]
    list_file_path = os.path.join(OUTPUT_DIR, f"slides_list_{trip_slug}.txt")
    output_mp4 = os.path.join(OUTPUT_DIR, f"summary_{trip_slug}.mp4")

    try:
        # Create ffmpeg concat file
        with open(list_file_path, "w") as f:
            for slide_path in slides:
                f.write(f"file '{slide_path}'\n")
                f.write("duration 3\n")
            # The concat demuxer ignores the duration of the last file,
            # so we add the last file again without a duration to finish cleanly.
            f.write(f"file '{slides[-1]}'\n")

        # Build ffmpeg command with optional looping music
        cmd = [
            "ffmpeg", "-y",
            "-f", "concat",
            "-safe", "0",
            "-i", list_file_path,
        ]

        music_path = None
        if music_track:
            music_path = _resolve_music_track(music_track)
            if music_path and os.path.exists(music_path):
                # -stream_loop -1 makes the music loop indefinitely so it
                # never cuts the video short (unlike -shortest with a 30s clip)
                cmd = [
                    "ffmpeg", "-y",
                    "-f", "concat",
                    "-safe", "0",
                    "-i", list_file_path,
                    "-stream_loop", "-1",
                    "-i", music_path,
                ]
            else:
                print(f"  ⚠️  Music track not found: {music_track}")

        # Video pixel format filter (must come after all inputs)
        cmd.extend(["-vf", "format=yuv420p"])

        # Audio filter: lower volume; stop audio when video ends (-shortest
        # is now safe because audio loops forever and video is always shorter)
        if music_path and os.path.exists(music_path):
            cmd.extend(["-filter:a", "volume=0.25", "-shortest"])

        cmd.append(output_mp4)

        subprocess.run(cmd, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

        return {
            "status": "success",
            "file_url": output_mp4,
        }

    except subprocess.CalledProcessError as e:
        return {
            "status": "error",
            "message": f"FFmpeg failed: {e.stderr.decode('utf-8', errors='ignore')}"
        }
    except Exception as e:
        return {
            "status": "error",
            "message": f"Video generation failed: {str(e)}"
        }


def _resolve_music_track(music_track):
    """
    Resolve a music track path, checking predefined audio tracks and relative paths.

    Args:
        music_track (str): Music track name or path.

    Returns:
        str: Resolved absolute path, or None if not found.
    """
    if not music_track:
        return None

    if os.path.isabs(music_track) and os.path.exists(music_track):
        return music_track

    # Clean track name
    clean_name = music_track.split('/')[-1]
    if not clean_name.endswith('.mp3') and not clean_name.endswith('.wav'):
        clean_name += '.mp3'

    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    candidates = [
        os.path.join(project_root, "tools", "assets", "audio", clean_name),
        os.path.join(project_root, "frontend", "assets", "audio", clean_name),
        os.path.join(OUTPUT_DIR, music_track),
        os.path.join(os.path.dirname(OUTPUT_DIR), music_track),
        os.path.join(os.getcwd(), music_track),
    ]

    for cand in candidates:
        if os.path.exists(cand):
            return cand

    return None



def _download_image(url):
    """
    Download an image from a URL and save it to a temporary file.

    Args:
        url (str): Image URL.

    Returns:
        str: Path to the downloaded image, or None if failed.
    """
    if not url or not url.startswith("http"):
        return None

    try:
        response = requests.get(url, timeout=10)
        if response.status_code == 200:
            ext = url.split(".")[-1].split("?")[0]
            if len(ext) > 4:
                ext = "jpg"
            filename = f"tmp_img_{uuid.uuid4().hex[:8]}.{ext}"
            path = os.path.join(OUTPUT_DIR, filename)
            with open(path, "wb") as f:
                f.write(response.content)
            return path
    except Exception as e:
        print(f"  \u26a0\ufe0f  Failed to download image {url}: {e}")

    return None


def _create_slide(
    title, subtitle="", body="",
    color_bg=(0, 30, 80), color_text=(255, 255, 255),
    width=1280, height=720,
    image_path=None
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
        image_path (str): Optional path to an image to display on the right.

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
            # Simple line wrap (crude)
            if len(line) > 50 and not image_path:
                pass # TODO: wrap

            draw.text(
                (60, y_pos), line,
                fill=color_text, font=font_body,
            )
            y_pos += 28

    # Draw image if provided
    if image_path and os.path.exists(image_path):
        try:
            overlay = Image.open(image_path)
            # Maintain aspect ratio, fit into 500x500 square on the right
            max_size = (500, 500)
            overlay.thumbnail(max_size, Image.Resampling.LANCZOS)

            # Position on the right side
            img_x = width - overlay.width - 60
            img_y = (height - overlay.height) // 2

            # Draw a subtle border/frame for the image
            draw.rectangle(
                [img_x - 5, img_y - 5, img_x + overlay.width + 5, img_y + overlay.height + 5],
                fill=(255, 255, 255) if sum(color_bg) < 384 else (0, 30, 80)
            )

            img.paste(overlay, (img_x, img_y))
        except Exception as e:
            print(f"  \u26a0\ufe0f  Failed to overlay image {image_path}: {e}")

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
            print(f"  \u2705 Summary saved: {summary_id[:8]}...")

    except Exception as e:
        print(f"  \u26a0\ufe0f  Failed to persist summary: {e}")


if __name__ == "__main__":
    import sys

    # Default: generate for the seed trip
    trip_id = (
        sys.argv[1] if len(sys.argv) > 1
        else "a0000001-0000-0000-0000-000000000001"
    )
    format = sys.argv[2] if len(sys.argv) > 2 else "image_slideshow"
    music_track = sys.argv[3] if len(sys.argv) > 3 else None

    print(f"\U0001f4ca Generating trip summary ({format})...")
    if music_track:
        print(f"  \U0001f3b5 Music track: {music_track}")
    result = generate_summary(trip_id, format=format, music_track=music_track)

    if result["status"] == "success":
        print(f"  \u2705 Summary generated!")
        print(f"  \U0001f4c1 File: {result['file_url']}")
    else:
        print(f"  \u274c {result.get('message', 'Unknown error')}")

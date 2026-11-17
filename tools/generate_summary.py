"""
Trip summary export tool for the VW California AI Trip Planner.

Generates cinematic, shareable trip summaries:
- Cinematic Video (MP4) with real terrain map animation (25 FPS), animated
  campervan sprite, live HUD odometer, photo highlights, and looped soundtrack
- Image slideshow of curated trip highlights
- Executive PDF dossier with map overview, stats, and photo gallery

See: architecture/summary_export_sop.md
"""

import os
import uuid
import json
import math
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
MAPS_CACHE_DIR = os.path.join(OUTPUT_DIR, "maps")

# Animation settings
ANIMATION_FRAMES_PER_DAY = 75  # 75 frames @ 25 FPS = 3.0s per day of ultra-smooth route motion
MAP_IMAGE_SIZE = (1280, 720)   # Width, height for video & slide frames
MAP_PADDING = 60

# Localization dictionary for summaries (PL / DE / EN)
I18N_SUMMARY = {
    "pl": {
        "day": "Dzień",
        "days": "dni",
        "driving": "jazdy",
        "no_waypoints": "Brak punktów",
        "drive": "Jazda",
        "distance": "Dystans",
        "overnight": "Nocleg",
        "memory_title": "📷 Wspomnienie — Dzień {day}",
        "memory_sub": "Wpis z Travel Memory · {title}",
        "trip_finished": "Wyjazd zakończony!",
        "total_distance": "Całkowity dystans",
        "driving_time": "Czas za kierownicą",
        "num_days": "Liczba dni",
        "collected_memories": "Zebrane wspomnienia: {count} zdjęć",
        "brand_title": "VW California Trip Planner",
        "from_date": "Od {date}",
        "until_date": "Do {date}",
        "no_dates": "Daty nieokreślone",
        "total_km": "Łącznie km",
        "driving_hours": "Godziny jazdy",
        "photos": "Zdjęcia",
        "start": "Start",
        "destination": "Cel",
        "trip_statistics": "Statystyki podróży",
        "metric": "Wskaźnik",
        "value": "Wartość",
        "total_dist_label": "Całkowity dystans",
        "total_drive_time": "Całkowity czas jazdy",
        "num_days_label": "Liczba dni",
        "total_photos": "Liczba zdjęć",
        "avg_km_day": "Średnio km / dzień",
        "avg_hours_day": "Średnio godzin / dzień",
        "longest_day_km": "Najdłuższy dzień (km)",
        "longest_day_h": "Najdłuższy dzień (godz.)",
        "hours_unit": "godz.",
        "overnight_campings": "Noclegi na kempingach",
        "table_day": "Dzień",
        "table_date": "Data",
        "table_camping": "Kemping",
        "daily_itinerary": "Plan dzień po dniu",
        "route_label": "Trasa",
        "camping_label": "Kemping",
        "photos_label": "Zdjęcia",
        "photo_default": "Zdjęcie",
        "photo_gallery": "Galeria zdjęć",
        "additional_photos": "Dodatkowe zdjęcia",
        "ready_for_adventure": "Gdzie zaprowadzi Cię kolejna droga?",
        "california_motto": "Volkswagen California · Twój mobilny dom na kółkach",
        "recap_title": "FILMOWE PODSUMOWANIE WYPRAWY",
    },
    "de": {
        "day": "Tag",
        "days": "Tage",
        "driving": "Fahrtzeit",
        "no_waypoints": "Keine Wegpunkte",
        "drive": "Fahrt",
        "distance": "Distanz",
        "overnight": "Übernachtung",
        "memory_title": "📷 Reiseerinnerung — Tag {day}",
        "memory_sub": "Travel Memory Eintrag · {title}",
        "trip_finished": "Reise beendet!",
        "total_distance": "Gesamtdistanz",
        "driving_time": "Fahrtzeit am Steuer",
        "num_days": "Anzahl Tage",
        "collected_memories": "Gesammelte Erinnerungen: {count} Fotos",
        "brand_title": "VW California Trip Planner",
        "from_date": "Ab {date}",
        "until_date": "Bis {date}",
        "no_dates": "Daten nicht angegeben",
        "total_km": "Gesamt km",
        "driving_hours": "Fahrtstunden",
        "photos": "Fotos",
        "start": "Start",
        "destination": "Ziel",
        "trip_statistics": "Reisestatistiken",
        "metric": "Kennzahl",
        "value": "Wert",
        "total_dist_label": "Gesamtdistanz",
        "total_drive_time": "Gesamte Fahrtzeit",
        "num_days_label": "Anzahl Tage",
        "total_photos": "Fotos gesamt",
        "avg_km_day": "Durchschnitt km / Tag",
        "avg_hours_day": "Durchschnitt Stunden / Tag",
        "longest_day_km": "Längster Tag (km)",
        "longest_day_h": "Längster Tag (Std.)",
        "hours_unit": "Std.",
        "overnight_campings": "Übernachtungs-Stellplätze",
        "table_day": "Tag",
        "table_date": "Datum",
        "table_camping": "Campingplatz / Stellplatz",
        "daily_itinerary": "Tagesübersicht",
        "route_label": "Route",
        "camping_label": "Stellplatz",
        "photos_label": "Fotos",
        "photo_default": "Foto",
        "photo_gallery": "Fotogalerie",
        "additional_photos": "Weitere Fotos",
        "ready_for_adventure": "Wohin führt die nächste Reise?",
        "california_motto": "Volkswagen California · Dein mobiles Zuhause",
        "recap_title": "FILMISCHE REISEERINNERUNG",
    },
    "en": {
        "day": "Day",
        "days": "days",
        "driving": "driving",
        "no_waypoints": "No waypoints",
        "drive": "Drive",
        "distance": "Distance",
        "overnight": "Overnight",
        "memory_title": "📷 Travel Memory — Day {day}",
        "memory_sub": "Travel Memory entry · {title}",
        "trip_finished": "Trip completed!",
        "total_distance": "Total distance",
        "driving_time": "Driving time",
        "num_days": "Number of days",
        "collected_memories": "Collected memories: {count} photos",
        "brand_title": "VW California Trip Planner",
        "from_date": "From {date}",
        "until_date": "Until {date}",
        "no_dates": "Dates not specified",
        "total_km": "Total km",
        "driving_hours": "Driving hours",
        "photos": "Photos",
        "start": "Start",
        "destination": "Destination",
        "trip_statistics": "Trip Statistics",
        "metric": "Metric",
        "value": "Value",
        "total_dist_label": "Total Distance",
        "total_drive_time": "Total Driving Time",
        "num_days_label": "Number of Days",
        "total_photos": "Total Photos",
        "avg_km_day": "Average km / day",
        "avg_hours_day": "Average hours / day",
        "longest_day_km": "Longest Day (km)",
        "longest_day_h": "Longest Day (hours)",
        "hours_unit": "hours",
        "overnight_campings": "Overnight Campings",
        "table_day": "Day",
        "table_date": "Date",
        "table_camping": "Campsite",
        "daily_itinerary": "Daily Itinerary",
        "route_label": "Route",
        "camping_label": "Campsite",
        "photos_label": "Photos",
        "photo_default": "Photo",
        "photo_gallery": "Photo Gallery",
        "additional_photos": "Additional Photos",
        "ready_for_adventure": "Where will the road take you next?",
        "california_motto": "Volkswagen California · Your home on wheels",
        "recap_title": "CINEMATIC TRIP RECAP",
    },
}


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
                    "lat, lng, caption, original_filename, tagged_day_schedule_id, captured_at "
                    "FROM photos "
                    "WHERE trip_id = :tid OR (user_id = :uid AND trip_id IS NULL) "
                    "ORDER BY captured_at ASC NULLS LAST, created_at ASC"
                ),
                {"tid": trip_id, "uid": trip["user_id"]},
            ).fetchall()

            photos = []
            seen_keys = set()
            for row in photo_rows:
                p_url = row[1]
                p_fname = row[6]
                dedup_key = p_url or p_fname or str(row[0])
                if dedup_key in seen_keys:
                    continue
                seen_keys.add(dedup_key)
                photos.append({
                    "id": str(row[0]),
                    "file_url": row[1],
                    "thumbnail_url": row[2],
                    "lat": float(row[3]) if row[3] else None,
                    "lng": float(row[4]) if row[4] else None,
                    "caption": row[5],
                    "filename": row[6],
                    "tagged_day_schedule_id": str(row[7]) if row[7] else None,
                    "captured_at": row[8].isoformat() if row[8] else None,
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
        if photo_path.lower().endswith(".heic"):
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
        return Image.open(photo_path).convert("RGB")
    except Exception as e:
        print(f"  ⚠️ Failed to open image {photo_path}: {e}")
        return None


def _get_font(size, bold=False):
    """Load system font with graceful fallback."""
    candidates = [
        "/System/Library/Fonts/Helvetica.ttc",
        "/System/Library/Fonts/Supplemental/Arial Bold.ttf" if bold else "/System/Library/Fonts/Supplemental/Arial.ttf",
        "/System/Library/Fonts/Supplemental/Arial.ttf",
        "/System/Library/Fonts/SFNS.ttf",
        "/Library/Fonts/Arial.ttf",
    ]
    for path in candidates:
        if os.path.exists(path):
            try:
                index = 1 if (bold and path.endswith(".ttc")) else 0
                return ImageFont.truetype(path, size, index=index)
            except Exception:
                try:
                    return ImageFont.truetype(path, size)
                except Exception:
                    continue
    return ImageFont.load_default()


# ── Web Mercator & Cartography Helpers ─────────────────────────────────────

def _lat_lng_to_world(lat, lng):
    """Convert Lat/Lng to normalized Web Mercator coordinates [0, 1]."""
    x = (lng + 180.0) / 360.0
    sin_lat = math.sin(math.radians(lat))
    sin_lat = max(-0.9999, min(0.9999, sin_lat))
    y = 0.5 - math.log((1.0 + sin_lat) / (1.0 - sin_lat)) / (4.0 * math.pi)
    return x, y


def _get_bounds_zoom(min_lat, max_lat, min_lng, max_lng, width=640, height=360, padding=0.25):
    """Calculate optimal Google Maps zoom level fitting bounding box."""
    avail_w = width * (1.0 - padding)
    avail_h = height * (1.0 - padding)
    for zoom in range(16, 2, -1):
        scale_factor = 256.0 * (2.0 ** zoom)
        x1, y1 = _lat_lng_to_world(max_lat, min_lng)
        x2, y2 = _lat_lng_to_world(min_lat, max_lng)
        dx = abs(x2 - x1) * scale_factor
        dy = abs(y2 - y1) * scale_factor
        if dx <= avail_w and dy <= avail_h:
            return zoom
    return 4


def _lat_lng_to_pixel(lat, lng, center_lat, center_lng, zoom, width=640, height=360, scale=2):
    """Convert Lat/Lng to pixel (x, y) on Google Static Map canvas."""
    scale_factor = 256.0 * (2.0 ** zoom)
    cx, cy = _lat_lng_to_world(center_lat, center_lng)
    px, py = _lat_lng_to_world(lat, lng)
    x = (px - cx) * scale_factor * scale + (width * scale) / 2.0
    y = (py - cy) * scale_factor * scale + (height * scale) / 2.0
    return x, y


def _fetch_static_map(center_lat, center_lng, zoom, width=640, height=360, scale=2):
    """
    Fetch static terrain map from Google Maps API with disk cache and offline fallback.
    """
    os.makedirs(MAPS_CACHE_DIR, exist_ok=True)
    cache_key = f"map_z{zoom}_{center_lat:.4f}_{center_lng:.4f}_{width}x{height}s{scale}.png"
    cache_path = os.path.join(MAPS_CACHE_DIR, cache_key)

    if os.path.exists(cache_path):
        try:
            return Image.open(cache_path).convert("RGB")
        except Exception:
            pass

    from tools.maps_client import maps_allows
    key = os.getenv("GOOGLE_MAPS_API_KEY") if maps_allows("static") else None
    if key:
        try:
            url = (
                f"https://maps.googleapis.com/maps/api/staticmap"
                f"?center={center_lat:.6f},{center_lng:.6f}"
                f"&zoom={zoom}"
                f"&size={width}x{height}"
                f"&scale={scale}"
                f"&maptype=terrain"
                f"&key={key}"
            )
            resp = requests.get(url, timeout=7)
            if resp.status_code == 200:
                img = Image.open(BytesIO(resp.content)).convert("RGB")
                img.save(cache_path)
                return img
            else:
                print(f"  ⚠️ Static map returned status {resp.status_code}")
        except Exception as ex:
            print(f"  ⚠️ Static map request failed: {ex}")

    # Fallback to stylized dark cartographic canvas
    return _generate_vector_cartographic_background(width * scale, height * scale, center_lat, center_lng, zoom)


def _generate_vector_cartographic_background(width, height, center_lat, center_lng, zoom):
    """Generate handsome deep-navy cartographic background when offline."""
    img = Image.new("RGB", (width, height), color=(0, 22, 55))
    draw = ImageDraw.Draw(img)

    # Subtle vertical gradient
    for y in range(0, height, 4):
        ratio = y / height
        r = int(0 + 10 * ratio)
        g = int(22 + 15 * ratio)
        b = int(55 + 25 * ratio)
        draw.rectangle([0, y, width, y + 4], fill=(r, g, b))

    # Lat/Lng grid lines
    for x in range(0, width, 80):
        draw.line([(x, 0), (x, height)], fill=(0, 48, 100), width=1)
    for y in range(0, height, 80):
        draw.line([(0, y), (width, y)], fill=(0, 48, 100), width=1)

    # Compass windrose in bottom-right
    cx, cy = width - 110, height - 110
    for rad in (25, 55, 90):
        draw.ellipse([cx - rad, cy - rad, cx + rad, cy + rad], outline=(0, 75, 140), width=1)
    draw.line([(cx - 70, cy), (cx + 70, cy)], fill=(0, 95, 170), width=1)
    draw.line([(cx, cy - 70), (cx, cy + 70)], fill=(0, 95, 170), width=1)

    return img


def _get_campervan_sprite(width=42, height=84):
    """
    Render high-resolution top-down VW California campervan sprite with pop-up roof.
    """
    van = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    draw = ImageDraw.Draw(van)

    # Soft drop shadow beneath van
    draw.ellipse([3, 10, width - 3, height - 2], fill=(0, 0, 0, 95))

    # Two-tone body: Reflex Silver & Starlight Blue
    draw.rounded_rectangle(
        [5, 6, width - 5, height - 8],
        radius=9,
        fill=(225, 235, 248, 255),
        outline=(0, 30, 80, 255),
        width=2,
    )

    # Dark side mouldings
    draw.rectangle([4, 25, 6, height - 20], fill=(0, 20, 50, 255))
    draw.rectangle([width - 6, 25, width - 4, height - 20], fill=(0, 20, 50, 255))

    # Pop-up roof panel (California trademark)
    draw.rounded_rectangle(
        [9, 22, width - 9, height - 12],
        radius=5,
        fill=(255, 255, 255, 255),
        outline=(130, 150, 180, 255),
        width=1,
    )
    draw.line([12, 28, width - 12, 28], fill=(180, 195, 215, 255), width=1)
    draw.line([12, 34, width - 12, 34], fill=(180, 195, 215, 255), width=1)

    # Dark tinted windshield
    draw.polygon(
        [(9, 20), (width - 9, 20), (width - 7, 13), (7, 13)],
        fill=(15, 30, 55, 255),
    )

    # Headlights
    draw.ellipse([7, 6, 13, 11], fill=(255, 255, 225, 255))
    draw.ellipse([width - 13, 6, width - 7, 11], fill=(255, 255, 225, 255))

    # VW Front Grille badge
    draw.ellipse(
        [width // 2 - 4, 5, width // 2 + 4, 12],
        fill=(0, 30, 80, 255),
        outline=(255, 255, 255, 255),
        width=1,
    )

    # Side mirrors
    draw.rectangle([1, 15, 5, 20], fill=(0, 30, 80, 255))
    draw.rectangle([width - 5, 15, width - 1, 20], fill=(0, 30, 80, 255))

    return van


# ── Cinematic Slides (Intro, Photo, Outro) ─────────────────────────────────

def _create_cinematic_intro_slide(trip_data, lang="pl", width=1280, height=720):
    """Render cinematic intro title slide with VW branding and Sniffer."""
    trip = trip_data["trip"]
    t = I18N_SUMMARY.get(lang, I18N_SUMMARY["pl"])

    canvas = Image.new("RGB", (width, height), (0, 20, 55))
    draw = ImageDraw.Draw(canvas)

    # Radial ambient glow
    for r in range(450, 0, -20):
        intensity = int(35 * (1.0 - r / 450.0))
        draw.ellipse(
            [width // 2 - r, height // 2 - r, width // 2 + r, height // 2 + r],
            fill=(0, 20 + intensity, 55 + intensity * 2),
        )

    # VW Logo badge
    logo_path = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        "frontend", "vw-logo-2x.png"
    )
    if os.path.exists(logo_path):
        try:
            logo = Image.open(logo_path).convert("RGBA")
            logo.thumbnail((72, 72), Image.Resampling.LANCZOS)
            canvas.paste(logo, (width // 2 - logo.width // 2, 75), logo)
        except Exception:
            pass

    font_title = _get_font(42, bold=True)
    font_sub = _get_font(20)
    font_badge = _get_font(14, bold=True)

    # Brand tag
    draw.text((width // 2, 165), "VOLKSWAGEN CALIFORNIA", fill=(0, 225, 217), font=font_badge, anchor="mm")
    draw.text((width // 2, 195), t.get("recap_title", "FILMOWE PODSUMOWANIE WYPRAWY"), fill=(180, 210, 245), font=_get_font(12, bold=True), anchor="mm")

    # Trip Title
    trip_title = trip.get("title", "Podróż z VW California")
    draw.text((width // 2, 260), trip_title, fill=(255, 255, 255), font=font_title, anchor="mm")

    # Dates
    start_d = trip.get("start_date", "")
    end_d = trip.get("end_date", "")
    dates = f"{start_d}  ->  {end_d}" if start_d and end_d else (start_d or end_d or "")
    if dates:
        draw.text((width // 2, 320), dates, fill=(200, 220, 245), font=font_sub, anchor="mm")

    # Stat pills in the center
    pill_y = 400
    stats = [
        (f"{trip_data['num_days']}", t.get("days", "dni").upper()),
        (f"{int(trip_data['total_driving_km'])} km", t.get("distance", "Dystans").upper()),
        (f"{trip_data['total_driving_hours']} h", t.get("driving_hours", "Jazda").upper()),
        (f"{trip_data['num_photos']}", t.get("photos", "Zdjęcia").upper()),
    ]

    total_w = 4 * 160 + 3 * 20
    start_x = (width - total_w) // 2
    for i, (val, lbl) in enumerate(stats):
        px = start_x + i * 180
        draw.rounded_rectangle([px, pill_y, px + 160, pill_y + 80], radius=14, fill=(0, 14, 38), outline=(0, 120, 220), width=1)
        draw.text((px + 80, pill_y + 28), val, fill=(255, 255, 255), font=_get_font(22, bold=True), anchor="mm")
        draw.text((px + 80, pill_y + 56), lbl, fill=(0, 225, 217), font=_get_font(11, bold=True), anchor="mm")

    # Sniffer avatar & Footer callout
    avatar_path = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        "frontend", "assets", "sniffer-avatar.png"
    )
    if os.path.exists(avatar_path):
        try:
            avatar = Image.open(avatar_path).convert("RGBA")
            avatar.thumbnail((34, 34), Image.Resampling.LANCZOS)
            canvas.paste(avatar, (width // 2 - 200, height - 76), avatar)
        except Exception:
            pass

    draw.text((width // 2 + 10, height - 60), "Travel Memories • Powered by Volkswagen Sniffer", fill=(160, 185, 215), font=_get_font(14, bold=True), anchor="mm")

    return canvas


def _create_cinematic_photo_slide(photo_path, caption="", day_number=1, total_days=3, title="", width=1280, height=720, lang="pl"):
    """Render full-screen photo memory slide with ambient backdrop and glassmorphic card."""
    canvas = Image.new("RGB", (width, height), (0, 14, 38))

    photo_img = _open_photo_image(photo_path)
    if photo_img:
        try:
            # Blurred ambient backdrop
            bg = photo_img.copy()
            bg = bg.resize((width // 4, height // 4), Image.Resampling.BOX)
            bg = bg.resize((width, height), Image.Resampling.BILINEAR)

            darkener = Image.new("RGB", (width, height), (0, 10, 25))
            bg = Image.blend(bg, darkener, 0.65)
            canvas.paste(bg, (0, 0))

            # Foreground photo centered
            fg = photo_img.copy()
            fg.thumbnail((1080, 530), Image.Resampling.LANCZOS)

            fg_x = (width - fg.width) // 2
            fg_y = 65 + (500 - fg.height) // 2

            draw = ImageDraw.Draw(canvas)
            # White frame & drop shadow
            draw.rectangle([fg_x - 4, fg_y - 4, fg_x + fg.width + 4, fg_y + fg.height + 4], fill=(255, 255, 255))
            canvas.paste(fg, (fg_x, fg_y))
        except Exception as ex:
            print(f"  ⚠️ Error embedding photo {photo_path}: {ex}")

    draw = ImageDraw.Draw(canvas)
    t = I18N_SUMMARY.get(lang, I18N_SUMMARY["pl"])

    # Top HUD Badge: [ TRAVEL MEMORY · DZIEŃ X ]
    day_text = f"TRAVEL MEMORY · {t.get('day', 'Dzień').upper()} {day_number} · {title}" if title else f"TRAVEL MEMORY · {t.get('day', 'Dzień').upper()} {day_number}"
    badge_w = 460
    badge_h = 36
    draw.rounded_rectangle([width // 2 - badge_w // 2, 14, width // 2 + badge_w // 2, 14 + badge_h], radius=18, fill=(0, 14, 38), outline=(0, 180, 255), width=1)
    draw.text((width // 2, 32), day_text, fill=(255, 255, 255), font=_get_font(14, bold=True), anchor="mm")

    # Bottom Glassmorphic Card for Caption
    card_w = min(840, width - 120)
    card_h = 68
    card_x = (width - card_w) // 2
    card_y = height - 88

    draw.rounded_rectangle([card_x, card_y, card_x + card_w, card_y + card_h], radius=16, fill=(0, 14, 38), outline=(255, 255, 255), width=1)

    clean_caption = caption or f"{t.get('day', 'Dzień')} {day_number}"
    if len(clean_caption) > 52:
        clean_caption = clean_caption[:49] + "..."

    draw.text((width // 2, card_y + 24), clean_caption, fill=(255, 255, 255), font=_get_font(20, bold=True), anchor="mm")
    draw.text((width // 2, card_y + 48), "VW California Travel Memories", fill=(0, 180, 255), font=_get_font(13), anchor="mm")

    return canvas


def _create_cinematic_outro_slide(trip_data, lang="pl", width=1280, height=720):
    """Render cinematic outro slide with trip totals and VW California motto."""
    trip = trip_data["trip"]
    t = I18N_SUMMARY.get(lang, I18N_SUMMARY["pl"])

    canvas = Image.new("RGB", (width, height), (0, 14, 38))
    draw = ImageDraw.Draw(canvas)

    # Radial ambient glow
    for r in range(450, 0, -25):
        intensity = int(30 * (1.0 - r / 450.0))
        draw.ellipse([width // 2 - r, height // 2 - r, width // 2 + r, height // 2 + r], fill=(0, 14 + intensity, 38 + intensity * 2))

    # Sniffer avatar centered
    avatar_path = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        "frontend", "assets", "sniffer-avatar.png"
    )
    if os.path.exists(avatar_path):
        try:
            avatar = Image.open(avatar_path).convert("RGBA")
            avatar.thumbnail((64, 64), Image.Resampling.LANCZOS)
            canvas.paste(avatar, (width // 2 - avatar.width // 2, 90), avatar)
        except Exception:
            pass

    draw.text((width // 2, 190), t.get("trip_finished", "Wyjazd zakończony!"), fill=(255, 255, 255), font=_get_font(38, bold=True), anchor="mm")
    draw.text((width // 2, 240), trip.get("title", ""), fill=(0, 225, 217), font=_get_font(22), anchor="mm")

    # Big stats summary box
    box_w = 680
    box_h = 160
    box_x = (width - box_w) // 2
    box_y = 290
    draw.rounded_rectangle([box_x, box_y, box_x + box_w, box_y + box_h], radius=20, fill=(0, 20, 50), outline=(255, 255, 255), width=1)

    stats_cols = [
        (f"{trip_data['total_driving_km']} km", t.get("total_distance", "Całkowity dystans")),
        (f"{trip_data['total_driving_hours']} h", t.get("total_drive_time", "Czas za kółkiem")),
        (f"{len(trip_data.get('photos', []))}", t.get("total_photos", "Zdjęć z podróży")),
    ]
    col_w = box_w // 3
    for i, (v, l) in enumerate(stats_cols):
        cx = box_x + i * col_w + col_w // 2
        draw.text((cx, box_y + 55), v, fill=(255, 255, 255), font=_get_font(28, bold=True), anchor="mm")
        draw.text((cx, box_y + 105), l, fill=(0, 225, 217), font=_get_font(12, bold=True), anchor="mm")
        if i < 2:
            draw.line([(box_x + (i + 1) * col_w, box_y + 25), (box_x + (i + 1) * col_w, box_y + box_h - 25)], fill=(0, 45, 95), width=1)

    # Sniffer footer
    draw.text((width // 2, height - 90), t.get("ready_for_adventure", "Gdzie zaprowadzi Cię kolejna droga?"), fill=(255, 255, 255), font=_get_font(18, bold=True), anchor="mm")
    draw.text((width // 2, height - 55), t.get("california_motto", "Volkswagen California · Twój mobilny dom na kółkach"), fill=(140, 165, 195), font=_get_font(13), anchor="mm")

    return canvas


def _create_slide(
    title, subtitle="", body="",
    color_bg=(0, 30, 80), color_text=(255, 255, 255),
    width=1280, height=720,
    image_path=None
):
    """
    Create a single summary slide as a PIL Image (retained for backward compatibility).
    """
    img = Image.new("RGB", (width, height), color=color_bg)
    draw = ImageDraw.Draw(img)

    font_title = _get_font(44, bold=True)
    font_subtitle = _get_font(24)
    font_body = _get_font(20)

    y_pos = height // 4
    draw.text((60, y_pos), title, fill=color_text, font=font_title)

    if subtitle:
        y_pos += 60
        sub_color = tuple(
            min(255, c + 60) if sum(color_bg) < 384 else max(0, c - 60)
            for c in color_text
        )
        draw.text((60, y_pos), subtitle, fill=sub_color, font=font_subtitle)

    if body:
        y_pos += 50
        for line in body.split("\n"):
            draw.text((60, y_pos), line, fill=color_text, font=font_body)
            y_pos += 28

    if image_path and os.path.exists(image_path):
        try:
            overlay = Image.open(image_path).convert("RGB")
            max_size = (500, 500)
            overlay.thumbnail(max_size, Image.Resampling.LANCZOS)
            img_x = width - overlay.width - 60
            img_y = (height - overlay.height) // 2
            draw.rectangle(
                [img_x - 4, img_y - 4, img_x + overlay.width + 4, img_y + overlay.height + 4],
                fill=(255, 255, 255) if sum(color_bg) < 384 else (0, 30, 80)
            )
            img.paste(overlay, (img_x, img_y))
        except Exception as e:
            print(f"  ⚠️ Failed to overlay image {image_path}: {e}")

    watermark = "VW California Trip Planner"
    draw.text((60, height - 40), watermark, fill=(160, 180, 205), font=font_subtitle)

    return img


_PHOTO_PIN_CACHE = {}


def _get_cached_photo_pin(photo_path, count=1, thumb_size=42):
    """
    Generate and cache a miniature photo pin badge with a pointer needle and optional count pill.
    """
    cache_key = (photo_path, count, thumb_size)
    if cache_key in _PHOTO_PIN_CACHE:
        return _PHOTO_PIN_CACHE[cache_key]

    photo_img = _open_photo_image(photo_path)
    if not photo_img:
        return None

    try:
        w, h = photo_img.size
        min_dim = min(w, h)
        cropped = photo_img.crop((
            (w - min_dim) // 2,
            (h - min_dim) // 2,
            (w + min_dim) // 2,
            (h + min_dim) // 2,
        ))
        cropped = cropped.resize((thumb_size, thumb_size), Image.Resampling.LANCZOS)

        pad = 4
        pin_w = thumb_size + pad * 2
        needle_h = 10
        pin_h = thumb_size + pad * 2 + needle_h

        pin_canvas = Image.new("RGBA", (pin_w + 16, pin_h), (0, 0, 0, 0))
        draw = ImageDraw.Draw(pin_canvas)

        cx = pin_canvas.width // 2
        card_x0 = (pin_canvas.width - pin_w) // 2
        card_y0 = 2
        card_x1 = card_x0 + pin_w
        card_y1 = card_y0 + pin_w

        # Pointer needle pointing down
        tip_y = pin_h - 1
        draw.polygon(
            [(cx - 5, card_y1 - 1), (cx + 5, card_y1 - 1), (cx, tip_y)],
            fill=(0, 20, 50, 245),
        )
        draw.line([(cx - 5, card_y1 - 1), (cx, tip_y)], fill=(0, 225, 217, 255), width=1)
        draw.line([(cx + 5, card_y1 - 1), (cx, tip_y)], fill=(0, 225, 217, 255), width=1)

        # Rounded card background
        draw.rounded_rectangle(
            [card_x0, card_y0, card_x1, card_y1],
            radius=8,
            fill=(0, 20, 50, 245),
            outline=(0, 225, 217, 255),
            width=2,
        )

        # Rounded photo mask
        mask = Image.new("L", (thumb_size, thumb_size), 0)
        ImageDraw.Draw(mask).rounded_rectangle([0, 0, thumb_size, thumb_size], radius=6, fill=255)
        pin_canvas.paste(cropped, (card_x0 + pad, card_y0 + pad), mask)
        draw.rounded_rectangle(
            [card_x0 + pad, card_y0 + pad, card_x0 + pad + thumb_size, card_y0 + pad + thumb_size],
            radius=6,
            outline=(255, 255, 255, 220),
            width=1,
        )

        # Optional count badge if multiple photos in cluster
        if count > 1:
            badge_text = f"+{count}"
            font_b = _get_font(10, bold=True)
            badge_w = 20 if count < 10 else 24
            badge_h = 14
            bx0 = card_x1 - 8
            by0 = card_y0 - 4
            bx1 = bx0 + badge_w
            by1 = by0 + badge_h
            draw.rounded_rectangle([bx0, by0, bx1, by1], radius=7, fill=(0, 225, 217, 255), outline=(0, 20, 50, 255), width=1)
            draw.text(((bx0 + bx1) // 2, (by0 + by1) // 2), badge_text, fill=(0, 20, 50), font=font_b, anchor="mm")

        _PHOTO_PIN_CACHE[cache_key] = pin_canvas
        return pin_canvas
    except Exception as ex:
        print(f"  ⚠️ Error generating photo pin thumbnail: {ex}")
        return None


# ── Route Animation & HUD Rendering ────────────────────────────────────────

def _interpolate_polyline_point(points, distances, target_dist):
    """
    Interpolate (lat, lng) and return (lat, lng, seg_idx) along polyline at target_dist meters.
    """
    if not points:
        return 0.0, 0.0, 0
    if target_dist <= 0 or len(points) == 1:
        return points[0][0], points[0][1], 0
    if target_dist >= distances[-1]:
        return points[-1][0], points[-1][1], max(0, len(points) - 2)

    for i in range(1, len(distances)):
        if distances[i] >= target_dist:
            seg_idx = i - 1
            seg_start_d = distances[seg_idx]
            seg_end_d = distances[seg_idx + 1]
            seg_len = seg_end_d - seg_start_d
            local_p = (target_dist - seg_start_d) / seg_len if seg_len > 0 else 0.0
            local_p = max(0.0, min(1.0, local_p))
            lat1, lng1 = points[seg_idx]
            lat2, lng2 = points[seg_idx + 1]
            return lat1 + (lat2 - lat1) * local_p, lng1 + (lng2 - lng1) * local_p, seg_idx

    return points[-1][0], points[-1][1], max(0, len(points) - 2)


def _render_map_frame(
    base_map_img,
    current_points,
    all_points,
    center_lat,
    center_lng,
    zoom,
    day_number,
    total_days,
    schedule_date,
    current_km,
    total_day_km,
    current_hours,
    total_day_hours,
    progress,
    width=1280,
    height=720,
    camping_name=None,
    lang="pl",
    van_sprite=None,
    photo_pins=None,
    heading_angle=None,
):
    """
    Render a single map animation frame with real terrain, glowing route,
    photo pins along the journey, rotated VW California campervan sprite, and live Digital Cockpit HUD.
    """
    img = base_map_img.copy()
    draw = ImageDraw.Draw(img)
    t = I18N_SUMMARY.get(lang, I18N_SUMMARY["pl"])

    # Convert lat/lng to pixel coordinates
    def to_xy(lat, lng):
        return _lat_lng_to_pixel(lat, lng, center_lat, center_lng, zoom, width=width // 2, height=height // 2, scale=2)

    # 1. Full route faint backdrop
    if len(all_points) >= 2:
        back_pixels = [to_xy(p[0], p[1]) for p in all_points]
        draw.line(back_pixels, fill=(0, 45, 95), width=7)

    # 2. Cyan Neon Glowing Route (Up to current progress)
    if len(current_points) >= 2:
        prog_pixels = [to_xy(p[0], p[1]) for p in current_points]
        # Multi-pass neon glow
        draw.line(prog_pixels, fill=(0, 100, 180), width=9)
        draw.line(prog_pixels, fill=(0, 200, 225), width=5)
        draw.line(prog_pixels, fill=(230, 255, 255), width=2)

    # 3. Camping Stop Marker
    if camping_name and len(all_points) >= 1:
        camp_xy = to_xy(all_points[-1][0], all_points[-1][1])
        draw.ellipse([camp_xy[0] - 14, camp_xy[1] - 14, camp_xy[0] + 14, camp_xy[1] + 14], fill=(0, 225, 217), outline=(255, 255, 255), width=2)
        draw.ellipse([camp_xy[0] - 6, camp_xy[1] - 6, camp_xy[0] + 6, camp_xy[1] + 6], fill=(0, 14, 38))

    # 4. Photo Pin Badges on Map Canvas (with thumbnails & count clustering)
    if photo_pins:
        clusters = []
        cluster_threshold = 28.0

        for pin in photo_pins:
            plat = pin.get("lat")
            plng = pin.get("lng")
            if plat is None or plng is None:
                continue
            pxy = to_xy(plat, plng)

            # Check if close to existing cluster
            merged = False
            for cl in clusters:
                cxy = cl["xy"]
                if math.hypot(pxy[0] - cxy[0], pxy[1] - cxy[1]) <= cluster_threshold:
                    cl["photos"].append(pin)
                    merged = True
                    break

            if not merged:
                clusters.append({"xy": pxy, "photos": [pin]})

        for cl in clusters:
            px, py = cl["xy"]
            primary_photo = cl["photos"][0]
            photo_path = primary_photo.get("file_url")
            badge = _get_cached_photo_pin(photo_path, count=len(cl["photos"]))
            if badge:
                bw, bh = badge.size
                cx = bw // 2
                tip_y = bh
                img.paste(badge, (int(px - cx), int(py - tip_y)), badge)
                draw.ellipse([px - 4, py - 4, px + 4, py + 4], fill=(0, 225, 217), outline=(255, 255, 255), width=1)
            else:
                draw.ellipse([px - 8, py - 8, px + 8, py + 8], fill=(0, 20, 50), outline=(0, 225, 217), width=2)
                draw.ellipse([px - 3, py - 3, px + 3, py + 3], fill=(255, 255, 255))

    # 5. VW California Campervan Sprite (rotated by heading)
    if current_points:
        curr_xy = to_xy(current_points[-1][0], current_points[-1][1])

        # Compute heading angle
        if heading_angle is not None:
            angle_deg = heading_angle
        else:
            angle_deg = 0.0
            if len(current_points) >= 2:
                prev_xy = to_xy(current_points[-2][0], current_points[-2][1])
                dx = curr_xy[0] - prev_xy[0]
                dy = curr_xy[1] - prev_xy[1]
                if abs(dx) > 0.1 or abs(dy) > 0.1:
                    angle_deg = math.degrees(math.atan2(dy, dx)) - 90.0

        if van_sprite is None:
            van_sprite = _get_campervan_sprite()

        try:
            rotated_van = van_sprite.rotate(-angle_deg, resample=Image.BICUBIC, expand=True)
            van_x = int(curr_xy[0] - rotated_van.width / 2.0)
            van_y = int(curr_xy[1] - rotated_van.height / 2.0)
            img.paste(rotated_van, (van_x, van_y), rotated_van)
        except Exception:
            draw.ellipse([curr_xy[0] - 12, curr_xy[1] - 12, curr_xy[0] + 12, curr_xy[1] + 12], fill=(255, 200, 0), outline=(255, 255, 255), width=2)

    # 6. Top-Left HUD Badge: [ CALIFORNIA · DZIEŃ X z N ]
    hud_day_text = f"CALIFORNIA · {t.get('day', 'Dzień').upper()} {day_number} / {total_days}"
    date_text = schedule_date or ""

    draw.rounded_rectangle([24, 20, 280, 78], radius=14, fill=(0, 14, 38), outline=(0, 180, 255), width=1)
    draw.text((40, 38), hud_day_text, fill=(255, 255, 255), font=_get_font(15, bold=True))
    if date_text:
        draw.text((40, 58), date_text, fill=(0, 225, 217), font=_get_font(13))

    # 7. Top-Right Digital Cockpit Odometer HUD
    draw.rounded_rectangle([width - 250, 20, width - 24, 78], radius=14, fill=(0, 14, 38), outline=(0, 180, 255), width=1)
    draw.ellipse([width - 236, 44, width - 228, 52], fill=(0, 225, 217))
    draw.text((width - 220, 38), f"{current_km:.1f} / {total_day_km:.1f} km", fill=(255, 255, 255), font=_get_font(15, bold=True))
    draw.ellipse([width - 236, 64, width - 228, 72], fill=(0, 180, 255))
    draw.text((width - 220, 58), f"{current_hours:.1f} / {total_day_hours:.1f} h", fill=(0, 225, 217), font=_get_font(13))

    # 8. Bottom Progress Bar
    bar_w = width - 48
    bar_h = 6
    bar_x = 24
    bar_y = height - 28
    draw.rectangle([bar_x, bar_y, bar_x + bar_w, bar_y + bar_h], fill=(0, 30, 70))
    draw.rectangle([bar_x, bar_y, bar_x + int(bar_w * progress), bar_y + bar_h], fill=(0, 225, 217))

    # Watermark
    draw.text((26, height - 52), "Volkswagen California · Sniffer", fill=(220, 235, 255), font=_get_font(12, bold=True))

    return img


# ── Photo Allocation & Pacing Helpers ─────────────────────────────────────

def _get_photo_slide_duration(total_photos):
    """
    Calculate dynamic slide duration for photo highlights in video recap.
    Keeps total video length engaging and brisk (typically 25-60s).
    """
    if total_photos <= 3:
        return 2.8
    elif total_photos <= 8:
        return 2.2
    elif total_photos <= 15:
        return 1.8
    elif total_photos <= 25:
        return 1.5
    elif total_photos <= 40:
        return 1.1
    else:
        return 0.8


def _partition_photos_by_schedule(photos, schedules):
    """
    Partition photos into a dictionary keyed by day schedule ID.
    If a photo is directly tagged or has day_number, match it.
    If a photo has captured_at date matching the schedule date, match it.
    If a photo has lat/lng, attach it to the geographically closest day route/waypoints.
    Guarantees that every single photo is allocated to a day.
    """
    if not schedules:
        return {}

    assigned = {day["id"]: [] for day in schedules}
    unassigned = []

    for photo in photos:
        matched = False
        p_day_id = photo.get("tagged_day_schedule_id")
        p_day_num = photo.get("day_number")
        p_captured = photo.get("captured_at")
        p_date_str = str(p_captured)[:10] if p_captured else None

        for day in schedules:
            if p_day_id and str(p_day_id) == str(day["id"]):
                assigned[day["id"]].append(photo)
                matched = True
                break
            elif p_day_num is not None and p_day_num == day.get("day_number"):
                assigned[day["id"]].append(photo)
                matched = True
                break
            elif p_date_str and day.get("date") and p_date_str == str(day.get("date"))[:10]:
                assigned[day["id"]].append(photo)
                matched = True
                break

        if not matched:
            unassigned.append(photo)

    # For unassigned photos, find closest day schedule by lat/lng or distribute
    if unassigned and schedules:
        for idx, photo in enumerate(unassigned):
            p_lat = photo.get("lat")
            p_lng = photo.get("lng")
            if p_lat is not None and p_lng is not None:
                best_day_id = schedules[0]["id"]
                min_dist = float("inf")
                for day in schedules:
                    wps = day.get("waypoints") or []
                    for wp in wps:
                        w_lat = wp.get("lat")
                        w_lng = wp.get("lng")
                        if w_lat is not None and w_lng is not None:
                            d = (p_lat - w_lat) ** 2 + (p_lng - w_lng) ** 2
                            if d < min_dist:
                                min_dist = d
                                best_day_id = day["id"]
                assigned[best_day_id].append(photo)
            else:
                assigned[schedules[0]["id"]].append(photo)

    return assigned


# ── Interactive Photo Stop & Pop-up Animation Helpers ─────────────────────

def _project_photo_to_route(photo, points, distances, total_dist):
    """
    Find the closest point along the route polyline for a given photo.
    Returns:
        (best_dist_along_route, best_progress, (pin_lat, pin_lng))
    """
    plat = photo.get("lat")
    plng = photo.get("lng")
    if plat is None or plng is None or len(points) < 2 or total_dist <= 0:
        return (total_dist * 0.98, 0.98, (plat, plng))

    best_dist_along_route = 0.0
    min_geom_dist_sq = float("inf")

    # Segment projection
    for i in range(len(points) - 1):
        lat1, lng1 = points[i]
        lat2, lng2 = points[i + 1]
        seg_dist = distances[i + 1] - distances[i]
        if seg_dist <= 0:
            continue

        cos_mid = math.cos(math.radians((lat1 + lat2) / 2.0))
        dx = (lng2 - lng1) * cos_mid
        dy = lat2 - lat1
        seg_len_sq = dx * dx + dy * dy

        if seg_len_sq <= 1e-12:
            u = 0.0
        else:
            px = (plng - lng1) * cos_mid
            py = plat - lat1
            u = max(0.0, min(1.0, (px * dx + py * dy) / seg_len_sq))

        proj_lat = lat1 + u * (lat2 - lat1)
        proj_lng = lng1 + u * (lng2 - lng1)

        d_lat = (plat - proj_lat) * 111000.0
        d_lng = (plng - proj_lng) * 111000.0 * cos_mid
        geom_dist_sq = d_lat * d_lat + d_lng * d_lng

        if geom_dist_sq < min_geom_dist_sq:
            min_geom_dist_sq = geom_dist_sq
            best_dist_along_route = distances[i] + u * seg_dist

    best_progress = max(0.0, min(1.0, best_dist_along_route / total_dist))
    return (best_dist_along_route, best_progress, (plat, plng))


def _render_pin_pulse_frame(base_frame, pin_xy, pulse_ratio):
    """
    Render a glowing cyan pulse circle expanding outward around the pin coordinate.
    pulse_ratio: float from 0.0 to 1.0
    """
    canvas = base_frame.copy().convert("RGBA")
    overlay = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)

    px, py = int(pin_xy[0]), int(pin_xy[1])
    r = int(10 + 26 * pulse_ratio)
    alpha = max(0, min(255, int(230 * (1.0 - pulse_ratio))))

    # Outer pulse ring
    draw.ellipse([px - r, py - r, px + r, py + r], outline=(0, 225, 217, alpha), width=3)

    # Inner subtle glow
    inner_r = max(4, r - 8)
    draw.ellipse([px - inner_r, py - inner_r, px + inner_r, py + inner_r], fill=(0, 225, 217, alpha // 4))

    canvas = Image.alpha_composite(canvas, overlay)
    return canvas.convert("RGB")


def _render_photo_popup_frame(
    base_frame,
    photo_path,
    pin_xy,
    progress,
    day_number=1,
    schedule_date=None,
    caption="",
    lang="pl",
    reverse=False,
):
    """
    Render dynamic pop-up zoom frame of a photo memory card over the map:
    - Map is dimmed with dark glass vignette
    - Card interpolates from pin coordinate (pin_xy) to center screen (640, 360)
    - Card scales from ~0.12 to 1.0 with rounded corners, cyan glow, photo, and title badge.
    reverse: True when animating backwards (from center back into pin).
    """
    canvas = base_frame.copy().convert("RGBA")
    w, h = canvas.size

    # Nonlinear easing
    if reverse:
        ease = max(0.0, min(1.0, 1.0 - progress))
        ease = ease * ease
    else:
        ease = max(0.0, min(1.0, progress))
        ease = math.sin(ease * math.pi / 2.0)

    # 1. Dark ambient vignette overlay over the map
    dim_alpha = max(0, min(220, int(185 * ease)))
    if dim_alpha > 0:
        darkener = Image.new("RGBA", (w, h), (0, 14, 38, dim_alpha))
        canvas = Image.alpha_composite(canvas, darkener)

    # 2. Origin and Target centers
    pin_x = max(80, min(w - 80, int(pin_xy[0])))
    pin_y = max(60, min(h - 60, int(pin_xy[1])))
    target_cx = w // 2
    target_cy = h // 2

    cur_cx = int(pin_x + (target_cx - pin_x) * ease)
    cur_cy = int(pin_y + (target_cy - pin_y) * ease)

    # 3. Card dimensions
    scale = 0.12 + 0.88 * ease
    card_max_w = 980
    card_max_h = 570

    cw = max(40, int(card_max_w * scale))
    ch = max(30, int(card_max_h * scale))

    x1 = cur_cx - cw // 2
    y1 = cur_cy - ch // 2
    x2 = x1 + cw
    y2 = y1 + ch

    card_overlay = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    c_draw = ImageDraw.Draw(card_overlay)

    # Drop shadow
    shadow_pad = max(2, int(8 * scale))
    c_draw.rounded_rectangle(
        [x1 - shadow_pad, y1 - shadow_pad, x2 + shadow_pad, y2 + shadow_pad],
        radius=max(4, int(20 * scale)),
        fill=(0, 0, 0, int(130 * ease)),
    )

    # Card background and cyan border
    card_radius = max(6, int(18 * scale))
    border_w = max(1, int(3 * scale))
    c_draw.rounded_rectangle(
        [x1, y1, x2, y2],
        radius=card_radius,
        fill=(0, 14, 38, int(245 * ease)),
        outline=(0, 225, 217, int(255 * ease)),
        width=border_w,
    )

    # 4. Embedded Photo Thumbnail
    photo_img = _open_photo_image(photo_path)
    if photo_img and cw > 60 and ch > 50:
        top_bar = int(48 * scale)
        bot_bar = int(58 * scale)
        pad_x = int(18 * scale)

        avail_w = max(20, cw - pad_x * 2)
        avail_h = max(20, ch - top_bar - bot_bar)

        thumb = photo_img.copy()
        thumb.thumbnail((avail_w, avail_h), Image.Resampling.BILINEAR)

        tx = x1 + (cw - thumb.width) // 2
        ty = y1 + top_bar + (avail_h - thumb.height) // 2

        # White border around the photo
        c_draw.rectangle(
            [tx - 2, ty - 2, tx + thumb.width + 1, ty + thumb.height + 1],
            fill=(255, 255, 255, int(230 * ease)),
        )

        canvas = Image.alpha_composite(canvas, card_overlay)
        canvas.paste(thumb, (tx, ty))
        card_overlay = Image.new("RGBA", (w, h), (0, 0, 0, 0))
        c_draw = ImageDraw.Draw(card_overlay)

    # 5. Header and Footer text (when card is sufficiently large)
    t = I18N_SUMMARY.get(lang, I18N_SUMMARY["pl"])
    if scale > 0.45:
        # Header Badge
        header_text = f"CALIFORNIA MEMORY · {t.get('day', 'Dzień').upper()} {day_number}"
        if schedule_date:
            header_text += f" · {schedule_date}"
        font_header = _get_font(max(10, int(15 * scale)), bold=True)
        c_draw.text((cur_cx, y1 + int(24 * scale)), header_text, fill=(0, 225, 217, int(255 * ease)), font=font_header, anchor="mm")

    if scale > 0.55:
        # Footer Caption
        caption_clean = caption or f"{t.get('day', 'Dzień')} {day_number}"
        if len(caption_clean) > 48:
            caption_clean = caption_clean[:45] + "..."
        font_cap = _get_font(max(12, int(18 * scale)), bold=True)
        c_draw.text((cur_cx, y2 - int(34 * scale)), caption_clean, fill=(255, 255, 255, int(255 * ease)), font=font_cap, anchor="mm")

        # Subtle sub-caption
        font_sub = _get_font(max(9, int(12 * scale)))
        c_draw.text((cur_cx, y2 - int(16 * scale)), "Volkswagen California · Travel Memory", fill=(0, 180, 255, int(200 * ease)), font=font_sub, anchor="mm")

    canvas = Image.alpha_composite(canvas, card_overlay)
    return canvas.convert("RGB")


# ── Full Summary Generation Engine ─────────────────────────────────────────

def generate_summary(
    trip_id,
    format="image_slideshow",
    include_map_animation=True,
    include_photos=True,
    music_track=None,
    lang="pl",
):
    """
    Generate a visual trip summary export (video, slideshow, or PDF).
    """
    trip_data = get_trip_summary(trip_id)
    if trip_data["status"] != "success":
        return trip_data

    # Deduplicate and include all photos upfront so all modes share the complete photo set
    all_photos = trip_data.get("photos", [])
    if all_photos:
        photo_map = {}
        for p in all_photos:
            f_url = p.get("file_url")
            if not f_url:
                continue
            # Keep latest or one with lat/lng
            if f_url not in photo_map or (p.get("lat") is not None and photo_map[f_url].get("lat") is None):
                photo_map[f_url] = p
        deduped = list(photo_map.values())
        trip_data["photos"] = deduped
        trip_data["num_photos"] = len(deduped)

    os.makedirs(OUTPUT_DIR, exist_ok=True)

    if format == "image_slideshow":
        result = _generate_slideshow(trip_data, include_map_animation, lang=lang)
    elif format == "pdf":
        result = _generate_pdf_report(trip_data, include_photos, lang=lang)
    elif format == "video":
        result = _generate_video(trip_data, music_track=music_track, lang=lang)
    else:
        return {
            "status": "error",
            "message": f"Unsupported format: '{format}'. Use: image_slideshow, pdf, or video.",
        }

    if result["status"] != "success":
        return result

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


def _generate_slideshow(trip_data, include_map_animation=True, lang="pl"):
    """
    Generate curated high-resolution highlight slides for the web slideshow view.
    """
    trip = trip_data["trip"]
    schedules = trip_data["daily_schedules"]
    all_photos = trip_data.get("photos", [])
    photos_by_day = _partition_photos_by_schedule(all_photos, schedules)
    t = I18N_SUMMARY.get(lang, I18N_SUMMARY["pl"])

    slides = []

    # Slide 1: Intro
    intro_slide = _create_cinematic_intro_slide(trip_data, lang=lang)
    slides.append(intro_slide)

    van_sprite = _get_campervan_sprite()

    # Day Highlight Slides & Photo Memories
    for day in schedules:
        day_num = day["day_number"]
        total_days = len(schedules)
        route_polyline = day.get("route_polyline")
        day_photos = photos_by_day.get(day["id"], [])

        # Render Map Route Overview if polyline exists
        if route_polyline:
            try:
                decoded = googlemaps.convert.decode_polyline(route_polyline)
                points = [(p["lat"], p["lng"]) for p in decoded]
                if len(points) >= 2:
                    lats = [p[0] for p in points]
                    lngs = [p[1] for p in points]
                    center_lat = (min(lats) + max(lats)) / 2.0
                    center_lng = (min(lngs) + max(lngs)) / 2.0
                    zoom = _get_bounds_zoom(min(lats), max(lats), min(lngs), max(lngs))

                    base_map = _fetch_static_map(center_lat, center_lng, zoom)
                    route_slide = _render_map_frame(
                        base_map_img=base_map,
                        current_points=points,
                        all_points=points,
                        center_lat=center_lat,
                        center_lng=center_lng,
                        zoom=zoom,
                        day_number=day_num,
                        total_days=total_days,
                        schedule_date=day.get("date"),
                        current_km=day.get("driving_km", 0),
                        total_day_km=day.get("driving_km", 0),
                        current_hours=day.get("driving_hours", 0),
                        total_day_hours=day.get("driving_hours", 0),
                        progress=1.0,
                        camping_name=day.get("camping_name"),
                        lang=lang,
                        van_sprite=van_sprite,
                        photo_pins=day_photos,
                    )
                    slides.append(route_slide)
            except Exception as ex:
                print(f"  ⚠️ Error generating map slide for day {day_num}: {ex}")

        # Photos for this day
        for photo in day_photos:
            photo_path = photo.get("file_url")
            if photo_path and os.path.exists(photo_path):
                photo_slide = _create_cinematic_photo_slide(
                    photo_path=photo_path,
                    caption=photo.get("caption") or photo.get("filename"),
                    day_number=day_num,
                    total_days=total_days,
                    title=trip.get("title", ""),
                    lang=lang,
                )
                slides.append(photo_slide)

    # Final Outro Slide
    outro_slide = _create_cinematic_outro_slide(trip_data, lang=lang)
    slides.append(outro_slide)

    # Save slides to disk
    slide_paths = []
    trip_slug = trip["id"][:8]
    for i, slide in enumerate(slides):
        path = os.path.join(OUTPUT_DIR, f"summary_{trip_slug}_slide_{i + 1}.png")
        slide.save(path)
        slide_paths.append(path)

    return {
        "status": "success",
        "file_url": slide_paths[0] if slide_paths else "",
        "all_slides": slide_paths,
        "slide_count": len(slides),
    }


def _generate_video(trip_data, music_track=None, lang="pl"):
    """
    Generate an engaging MP4 video with smooth 25 FPS map animation,
    campervan travel flight, photo highlights, and looped soundtrack.
    """
    trip = trip_data["trip"]
    schedules = trip_data["daily_schedules"]
    all_photos = trip_data.get("photos", [])
    photos_by_day = _partition_photos_by_schedule(all_photos, schedules)
    photo_duration = _get_photo_slide_duration(len(all_photos))
    trip_slug = trip["id"][:8]

    video_items = []  # List of tuples: (file_path, duration_seconds)
    frame_counter = 0

    # 1. Cinematic Intro Slide (2.5s)
    intro_slide = _create_cinematic_intro_slide(trip_data, lang=lang)
    intro_path = os.path.join(OUTPUT_DIR, f"vid_{trip_slug}_intro.png")
    intro_slide.save(intro_path)
    video_items.append((intro_path, 2.5))

    van_sprite = _get_campervan_sprite()

    # 2. Day-by-Day Sequences
    for day in schedules:
        day_num = day["day_number"]
        total_days = len(schedules)
        route_polyline = day.get("route_polyline")
        day_photos = photos_by_day.get(day["id"], [])

        if route_polyline:
            try:
                decoded = googlemaps.convert.decode_polyline(route_polyline)
                points = [(p["lat"], p["lng"]) for p in decoded]
                if len(points) >= 2:
                    lats = [p[0] for p in points]
                    lngs = [p[1] for p in points]
                    center_lat = (min(lats) + max(lats)) / 2.0
                    center_lng = (min(lngs) + max(lngs)) / 2.0
                    zoom = _get_bounds_zoom(min(lats), max(lats), min(lngs), max(lngs))

                    base_map = _fetch_static_map(center_lat, center_lng, zoom)

                    # Compute distances along polyline
                    def haversine(lat1, lng1, lat2, lng2):
                        R = 6371000.0
                        dlat = math.radians(lat2 - lat1)
                        dlng = math.radians(lng2 - lng1)
                        a = math.sin(dlat / 2.0) ** 2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlng / 2.0) ** 2
                        c = 2.0 * math.atan2(math.sqrt(a), math.sqrt(1.0 - a))
                        return R * c

                    distances = [0.0]
                    total_dist = 0.0
                    for i in range(1, len(points)):
                        d = haversine(points[i - 1][0], points[i - 1][1], points[i][0], points[i][1])
                        total_dist += d
                        distances.append(total_dist)

                    total_day_km = day.get("driving_km", total_dist / 1000.0)
                    total_day_h = day.get("driving_hours", total_day_km / 70.0)

                    smoothed_heading = None
                    last_map_frame = None

                    # ── Map Photos to Stops Along the Route ───────────────
                    photo_stop_items = []
                    for photo in day_photos:
                        d_m, prog, pin_coords = _project_photo_to_route(photo, points, distances, total_dist)
                        photo_stop_items.append((prog, d_m, pin_coords, photo))

                    # Sort chronologically / geographically along route
                    photo_stop_items.sort(key=lambda item: item[0])

                    # Cluster photos within 2.5% of route into unified stops
                    stops = []
                    for prog, d_m, pin_coords, photo in photo_stop_items:
                        if stops and abs(prog - stops[-1]["progress"]) < 0.025:
                            stops[-1]["photos"].append(photo)
                        else:
                            stops.append({
                                "progress": prog,
                                "dist_m": d_m,
                                "pin_coords": pin_coords,
                                "photos": [photo],
                            })

                    # Build milestones: (start_prog, end_prog, stop_or_none)
                    milestones = []
                    curr_p = 0.0
                    for s in stops:
                        target_p = max(curr_p, min(1.0, s["progress"]))
                        milestones.append((curr_p, target_p, s))
                        curr_p = target_p

                    if curr_p < 1.0 or not milestones:
                        milestones.append((curr_p, 1.0, None))

                    # Iterate over driving milestones
                    for seg_idx, (p_start, p_end, stop_data) in enumerate(milestones):
                        delta_p = p_end - p_start

                        # Determine number of frames for driving segment
                        if delta_p > 0.001:
                            seg_frames = max(6, int(round(ANIMATION_FRAMES_PER_DAY * delta_p)))
                        else:
                            seg_frames = 1 if seg_idx == 0 else 0

                        for f_step in range(seg_frames):
                            if seg_frames > 0:
                                progress = p_start + ((f_step + 1) / float(seg_frames)) * delta_p
                            else:
                                progress = p_end
                            progress = max(0.0, min(1.0, progress))
                            target_dist = total_dist * progress

                            cur_lat, cur_lng, pt_idx = _interpolate_polyline_point(points, distances, target_dist)
                            draw_pts = points[:pt_idx + 1] + [(cur_lat, cur_lng)]

                            # Continuous lookahead along polyline (~600m to 4500m ahead)
                            lookahead_meters = max(600.0, min(4500.0, total_dist * 0.04))
                            ahead_dist = min(total_dist, target_dist + lookahead_meters)
                            ahead_lat, ahead_lng, _ = _interpolate_polyline_point(points, distances, ahead_dist)

                            # Screen vector heading
                            curr_xy = _lat_lng_to_pixel(cur_lat, cur_lng, center_lat, center_lng, zoom, width=640, height=360, scale=2)
                            ahead_xy = _lat_lng_to_pixel(ahead_lat, ahead_lng, center_lat, center_lng, zoom, width=640, height=360, scale=2)
                            dx = ahead_xy[0] - curr_xy[0]
                            dy = ahead_xy[1] - curr_xy[1]

                            if math.hypot(dx, dy) > 0.4:
                                raw_angle = math.degrees(math.atan2(dy, dx)) - 90.0
                            else:
                                raw_angle = smoothed_heading if smoothed_heading is not None else 0.0

                            if smoothed_heading is None:
                                smoothed_heading = raw_angle
                            else:
                                diff = (raw_angle - smoothed_heading + 180.0) % 360.0 - 180.0
                                smoothed_heading = (smoothed_heading + diff * 0.22) % 360.0

                            curr_km = total_day_km * progress
                            curr_h = total_day_h * progress

                            frame_img = _render_map_frame(
                                base_map_img=base_map,
                                current_points=draw_pts,
                                all_points=points,
                                center_lat=center_lat,
                                center_lng=center_lng,
                                zoom=zoom,
                                day_number=day_num,
                                total_days=total_days,
                                schedule_date=day.get("date"),
                                current_km=curr_km,
                                total_day_km=total_day_km,
                                current_hours=curr_h,
                                total_day_hours=total_day_h,
                                progress=progress,
                                camping_name=day.get("camping_name"),
                                lang=lang,
                                van_sprite=van_sprite,
                                photo_pins=day_photos,
                                heading_angle=smoothed_heading,
                            )

                            last_map_frame = frame_img
                            frame_counter += 1
                            f_path = os.path.join(OUTPUT_DIR, f"vid_{trip_slug}_d{day_num}_{frame_counter:04d}.png")
                            frame_img.save(f_path)
                            video_items.append((f_path, 0.04))  # 25 FPS

                        # ── Van Arrived at Photo Stop! ────────────────────
                        if stop_data and stop_data.get("photos") and last_map_frame:
                            stop_photos = stop_data["photos"]
                            plat, plng = stop_data.get("pin_coords", (None, None))
                            if plat is not None and plng is not None:
                                pin_xy = _lat_lng_to_pixel(plat, plng, center_lat, center_lng, zoom, width=640, height=360, scale=2)
                            else:
                                pin_xy = _lat_lng_to_pixel(cur_lat, cur_lng, center_lat, center_lng, zoom, width=640, height=360, scale=2)

                            # 1. Moment of Pause & Pin Pulse (4 frames = 0.16s)
                            for pulse_idx in range(4):
                                pulse_ratio = (pulse_idx + 1) / 4.0
                                pulse_frame = _render_pin_pulse_frame(last_map_frame, pin_xy, pulse_ratio)
                                frame_counter += 1
                                p_path = os.path.join(OUTPUT_DIR, f"vid_{trip_slug}_d{day_num}_pulse_{frame_counter:04d}.png")
                                pulse_frame.save(p_path)
                                video_items.append((p_path, 0.04))

                            # 2. For each photo at this stop: reveal, hold, and return
                            for p_sub_idx, photo in enumerate(stop_photos):
                                p_file = photo.get("file_url")
                                p_cap = photo.get("caption") or photo.get("filename")

                                # A. Pop-up Zoom-in Animation (8 frames = 0.32s)
                                for pop_i in range(8):
                                    pop_prog = (pop_i + 1) / 8.0
                                    pop_frame = _render_photo_popup_frame(
                                        base_frame=last_map_frame,
                                        photo_path=p_file,
                                        pin_xy=pin_xy,
                                        progress=pop_prog,
                                        day_number=day_num,
                                        schedule_date=day.get("date"),
                                        caption=p_cap,
                                        lang=lang,
                                        reverse=False,
                                    )
                                    frame_counter += 1
                                    pop_path = os.path.join(OUTPUT_DIR, f"vid_{trip_slug}_d{day_num}_pop_{frame_counter:04d}.png")
                                    pop_frame.save(pop_path)
                                    video_items.append((pop_path, 0.04))

                                # B. Full Cinematic Photo Slide Hold
                                p_slide = _create_cinematic_photo_slide(
                                    photo_path=p_file,
                                    caption=p_cap,
                                    day_number=day_num,
                                    total_days=total_days,
                                    title=trip.get("title", ""),
                                    lang=lang,
                                )
                                frame_counter += 1
                                p_slide_path = os.path.join(OUTPUT_DIR, f"vid_{trip_slug}_d{day_num}_slide_{frame_counter:04d}.png")
                                p_slide.save(p_slide_path)
                                video_items.append((p_slide_path, photo_duration))

                                # C. Pop-down Zoom-out Animation Back to Map (6 frames = 0.24s)
                                for ret_i in range(6):
                                    ret_prog = (ret_i + 1) / 6.0
                                    ret_frame = _render_photo_popup_frame(
                                        base_frame=last_map_frame,
                                        photo_path=p_file,
                                        pin_xy=pin_xy,
                                        progress=ret_prog,
                                        day_number=day_num,
                                        schedule_date=day.get("date"),
                                        caption=p_cap,
                                        lang=lang,
                                        reverse=True,
                                    )
                                    frame_counter += 1
                                    ret_path = os.path.join(OUTPUT_DIR, f"vid_{trip_slug}_d{day_num}_ret_{frame_counter:04d}.png")
                                    ret_frame.save(ret_path)
                                    video_items.append((ret_path, 0.04))

                            # 3. Short 2-frame breath on the map before continuing driving
                            if last_map_frame:
                                frame_counter += 1
                                pause_path = os.path.join(OUTPUT_DIR, f"vid_{trip_slug}_d{day_num}_pause_{frame_counter:04d}.png")
                                last_map_frame.save(pause_path)
                                video_items.append((pause_path, 0.08))

            except Exception as ex:
                print(f"  ⚠️ Error generating video animation frames for day {day_num}: {ex}")

        else:
            # Fallback if no polyline: show photo slides directly
            for p_idx, photo in enumerate(day_photos):
                photo_path = photo.get("file_url")
                if photo_path and os.path.exists(photo_path):
                    p_slide = _create_cinematic_photo_slide(
                        photo_path=photo_path,
                        caption=photo.get("caption") or photo.get("filename"),
                        day_number=day_num,
                        total_days=total_days,
                        title=trip.get("title", ""),
                        lang=lang,
                    )
                    p_slide_path = os.path.join(OUTPUT_DIR, f"vid_{trip_slug}_fallback_p_d{day_num}_{p_idx}.png")
                    p_slide.save(p_slide_path)
                    video_items.append((p_slide_path, photo_duration))

    # 3. Cinematic Outro Slide (3.0s)
    outro_slide = _create_cinematic_outro_slide(trip_data, lang=lang)
    outro_path = os.path.join(OUTPUT_DIR, f"vid_{trip_slug}_outro.png")
    outro_slide.save(outro_path)
    video_items.append((outro_path, 3.0))

    if not video_items:
        return {"status": "error", "message": "No frames or slides generated for video."}

    # Write concat demuxer list
    list_file_path = os.path.join(OUTPUT_DIR, f"slides_list_{trip_slug}.txt")
    output_mp4 = os.path.join(OUTPUT_DIR, f"summary_{trip_slug}.mp4")

    try:
        with open(list_file_path, "w") as f:
            for item_path, dur in video_items:
                f.write(f"file '{os.path.abspath(item_path)}'\n")
                f.write(f"duration {dur:.4f}\n")
            # Repeat last file without duration for demuxer termination
            f.write(f"file '{os.path.abspath(video_items[-1][0])}'\n")

        # Build FFmpeg command
        cmd = [
            "ffmpeg", "-y",
            "-f", "concat",
            "-safe", "0",
            "-i", list_file_path,
        ]

        music_path = None
        if music_track and music_track != "none":
            music_path = _resolve_music_track(music_track)
            if music_path and os.path.exists(music_path):
                cmd.extend([
                    "-stream_loop", "-1",
                    "-i", music_path,
                ])

        cmd.extend(["-vf", "format=yuv420p"])

        if music_path and os.path.exists(music_path):
            cmd.extend(["-filter:a", "volume=0.25", "-shortest"])

        cmd.append(output_mp4)

        proc = subprocess.run(cmd, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

        return {
            "status": "success",
            "file_url": output_mp4,
        }

    except subprocess.CalledProcessError as e:
        err_msg = e.stderr.decode("utf-8", errors="ignore") if e.stderr else str(e)
        return {"status": "error", "message": f"FFmpeg failed: {err_msg}"}
    except Exception as e:
        return {"status": "error", "message": f"Video generation failed: {str(e)}"}


# ── PDF Report Generator (ReportLab) ───────────────────────────────────────

def _generate_pdf_report(trip_data, include_photos=True, lang="pl"):
    """
    Generate an executive PDF report using ReportLab.
    """
    trip = trip_data["trip"]
    schedules = trip_data["daily_schedules"]
    photos = trip_data["photos"]
    trip_slug = trip["id"][:8]
    t = I18N_SUMMARY.get(lang, I18N_SUMMARY["pl"])

    pdf_path = os.path.join(OUTPUT_DIR, f"report_{trip_slug}.pdf")

    doc = SimpleDocTemplate(
        pdf_path,
        pagesize=A4,
        rightMargin=2 * cm,
        leftMargin=2 * cm,
        topMargin=2 * cm,
        bottomMargin=2 * cm,
    )

    VW_DARK_BLUE = HexColor("#001E50")
    VW_MEDIUM_BLUE = HexColor("#003D8F")
    VW_GOLD = HexColor("#FFB800")
    WHITE = white
    LIGHT_GRAY = HexColor("#F4F6F9")
    DARK_GRAY = HexColor("#333333")

    styles = getSampleStyleSheet()

    title_style = ParagraphStyle(
        "VWTitle",
        parent=styles["Title"],
        fontName="Helvetica-Bold",
        fontSize=28,
        textColor=VW_DARK_BLUE,
        spaceAfter=6,
        alignment=TA_CENTER,
    )

    subtitle_style = ParagraphStyle(
        "VWSubtitle",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=16,
        textColor=VW_MEDIUM_BLUE,
        spaceAfter=12,
        alignment=TA_CENTER,
    )

    heading_style = ParagraphStyle(
        "VWHeading",
        parent=styles["Heading1"],
        fontName="Helvetica-Bold",
        fontSize=18,
        textColor=VW_DARK_BLUE,
        spaceBefore=18,
        spaceAfter=10,
    )

    subheading_style = ParagraphStyle(
        "VWSubHeading",
        parent=styles["Heading2"],
        fontName="Helvetica-Bold",
        fontSize=14,
        textColor=VW_MEDIUM_BLUE,
        spaceBefore=12,
        spaceAfter=6,
    )

    body_style = ParagraphStyle(
        "VWBody",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=11,
        textColor=DARK_GRAY,
        spaceAfter=6,
        leading=15,
    )

    small_style = ParagraphStyle(
        "VWSmall",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=9,
        textColor=HexColor("#666666"),
        spaceAfter=4,
        leading=12,
    )

    stat_label_style = ParagraphStyle(
        "VWStatLabel",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=10,
        textColor=HexColor("#666666"),
        alignment=TA_CENTER,
    )

    stat_value_style = ParagraphStyle(
        "VWStatValue",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=24,
        textColor=VW_DARK_BLUE,
        alignment=TA_CENTER,
    )

    story = []

    # PAGE 1: TITLE
    story.append(Spacer(1, 4 * cm))
    story.append(Paragraph(t["brand_title"], ParagraphStyle(
        "Brand", parent=styles["Normal"], fontName="Helvetica-Bold",
        fontSize=14, textColor=VW_MEDIUM_BLUE, alignment=TA_CENTER
    )))
    story.append(Spacer(1, 1 * cm))
    story.append(Paragraph(trip["title"], title_style))
    story.append(Spacer(1, 0.5 * cm))

    start_date = trip.get("start_date", "")
    end_date = trip.get("end_date", "")
    if start_date and end_date:
        date_text = f"{start_date} → {end_date}"
    elif start_date:
        date_text = t["from_date"].format(date=start_date)
    elif end_date:
        date_text = t["until_date"].format(date=end_date)
    else:
        date_text = t["no_dates"]
    story.append(Paragraph(date_text, subtitle_style))
    story.append(Spacer(1, 2 * cm))

    story.append(HRFlowable(width="60%", thickness=2, color=VW_GOLD, spaceAfter=2 * cm))

    stats_data = [
        [
            Paragraph(f"{trip_data['total_driving_km']:.0f}", stat_value_style),
            Paragraph(f"{trip_data['total_driving_hours']:.1f}", stat_value_style),
            Paragraph(f"{trip_data['num_days']}", stat_value_style),
            Paragraph(f"{trip_data['num_photos']}", stat_value_style),
        ],
        [
            Paragraph(t["total_km"], stat_label_style),
            Paragraph(t["driving_hours"], stat_label_style),
            Paragraph(t["days"].capitalize(), stat_label_style),
            Paragraph(t["photos"], stat_label_style),
        ],
    ]
    stats_table = Table(stats_data, colWidths=[4.5 * cm] * 4)
    stats_table.setStyle(TableStyle([
        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, 0), 4),
        ("BOTTOMPADDING", (0, 1), (-1, 1), 4),
    ]))
    story.append(stats_table)
    story.append(PageBreak())

    # PAGE 2: STATISTICS SUMMARY
    story.append(Paragraph(t["trip_statistics"], heading_style))
    story.append(HRFlowable(width="100%", thickness=1, color=VW_MEDIUM_BLUE, spaceAfter=12))

    summary_data = [
        [t["metric"], t["value"]],
        [t["total_dist_label"], f"{trip_data['total_driving_km']:.1f} km"],
        [t["total_drive_time"], f"{trip_data['total_driving_hours']:.1f} {t['hours_unit']}"],
        [t["num_days_label"], str(trip_data["num_days"])],
        [t["total_photos"], str(trip_data["num_photos"])],
        [t["avg_km_day"], f"{trip_data['total_driving_km'] / max(trip_data['num_days'], 1):.1f} km"],
        [t["avg_hours_day"], f"{trip_data['total_driving_hours'] / max(trip_data['num_days'], 1):.1f} {t['hours_unit']}"],
    ]
    summary_table = Table(summary_data, colWidths=[8 * cm, 8 * cm])
    summary_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), VW_DARK_BLUE),
        ("TEXTCOLOR", (0, 0), (-1, 0), WHITE),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, 0), 12),
        ("GRID", (0, 0), (-1, -1), 0.5, HexColor("#DDDDDD")),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [WHITE, LIGHT_GRAY]),
        ("TOPPADDING", (0, 0), (-1, -1), 8),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
        ("LEFTPADDING", (0, 0), (-1, -1), 12),
        ("RIGHTPADDING", (0, 0), (-1, -1), 12),
    ]))
    story.append(summary_table)
    story.append(PageBreak())

    # PAGE 3: DAILY ITINERARY
    story.append(Paragraph(t["daily_itinerary"], heading_style))
    story.append(HRFlowable(width="100%", thickness=1, color=VW_MEDIUM_BLUE, spaceAfter=12))

    for day in schedules:
        day_title = f"{t['day']} {day['day_number']}"
        if day.get("date"):
            day_title += f" — {day['date']}"
        story.append(Paragraph(day_title, subheading_style))

        waypoint_labels = [
            wp.get("label", "Unknown")
            for wp in day.get("waypoints", [])
            if isinstance(wp, dict)
        ]
        if waypoint_labels:
            route_text = " → ".join(waypoint_labels)
            story.append(Paragraph(f"<b>{t['route_label']}:</b> {route_text}", body_style))

        stats_text = f"<b>{t['drive']}:</b> {day['driving_hours']}h · <b>{t['distance']}:</b> {day['driving_km']}km"
        story.append(Paragraph(stats_text, body_style))

        if day.get("camping_name"):
            story.append(Paragraph(f"<b>{t['camping_label']}:</b> {day['camping_name']}", body_style))

        story.append(Spacer(1, 8))

    doc.build(story)

    return {
        "status": "success",
        "file_url": pdf_path,
    }


# ── Audio & Persistence Helpers ────────────────────────────────────────────

def _resolve_music_track(music_track):
    """
    Resolve music track path from Audius streaming cache, tools, or frontend assets.
    """
    if not music_track or music_track == "none":
        return None

    # Check for Audius streaming identifier or URL
    if music_track.startswith("audius:") or "audius" in music_track:
        try:
            from tools import audius_service
            cached_track = audius_service.download_and_cache_track(music_track)
            if cached_track and os.path.exists(cached_track):
                print(f"  🎵 Using Audius stream track: {cached_track}")
                return cached_track
        except Exception as e:
            print(f"  ⚠️ Failed to resolve Audius track '{music_track}': {e}")

    if os.path.isabs(music_track) and os.path.exists(music_track):
        return music_track

    clean_name = music_track.split("/")[-1]
    if not clean_name.endswith(".mp3") and not clean_name.endswith(".wav"):
        clean_name += ".mp3"

    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    candidates = [
        os.path.join(project_root, "tools", "assets", "audio", clean_name),
        os.path.join(project_root, "frontend", "assets", "audio", clean_name),
        os.path.join(OUTPUT_DIR, music_track),
        os.path.join(os.getcwd(), music_track),
    ]
    for cand in candidates:
        if os.path.exists(cand):
            return cand

    # If it was an unknown or failed Audius track, fallback to vanlife_chill
    fallback = os.path.join(project_root, "frontend", "assets", "audio", "vanlife_chill.mp3")
    if os.path.exists(fallback):
        print(f"  ℹ️ Falling back to default audio: {fallback}")
        return fallback

    return None


def _download_image(url):
    """Download an image from a URL and save it to a temporary file."""
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
        print(f"  ⚠️ Failed to download image {url}: {e}")
    return None


def _persist_summary(
    summary_id, trip_id, user_id, format,
    file_url, music_track, include_map_animation,
    include_photos,
):
    """Save trip summary metadata to the database."""
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
        print(f"  ⚠️ Failed to persist summary: {e}")


if __name__ == "__main__":
    import sys

    trip_id = (
        sys.argv[1] if len(sys.argv) > 1
        else "a0000001-0000-0000-0000-000000000001"
    )
    format = sys.argv[2] if len(sys.argv) > 2 else "image_slideshow"
    music_track = sys.argv[3] if len(sys.argv) > 3 else "vanlife_chill"

    print(f"📊 Generating trip summary ({format})...")
    if music_track:
        print(f"  🎵 Music track: {music_track}")
    result = generate_summary(trip_id, format=format, music_track=music_track)

    if result["status"] == "success":
        print(f"  ✅ Summary generated!")
        print(f"  📁 File: {result['file_url']}")
    else:
        print(f"  ❌ {result.get('message', 'Unknown error')}")

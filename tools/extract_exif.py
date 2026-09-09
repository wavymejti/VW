"""
EXIF extraction tool for the VW California AI Trip Planner.

Extracts GPS coordinates, timestamps, and camera metadata from
uploaded photos. Converts DMS coordinates to Decimal Degrees.

See: architecture/travel_memory_sop.md
"""

import os

# Register HEIF/HEIC opener for Pillow
try:
    from pillow_heif import register_heif_opener
    register_heif_opener()
except ImportError:
    pass

import re
import uuid
from datetime import datetime

from PIL import Image
from PIL.ExifTags import TAGS, GPSTAGS
from sqlalchemy import text

from tools.db import get_engine


# Supported image file extensions
SUPPORTED_FORMATS = {".jpg", ".jpeg", ".png", ".tiff", ".tif", ".heic", ".heif"}

# Maximum file size (20 MB)
MAX_FILE_SIZE_BYTES = 20 * 1024 * 1024

# Thumbnail max width
THUMBNAIL_MAX_WIDTH = 400


def extract_exif(filepath):
    """
    Extract EXIF metadata from an image file.

    Args:
        filepath (str): Path to the image file.

    Returns:
        dict: Extracted metadata including GPS coordinates,
              capture time, and camera info.
    """
    # Validate file
    if not os.path.exists(filepath):
        return {
            "status": "error",
            "message": f"File not found: {filepath}",
        }

    ext = os.path.splitext(filepath)[1].lower()
    if ext not in SUPPORTED_FORMATS:
        return {
            "status": "error",
            "message": (
                f"Unsupported format '{ext}'. "
                f"Supported: {', '.join(SUPPORTED_FORMATS)}"
            ),
        }

    file_size = os.path.getsize(filepath)
    if file_size > MAX_FILE_SIZE_BYTES:
        return {
            "status": "error",
            "message": (
                f"File too large ({file_size / 1024 / 1024:.1f}MB). "
                f"Max: {MAX_FILE_SIZE_BYTES / 1024 / 1024:.0f}MB."
            ),
        }

    try:
        image = Image.open(filepath)
        
        # HEIF/HEIC images use getexif() instead of _getexif()
        ext = os.path.splitext(filepath)[1].lower()
        if ext in (".heic", ".heif"):
            exif_data = image.getexif()
            if not exif_data:
                return {
                    "status": "warning",
                    "message": "No EXIF data found in image.",
                    "metadata": _empty_metadata(filepath),
                }
            
            # Parse EXIF tags
            parsed = {}
            for tag_id, value in exif_data.items():
                tag_name = TAGS.get(tag_id, str(tag_id))
                parsed[tag_name] = value
            
            # Extract GPS data from GPS IFD for HEIF/HEIC
            gps_ifd = exif_data.get_ifd(34853)  # GPSInfo tag ID
            lat, lng = _parse_gps(gps_ifd)
        else:
            exif_data = image._getexif()

            if not exif_data:
                return {
                    "status": "warning",
                    "message": "No EXIF data found in image.",
                    "metadata": _empty_metadata(filepath),
                }

            # Parse EXIF tags
            parsed = {}
            for tag_id, value in exif_data.items():
                tag_name = TAGS.get(tag_id, str(tag_id))
                parsed[tag_name] = value

            # Extract GPS data
            gps_info = parsed.get("GPSInfo", {})
            lat, lng = _parse_gps(gps_info)

        # Extract timestamp
        captured_at = _parse_datetime(
            parsed.get("DateTimeOriginal")
            or parsed.get("DateTime")
        )

        # Build metadata result
        metadata = {
            "lat": lat,
            "lng": lng,
            "captured_at": captured_at,
            "camera_make": parsed.get("Make"),
            "camera_model": parsed.get("Model"),
            "orientation": parsed.get("Orientation"),
            "original_filename": os.path.basename(filepath),
        }

        has_gps = lat is not None and lng is not None
        return {
            "status": "success" if has_gps else "warning",
            "message": (
                "EXIF extracted with GPS."
                if has_gps
                else "EXIF extracted but no GPS data found."
            ),
            "metadata": metadata,
        }

    except Exception as e:
        return {
            "status": "error",
            "message": f"Failed to extract EXIF: {e}",
        }


def _parse_gps(gps_info):
    """
    Parse GPS EXIF data, converting DMS to Decimal Degrees.

    Args:
        gps_info (dict): Raw GPS EXIF data.

    Returns:
        tuple: (latitude, longitude) as floats, or (None, None).
    """
    if not gps_info:
        return None, None

    # Parse GPS tags
    gps_data = {}
    for tag_id, value in gps_info.items():
        tag_name = GPSTAGS.get(tag_id, str(tag_id))
        gps_data[tag_name] = value

    try:
        # Extract lat/lng DMS values
        lat_dms = gps_data.get("GPSLatitude")
        lat_ref = gps_data.get("GPSLatitudeRef", "N")
        lng_dms = gps_data.get("GPSLongitude")
        lng_ref = gps_data.get("GPSLongitudeRef", "E")

        if not lat_dms or not lng_dms:
            return None, None

        # Convert DMS to Decimal Degrees
        lat = _dms_to_decimal(lat_dms, lat_ref)
        lng = _dms_to_decimal(lng_dms, lng_ref)

        # Validate ranges
        if not (-90 <= lat <= 90) or not (-180 <= lng <= 180):
            return None, None

        return round(lat, 7), round(lng, 7)

    except (TypeError, ValueError, KeyError):
        return None, None


def _dms_to_decimal(dms, ref):
    """
    Convert Degrees/Minutes/Seconds to Decimal Degrees.

    Args:
        dms (tuple): (degrees, minutes, seconds) — each may
                     be a fraction or float.
        ref (str): Hemisphere reference (N/S/E/W).

    Returns:
        float: Decimal degrees value.
    """
    degrees = float(dms[0])
    minutes = float(dms[1])
    seconds = float(dms[2])

    decimal = degrees + (minutes / 60) + (seconds / 3600)

    # Southern/Western hemispheres are negative
    if ref in ("S", "W"):
        decimal = -decimal

    return decimal


def _parse_datetime(dt_string):
    """
    Parse EXIF datetime string to ISO 8601 format.

    Args:
        dt_string (str): EXIF datetime
            (e.g., '2026:06:15 14:30:00').

    Returns:
        str: ISO 8601 timestamp or None.
    """
    if not dt_string:
        return None

    try:
        dt = datetime.strptime(str(dt_string), "%Y:%m:%d %H:%M:%S")
        return dt.isoformat()
    except ValueError:
        return None


def _empty_metadata(filepath):
    """
    Return an empty metadata dict when no EXIF is available.

    Args:
        filepath (str): Path to the image file.

    Returns:
        dict: Metadata with null values.
    """
    return {
        "lat": None,
        "lng": None,
        "captured_at": None,
        "camera_make": None,
        "camera_model": None,
        "orientation": None,
        "original_filename": os.path.basename(filepath),
    }


def generate_thumbnail(filepath, output_dir=None):
    """
    Generate a thumbnail version of an image.

    Args:
        filepath (str): Path to the original image.
        output_dir (str): Directory for the thumbnail.
            Defaults to .tmp/.

    Returns:
        str: Path to the generated thumbnail, or None.
    """
    if output_dir is None:
        output_dir = os.path.join(
            os.path.dirname(
                os.path.dirname(os.path.abspath(__file__))
            ),
            ".tmp",
        )

    os.makedirs(output_dir, exist_ok=True)

    try:
        image = Image.open(filepath)

        # Calculate thumbnail size maintaining aspect ratio
        width, height = image.size
        if width > THUMBNAIL_MAX_WIDTH:
            ratio = THUMBNAIL_MAX_WIDTH / width
            new_size = (
                THUMBNAIL_MAX_WIDTH,
                int(height * ratio),
            )
            image = image.resize(new_size, Image.LANCZOS)

        # Save thumbnail as JPEG for HEIC/HEIF or original format
        basename = os.path.basename(filepath)
        name, ext = os.path.splitext(basename)
        if ext.lower() in (".heic", ".heif"):
            thumb_filename = f"{name}_thumb.jpg"
            thumb_path = os.path.join(output_dir, thumb_filename)
            image.convert("RGB").save(thumb_path, "JPEG", quality=85)
        else:
            thumb_filename = f"{name}_thumb{ext}"
            thumb_path = os.path.join(output_dir, thumb_filename)
            image.save(thumb_path)

        return thumb_path

    except Exception as e:
        print(f"  ⚠️  Thumbnail generation failed: {e}")
        return None


def _generate_caption_from_filename(filepath):
    """
    Generate a clean, human-readable caption from the filename.

    Strips the file extension, replaces underscores and hyphens
    with spaces, and applies title case.

    Args:
        filepath (str): Path to the image file.

    Returns:
        str: A cleaned-up caption derived from the filename.
    """
    basename = os.path.basename(filepath)
    name, _ = os.path.splitext(basename)

    # Replace underscores and hyphens with spaces
    caption = re.sub(r"[_\-]+", " ", name)

    # Collapse multiple spaces and strip edges
    caption = re.sub(r"\s+", " ", caption).strip()

    return caption.title() if caption else "Untitled Photo"


def store_photo(filepath, user_id, trip_id=None):
    """
    Process a photo: extract EXIF, generate thumbnail, and
    store metadata in the database.

    Args:
        filepath (str): Path to the image file.
        user_id (str): User UUID.
        trip_id (str): Optional trip UUID to link.

    Returns:
        dict: Photo record with all metadata.
    """
    # Extract EXIF
    exif_result = extract_exif(filepath)
    metadata = exif_result.get("metadata", _empty_metadata(filepath))

    # Generate thumbnail
    thumb_path = generate_thumbnail(filepath)

    # Build photo record
    photo = {
        "id": str(uuid.uuid4()),
        "user_id": user_id,
        "trip_id": trip_id,
        "file_url": filepath,
        "thumbnail_url": thumb_path,
        "lat": metadata.get("lat"),
        "lng": metadata.get("lng"),
        "captured_at": metadata.get("captured_at"),
        "camera_make": metadata.get("camera_make"),
        "camera_model": metadata.get("camera_model"),
        "orientation": metadata.get("orientation"),
        "original_filename": metadata.get("original_filename"),
        "caption": _generate_caption_from_filename(filepath),
    }

    # Store in database
    try:
        engine = get_engine()
        with engine.connect() as conn:
            conn.execute(
                text("""
                    INSERT INTO photos
                        (id, user_id, trip_id, file_url,
                         thumbnail_url, location, lat, lng,
                         captured_at, camera_make, camera_model,
                         orientation, original_filename, caption)
                    VALUES
                        (:id, :user_id, :trip_id, :file_url,
                         :thumbnail_url,
                         CASE WHEN :lat IS NOT NULL THEN
                            ST_SetSRID(ST_MakePoint(:lng, :lat),
                            4326)::geography
                         ELSE NULL END,
                         :lat, :lng,
                         :captured_at, :camera_make,
                         :camera_model, :orientation,
                         :original_filename, :caption)
                """),
                photo,
            )
            conn.commit()
            print(f"  ✅ Photo stored: {photo['original_filename']}")

    except Exception as e:
        print(f"  ⚠️  Failed to store photo: {e}")

    # Auto-link the photo if possible
    link_info = _auto_link_photo(photo["id"], user_id, trip_id)
    if link_info:
        photo["trip_id"] = link_info["trip_id"]
        photo["tagged_day_schedule_id"] = link_info["tagged_day_schedule_id"]
        photo["day_number"] = link_info["day_number"]

    # Determine whether the frontend needs to ask for manual pinning
    exif_status = exif_result.get("status", "success")
    needs_location = (
        exif_status == "warning"
        and photo["lat"] is None
        and photo["lng"] is None
    )

    return {
        "status": exif_status,
        "photo_id": photo["id"],
        "photo": photo,
        "message": exif_result.get("message", ""),
        "linked": bool(link_info),
        "needs_location": needs_location,
    }

def _auto_link_photo(photo_id, user_id, trip_id_hint=None):
    """
    Attempt to auto-link a photo to a trip and daily schedule
    based on location proximity and timestamp.
    """
    try:
        engine = get_engine()
        with engine.connect() as conn:
            # Check if photo has location
            photo_res = conn.execute(
                text("SELECT lat, lng, captured_at, trip_id FROM photos WHERE id = :photo_id"),
                {"photo_id": photo_id}
            ).fetchone()
            
            if not photo_res or photo_res.lat is None or photo_res.lng is None:
                return None
                
            active_trip_id = trip_id_hint or photo_res.trip_id

            # Pass 1: Try temporal + spatial (5km threshold)
            query = """
                UPDATE photos p
                SET trip_id = ds.trip_id,
                    tagged_day_schedule_id = ds.id
                FROM daily_schedules ds
                JOIN trips t ON t.id = ds.trip_id
                WHERE p.id = :photo_id
                  AND t.user_id = :user_id
                  AND ds.route_polyline IS NOT NULL
                  AND (
                      p.captured_at IS NULL OR
                      (p.captured_at >= t.start_date AND p.captured_at < t.end_date + interval '1 day')
                  )
                  AND ST_DWithin(
                      p.location,
                      ST_LineFromEncodedPolyline(ds.route_polyline, 5)::geography,
                      5000
                  )
            """
            params = {"photo_id": photo_id, "user_id": user_id}
            if active_trip_id:
                query += " AND t.id = :active_trip_id"
                params["active_trip_id"] = active_trip_id
                
            query += " RETURNING ds.trip_id, ds.id, ds.day_number;"
            
            result = conn.execute(text(query), params).fetchone()
            conn.commit()
            
            if result:
                print(f"  🔗 Auto-linked to Trip {result[0]}, Day {result[2]}")
                return {
                    "trip_id": str(result[0]),
                    "tagged_day_schedule_id": str(result[1]),
                    "day_number": result[2]
                }

            # Pass 2: Spatial-only fallback (25km threshold) to closest route day
            query2 = """
                WITH closest_day AS (
                    SELECT ds.trip_id, ds.id as sched_id, ds.day_number
                    FROM daily_schedules ds
                    JOIN trips t ON t.id = ds.trip_id
                    WHERE t.user_id = :user_id
                      AND ds.route_polyline IS NOT NULL
            """
            params2 = {"photo_id": photo_id, "user_id": user_id}
            if active_trip_id:
                query2 += " AND t.id = :active_trip_id"
                params2["active_trip_id"] = active_trip_id

            query2 += """
                      AND ST_DWithin(
                          (SELECT location FROM photos WHERE id = :photo_id),
                          ST_LineFromEncodedPolyline(ds.route_polyline, 5)::geography,
                          25000
                      )
                    ORDER BY ST_Distance(
                        (SELECT location FROM photos WHERE id = :photo_id),
                        ST_LineFromEncodedPolyline(ds.route_polyline, 5)::geography
                    ) ASC
                    LIMIT 1
                )
                UPDATE photos p
                SET trip_id = cd.trip_id,
                    tagged_day_schedule_id = cd.sched_id
                FROM closest_day cd
                WHERE p.id = :photo_id
                RETURNING cd.trip_id, cd.sched_id, cd.day_number;
            """
            result2 = conn.execute(text(query2), params2).fetchone()
            conn.commit()

            if result2:
                print(f"  🔗 Proximity auto-linked to Trip {result2[0]}, Day {result2[2]}")
                return {
                    "trip_id": str(result2[0]),
                    "tagged_day_schedule_id": str(result2[1]),
                    "day_number": result2[2]
                }

            return None
            
    except Exception as e:
        print(f"  ⚠️ Auto-linking failed: {e}")
        return None


def pin_photo_location(
    photo_id,
    lat=None,
    lng=None,
    user_id=None,
    captured_at=None,
    tagged_day_schedule_id=None,
    trip_id=None,
    day_number=None,
):
    """
    Manually pin a photo or update its location, capture date, trip day, and trip.
    
    Args:
        photo_id (str): UUID of the photo
        lat (float, optional): Latitude (-90 to 90)
        lng (float, optional): Longitude (-180 to 180)
        user_id (str, optional): Optional user ID for authorization check
        captured_at (str, optional): ISO datetime or 'YYYY-MM-DD'
        tagged_day_schedule_id (str, optional): UUID of daily_schedule
        trip_id (str, optional): UUID of trip
        day_number (int, optional): Day number in trip (1-indexed)
        
    Returns:
        dict: Status and updated photo info
    """
    try:
        engine = get_engine()
        with engine.begin() as conn:
            # Check photo exists and user owns it
            query = "SELECT id, user_id, trip_id, lat, lng, captured_at FROM photos WHERE id = :photo_id"
            params = {"photo_id": photo_id}
            if user_id:
                query += " AND user_id = :user_id"
                params["user_id"] = user_id
                
            photo = conn.execute(text(query), params).fetchone()
            if not photo:
                return {"status": "error", "message": "Photo not found or unauthorized"}

            # Resolve schedule if day_number or tagged_day_schedule_id given
            final_schedule_id = tagged_day_schedule_id
            final_trip_id = trip_id or photo.trip_id
            final_day_num = day_number

            if final_schedule_id:
                sched_row = conn.execute(
                    text("SELECT id, trip_id, day_number, schedule_date FROM daily_schedules WHERE id = :sid"),
                    {"sid": final_schedule_id}
                ).fetchone()
                if sched_row:
                    final_trip_id = str(sched_row.trip_id)
                    final_day_num = sched_row.day_number
            elif final_trip_id and final_day_num is not None:
                sched_row = conn.execute(
                    text("SELECT id, day_number, schedule_date FROM daily_schedules WHERE trip_id = :tid AND day_number = :dnum"),
                    {"tid": final_trip_id, "dnum": int(final_day_num)}
                ).fetchone()
                if sched_row:
                    final_schedule_id = str(sched_row.id)

            # Parse captured_at if provided
            parsed_dt = None
            if captured_at:
                try:
                    c_clean = str(captured_at).strip().replace("Z", "+00:00")
                    if len(c_clean) == 10:  # YYYY-MM-DD
                        parsed_dt = datetime.strptime(c_clean, "%Y-%m-%d")
                    else:
                        parsed_dt = datetime.fromisoformat(c_clean)
                except Exception as e:
                    print(f"  ⚠️ Could not parse captured_at '{captured_at}': {e}")

            # Prepare update statements
            update_clauses = []
            update_params = {"photo_id": photo_id}

            if lat is not None and lng is not None:
                fl_lat = float(lat)
                fl_lng = float(lng)
                if not (-90 <= fl_lat <= 90) or not (-180 <= fl_lng <= 180):
                    return {"status": "error", "message": "Invalid coordinates"}
                update_clauses.append("lat = :lat")
                update_clauses.append("lng = :lng")
                update_clauses.append("location = ST_SetSRID(ST_MakePoint(:lng, :lat), 4326)::geography")
                update_params["lat"] = fl_lat
                update_params["lng"] = fl_lng

            if parsed_dt is not None:
                update_clauses.append("captured_at = :captured_at")
                update_params["captured_at"] = parsed_dt

            if final_trip_id is not None:
                update_clauses.append("trip_id = :trip_id")
                update_params["trip_id"] = final_trip_id

            if final_schedule_id is not None:
                update_clauses.append("tagged_day_schedule_id = :tagged_sched_id")
                update_params["tagged_sched_id"] = final_schedule_id

            if update_clauses:
                sql = f"UPDATE photos SET {', '.join(update_clauses)} WHERE id = :photo_id"
                conn.execute(text(sql), update_params)

        # If location was provided but no schedule was explicitly linked, attempt auto-link
        link_info = None
        if not final_schedule_id:
            link_info = _auto_link_photo(photo_id, photo.user_id, final_trip_id)
        
        return {
            "status": "success",
            "message": "Photo updated successfully",
            "photo_id": photo_id,
            "lat": update_params.get("lat", float(photo.lat) if photo.lat is not None else None),
            "lng": update_params.get("lng", float(photo.lng) if photo.lng is not None else None),
            "captured_at": parsed_dt.isoformat() if parsed_dt else (photo.captured_at.isoformat() if photo.captured_at else None),
            "tagged_day_schedule_id": final_schedule_id or (link_info.get("tagged_day_schedule_id") if link_info else None),
            "day_number": final_day_num or (link_info.get("day_number") if link_info else None),
            "trip_id": final_trip_id or (link_info.get("trip_id") if link_info else None),
            "linked": bool(final_schedule_id or link_info),
        }
            
    except Exception as e:
        print(f"  ⚠️  Failed to pin/update photo: {e}")
        return {"status": "error", "message": str(e)}


if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        print("Usage: python3 -m tools.extract_exif <image_path>")
        sys.exit(1)

    filepath = sys.argv[1]
    print(f"📷 Extracting EXIF from: {filepath}")
    result = extract_exif(filepath)

    if result["status"] in ("success", "warning"):
        meta = result["metadata"]
        print(f"  Status: {result['status']}")
        print(f"  Message: {result['message']}")
        print(f"  GPS: {meta['lat']}, {meta['lng']}")
        print(f"  Captured: {meta['captured_at']}")
        print(f"  Camera: {meta['camera_make']} "
              f"{meta['camera_model']}")
    else:
        print(f"  ❌ {result['message']}")

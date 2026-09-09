"""
Persistent database cache module for attractions and points of interest (POI).

Provides 2-tier caching for the VW California AI Trip Planner:
1. Spatial POI Cache (cached_attractions) using PostGIS ST_DWithin:
   Stores individual attraction details to eliminate repeated Google Places API calls
   across overlapping trip segments.
2. Trip-Level Aggregated Cache (trip_attractions_cache):
   Stores the full multi-day attractions JSON for a trip route so repeat views,
   reloads, and server restarts return results instantly with 0 external API calls.
"""

import json
import logging
from decimal import Decimal
from sqlalchemy import text
from tools.db import get_engine

logger = logging.getLogger(__name__)


def get_trip_attractions_cache(trip_id, cache_key):
    """
    Retrieve cached trip attractions payload from PostgreSQL.

    Args:
        trip_id (str): UUID of the trip.
        cache_key (str): Unique cache key identifying trip and filter parameters.

    Returns:
        dict | None: The cached attractions dictionary or None if not found/error.
    """
    if not cache_key:
        return None

    try:
        engine = get_engine()
        with engine.connect() as conn:
            row = conn.execute(
                text(
                    "SELECT attractions_data "
                    "FROM trip_attractions_cache "
                    "WHERE cache_key = :key"
                ),
                {"key": cache_key},
            ).fetchone()

            if not row:
                return None

            data = row[0]
            if isinstance(data, str):
                return json.loads(data)
            return data

    except Exception as e:
        logger.warning(
            "[attractions_cache] Failed to read trip cache for %s: %s",
            cache_key,
            e,
        )
        return None


def save_trip_attractions_cache(trip_id, cache_key, attractions_data):
    """
    Persist aggregated trip attractions payload to PostgreSQL.

    Args:
        trip_id (str): UUID of the trip.
        cache_key (str): Unique cache key identifying trip and parameters.
        attractions_data (dict): Full attractions payload to cache.

    Returns:
        bool: True if successfully saved, False otherwise.
    """
    if not trip_id or not cache_key or not attractions_data:
        return False

    try:
        engine = get_engine()
        with engine.connect() as conn:
            conn.execute(
                text(
                    """
                    INSERT INTO trip_attractions_cache
                        (trip_id, cache_key, attractions_data, updated_at)
                    VALUES
                        (:trip_id, :cache_key, :attractions_data, NOW())
                    ON CONFLICT (cache_key) DO UPDATE SET
                        attractions_data = EXCLUDED.attractions_data,
                        updated_at = NOW()
                    """
                ),
                {
                    "trip_id": str(trip_id),
                    "cache_key": cache_key,
                    "attractions_data": json.dumps(attractions_data),
                },
            )
            conn.commit()
            return True

    except Exception as e:
        logger.warning(
            "[attractions_cache] Failed to write trip cache for %s: %s",
            cache_key,
            e,
        )
        return False


def get_cached_attractions_near(lat, lng, radius_m=20000, limit=20):
    """
    Search cached POIs within a given radius using PostGIS ST_DWithin.

    Args:
        lat (float): Latitude of the center point.
        lng (float): Longitude of the center point.
        radius_m (int): Search radius in meters (default 20,000m = 20km).
        limit (int): Maximum number of attractions to retrieve.

    Returns:
        list[dict]: List of normalized attraction dictionaries.
    """
    if lat is None or lng is None:
        return []

    try:
        engine = get_engine()
        with engine.connect() as conn:
            query = text(
                """
                SELECT place_id, name, lat, lng, rating, user_ratings_total,
                       address, types, category, category_label, emoji, color,
                       photo_url, google_maps_url,
                       ST_Distance(
                           location,
                           ST_SetSRID(ST_MakePoint(:lng, :lat), 4326)::geography
                       ) AS distance_m
                FROM cached_attractions
                WHERE ST_DWithin(
                    location,
                    ST_SetSRID(ST_MakePoint(:lng, :lat), 4326)::geography,
                    :radius_m
                )
                ORDER BY user_ratings_total DESC NULLS LAST, rating DESC NULLS LAST
                LIMIT :limit
                """
            )

            rows = conn.execute(
                query,
                {
                    "lat": float(lat),
                    "lng": float(lng),
                    "radius_m": int(radius_m),
                    "limit": int(limit),
                },
            ).fetchall()

            results = []
            for row in rows:
                r_dict = {
                    "place_id": row[0],
                    "name": row[1],
                    "lat": float(row[2]) if isinstance(row[2], Decimal) else row[2],
                    "lng": float(row[3]) if isinstance(row[3], Decimal) else row[3],
                    "rating": float(row[4]) if isinstance(row[4], Decimal) else row[4],
                    "user_ratings_total": int(row[5]) if row[5] is not None else 0,
                    "address": row[6] or "",
                    "types": row[7] if isinstance(row[7], list) else [],
                    "category": row[8] or "tourist_attraction",
                    "category_label": row[9] or "Atrakcja",
                    "emoji": row[10] or "⭐",
                    "color": row[11] or "#F9A825",
                    "photo_url": row[12],
                    "google_maps_url": row[13],
                }
                results.append(r_dict)

            return results

    except Exception as e:
        logger.warning(
            "[attractions_cache] Spatial search failed near (%s, %s): %s",
            lat,
            lng,
            e,
        )
        return []


def save_cached_attractions(attractions):
    """
    Save or update a list of attractions into the persistent spatial cache.

    Args:
        attractions (list[dict]): Normalized attraction dictionaries.

    Returns:
        int: Number of items successfully saved.
    """
    if not attractions:
        return 0

    saved_count = 0
    try:
        engine = get_engine()
        with engine.connect() as conn:
            for item in attractions:
                pid = item.get("place_id")
                lat = item.get("lat")
                lng = item.get("lng")
                name = item.get("name")

                if not pid or lat is None or lng is None or not name:
                    continue

                types_val = item.get("types")
                if not isinstance(types_val, list):
                    types_val = []

                rating_val = item.get("rating")
                if rating_val is not None:
                    rating_val = float(rating_val)

                reviews_val = item.get("user_ratings_total") or item.get("review_count") or 0

                conn.execute(
                    text(
                        """
                        INSERT INTO cached_attractions (
                            place_id, name, location, lat, lng,
                            rating, user_ratings_total, address, types,
                            category, category_label, emoji, color,
                            photo_url, google_maps_url, updated_at
                        ) VALUES (
                            :place_id, :name,
                            ST_SetSRID(ST_MakePoint(:lng, :lat), 4326)::geography,
                            :lat, :lng,
                            :rating, :user_ratings_total, :address, :types,
                            :category, :category_label, :emoji, :color,
                            :photo_url, :google_maps_url, NOW()
                        )
                        ON CONFLICT (place_id) DO UPDATE SET
                            rating = EXCLUDED.rating,
                            user_ratings_total = EXCLUDED.user_ratings_total,
                            photo_url = COALESCE(EXCLUDED.photo_url, cached_attractions.photo_url),
                            address = COALESCE(EXCLUDED.address, cached_attractions.address),
                            updated_at = NOW()
                        """
                    ),
                    {
                        "place_id": pid,
                        "name": name,
                        "lat": float(lat),
                        "lng": float(lng),
                        "rating": rating_val,
                        "user_ratings_total": int(reviews_val),
                        "address": item.get("address") or "",
                        "types": types_val,
                        "category": item.get("category") or "tourist_attraction",
                        "category_label": item.get("category_label") or "Atrakcja",
                        "emoji": item.get("emoji") or "⭐",
                        "color": item.get("color") or "#F9A825",
                        "photo_url": item.get("photo_url"),
                        "google_maps_url": item.get("google_maps_url"),
                    },
                )
                saved_count += 1

            conn.commit()

    except Exception as e:
        logger.warning("[attractions_cache] Failed to save attractions: %s", e)

    return saved_count

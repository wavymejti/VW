"""
Camping search tool for the VW California AI Trip Planner.

Searches for campgrounds matching user filters near a given location.
Uses PostGIS database first, falls back to Google Maps Places API
if insufficient results are found.

See: architecture/camping_search_sop.md
"""

import os
import sys
from sqlalchemy import text

from tools.db import get_engine
from tools.maps_client import get_client as get_maps_client


def search_campings(
    lat,
    lng,
    radius_km=50,
    amenities=None,
    max_cost_eur=None,
    vw_compatible=True,
    limit=10,
):
    """
    Search for campgrounds near a location with optional filters.

    Args:
        lat (float): Center latitude for the search.
        lng (float): Center longitude for the search.
        radius_km (float): Search radius in kilometers (default: 50).
        amenities (list): Required amenities
            (e.g., ['power', 'showers']).
        max_cost_eur (float): Maximum cost per night in EUR.
        vw_compatible (bool): Only show VW California compatible sites.
        limit (int): Maximum number of results to return.

    Returns:
        dict: Search results with campings list and metadata.
    """
    if amenities is None:
        amenities = []

    # Validate inputs
    if not (-90 <= lat <= 90) or not (-180 <= lng <= 180):
        return {
            "status": "error",
            "message": "Invalid coordinates provided.",
            "results": [],
        }

    # Step 1: Query the local database using PostGIS
    db_results = _search_database(
        lat, lng, radius_km, amenities, max_cost_eur,
        vw_compatible, limit,
    )

    # Step 2: If insufficient results, fall back to Google Maps
    if len(db_results) < 3:
        maps_results = _search_google_maps(lat, lng, radius_km)
        # Cache new results in the database
        _cache_maps_results(maps_results)
        # Merge results, avoiding duplicates by place_id
        existing_ids = {c["place_id"] for c in db_results if c["place_id"]}
        for camp in maps_results:
            if camp["place_id"] not in existing_ids:
                db_results.append(camp)
        source = "mixed" if maps_results else "database"
    else:
        source = "database"

    # Trim to limit
    final_results = db_results[:limit]

    return {
        "status": "success",
        "results": final_results,
        "total_found": len(final_results),
        "source": source,
    }


def _search_database(lat, lng, radius_km, amenities, max_cost_eur,
                      vw_compatible, limit):
    """
    Query the PostGIS database for campgrounds within radius.

    Returns:
        list: List of camping dictionaries.
    """
    # Convert km to meters for ST_DWithin
    radius_m = radius_km * 1000

    # Build dynamic WHERE clauses for amenities
    amenity_conditions = []
    amenity_map = {
        "power": "has_power",
        "water": "has_water",
        "wifi": "has_wifi",
        "showers": "has_showers",
        "toilets": "has_toilets",
        "waste_disposal": "has_waste_disposal",
    }

    for amenity in amenities:
        col = amenity_map.get(amenity.lower())
        if col:
            amenity_conditions.append(f"{col} = TRUE")

    # Build the full query
    where_parts = [
        "ST_DWithin(location, "
        "ST_SetSRID(ST_MakePoint(:lng, :lat), 4326)::geography, "
        ":radius_m)"
    ]

    if amenity_conditions:
        where_parts.extend(amenity_conditions)

    if max_cost_eur is not None:
        where_parts.append(
            "cost_per_night_eur <= :max_cost_eur"
        )

    if vw_compatible:
        where_parts.append("shore_power_hookup = TRUE")

    where_clause = " AND ".join(where_parts)

    query = f"""
        SELECT id, name, lat, lng, place_id, address, country,
               cost_per_night_eur,
               has_power, has_water, has_wifi, has_showers,
               has_toilets, has_waste_disposal,
               shore_power_hookup, max_vehicle_length_m,
               level_ground, rating, review_count, source,
               ST_Distance(
                   location,
                   ST_SetSRID(ST_MakePoint(:lng, :lat),
                   4326)::geography
               ) AS distance_m
        FROM campings
        WHERE {where_clause}
        ORDER BY distance_m ASC, rating DESC NULLS LAST
        LIMIT :limit
    """

    params = {
        "lat": lat,
        "lng": lng,
        "radius_m": radius_m,
        "limit": limit,
    }
    if max_cost_eur is not None:
        params["max_cost_eur"] = max_cost_eur

    try:
        engine = get_engine()
        with engine.connect() as conn:
            result = conn.execute(text(query), params)
            rows = result.fetchall()
            columns = result.keys()

            campings = []
            for row in rows:
                camping = dict(zip(columns, row))
                # Convert UUID to string for JSON
                camping["id"] = str(camping["id"])
                # Round distance for readability
                camping["distance_km"] = round(
                    camping["distance_m"] / 1000, 1
                )
                del camping["distance_m"]
                campings.append(camping)

            return campings

    except Exception as e:
        print(f"  ⚠️  Database search failed: {e}")
        return []


def _search_google_maps(lat, lng, radius_km):
    """
    Search Google Maps Places API for campgrounds as a fallback.

    Returns:
        list: List of camping dictionaries from Google Maps.
    """
    try:
        client = get_maps_client()
        # Use Places API nearby search for campgrounds
        result = client.places_nearby(
            location=(lat, lng),
            radius=min(radius_km * 1000, 50000),  # Max 50km
            type="campground",
        )

        campings = []
        for place in result.get("results", []):
            location = place.get("geometry", {}).get("location", {})
            campings.append({
                "id": None,
                "name": place.get("name", "Unknown"),
                "lat": location.get("lat"),
                "lng": location.get("lng"),
                "place_id": place.get("place_id"),
                "address": place.get("vicinity"),
                "country": None,
                "cost_per_night_eur": None,
                "has_power": None,
                "has_water": None,
                "has_wifi": None,
                "has_showers": None,
                "has_toilets": None,
                "has_waste_disposal": None,
                "shore_power_hookup": None,
                "max_vehicle_length_m": None,
                "level_ground": None,
                "rating": place.get("rating"),
                "review_count": place.get(
                    "user_ratings_total", 0
                ),
                "source": "google_maps",
            })

        return campings

    except Exception as e:
        print(f"  ⚠️  Google Maps search failed: {e}")
        return []


def _cache_maps_results(campings):
    """
    Cache Google Maps results into the local database for future queries.

    Args:
        campings (list): List of camping dicts from Google Maps.
    """
    if not campings:
        return

    try:
        engine = get_engine()
        with engine.connect() as conn:
            for camp in campings:
                if not camp.get("place_id") or not camp.get("lat"):
                    continue

                # Check if already cached
                existing = conn.execute(
                    text(
                        "SELECT id FROM campings "
                        "WHERE place_id = :pid"
                    ),
                    {"pid": camp["place_id"]},
                ).fetchone()

                if existing:
                    continue

                # Insert new camping
                conn.execute(
                    text("""
                        INSERT INTO campings
                            (name, lat, lng, location, place_id,
                             address, rating, review_count, source)
                        VALUES
                            (:name, :lat, :lng,
                             ST_SetSRID(ST_MakePoint(:lng, :lat),
                             4326)::geography,
                             :place_id, :address, :rating,
                             :review_count, 'google_maps')
                    """),
                    {
                        "name": camp["name"],
                        "lat": camp["lat"],
                        "lng": camp["lng"],
                        "place_id": camp["place_id"],
                        "address": camp.get("address"),
                        "rating": camp.get("rating"),
                        "review_count": camp.get("review_count", 0),
                    },
                )

            conn.commit()

    except Exception as e:
        print(f"  ⚠️  Failed to cache results: {e}")


if __name__ == "__main__":
    # Example: Search near Lake Bled, Slovenia
    print("🔍 Searching for campings near Lake Bled...")
    results = search_campings(
        lat=46.3636,
        lng=14.0938,
        radius_km=50,
        amenities=["power", "showers"],
        vw_compatible=True,
    )

    if results["status"] == "success":
        print(f"  Found {results['total_found']} results "
              f"(source: {results['source']})")
        for camp in results["results"]:
            print(f"  📍 {camp['name']} — "
                  f"{camp.get('distance_km', '?')}km away "
                  f"(€{camp.get('cost_per_night_eur', '?')}/night)")
    else:
        print(f"  ❌ {results['message']}")

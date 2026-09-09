-- =============================================================
-- VW California AI Trip Planner — Migration 006
-- Persistent PostgreSQL / PostGIS Caching for Attractions & POIs
-- =============================================================

-- 1. Spatial cache of individual points of interest (POI)
CREATE TABLE IF NOT EXISTS cached_attractions (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    place_id VARCHAR(255) NOT NULL UNIQUE,
    name VARCHAR(255) NOT NULL,
    location GEOGRAPHY(POINT, 4326),
    lat NUMERIC(10, 7) NOT NULL,
    lng NUMERIC(10, 7) NOT NULL,
    rating NUMERIC(2, 1) CHECK (rating >= 0 AND rating <= 5),
    user_ratings_total INTEGER DEFAULT 0,
    address TEXT,
    types TEXT[] DEFAULT '{}',
    category VARCHAR(50) DEFAULT 'tourist_attraction',
    category_label VARCHAR(100) DEFAULT 'Atrakcja',
    emoji VARCHAR(10) DEFAULT '⭐',
    color VARCHAR(20) DEFAULT '#F9A825',
    photo_url TEXT,
    google_maps_url TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Spatial index for radius / proximity queries
CREATE INDEX IF NOT EXISTS idx_cached_attractions_location 
    ON cached_attractions USING GIST(location);

-- Index for unique place lookup
CREATE INDEX IF NOT EXISTS idx_cached_attractions_place_id 
    ON cached_attractions(place_id);

-- 2. Aggregated attractions cache per trip route
CREATE TABLE IF NOT EXISTS trip_attractions_cache (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    trip_id UUID NOT NULL,
    cache_key VARCHAR(255) NOT NULL UNIQUE,
    attractions_data JSONB NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_trip_attractions_cache_key 
    ON trip_attractions_cache(cache_key);

CREATE INDEX IF NOT EXISTS idx_trip_attractions_trip_id 
    ON trip_attractions_cache(trip_id);

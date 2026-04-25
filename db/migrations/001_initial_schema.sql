-- =============================================================
-- VW California AI Trip Planner — Initial Database Schema
-- Migration 001: Core tables with PostGIS support
-- =============================================================

-- Enable PostGIS extension for geospatial queries
CREATE EXTENSION IF NOT EXISTS postgis;

-- Enable UUID generation
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- -----------------------------------------------------------
-- 1. Users
-- -----------------------------------------------------------
CREATE TABLE IF NOT EXISTS users (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    email VARCHAR(255) UNIQUE NOT NULL,
    display_name VARCHAR(100) NOT NULL,
    vehicle_model VARCHAR(100) DEFAULT 'VW California',

    -- Preferences (stored as JSONB for flexibility)
    max_daily_drive_hours NUMERIC(3, 1) DEFAULT 6.0,
    preferred_amenities TEXT[] DEFAULT '{}',
    budget_per_night_eur NUMERIC(8, 2),
    hookup_type VARCHAR(50),

    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- -----------------------------------------------------------
-- 2. Trips
-- -----------------------------------------------------------
CREATE TABLE IF NOT EXISTS trips (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    title VARCHAR(255) NOT NULL,
    description TEXT,

    -- Origin coordinates
    origin_label VARCHAR(255),
    origin_lat NUMERIC(10, 7),
    origin_lng NUMERIC(10, 7),

    -- Destination coordinates
    destination_label VARCHAR(255),
    destination_lat NUMERIC(10, 7),
    destination_lng NUMERIC(10, 7),

    start_date DATE,
    end_date DATE,
    status VARCHAR(20) DEFAULT 'draft'
        CHECK (status IN ('draft', 'planned', 'active', 'completed')),

    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_trips_user_id ON trips(user_id);
CREATE INDEX idx_trips_status ON trips(status);

-- -----------------------------------------------------------
-- 3. Campings
-- -----------------------------------------------------------
CREATE TABLE IF NOT EXISTS campings (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name VARCHAR(255) NOT NULL,
    location GEOGRAPHY(POINT, 4326),
    lat NUMERIC(10, 7) NOT NULL,
    lng NUMERIC(10, 7) NOT NULL,
    place_id VARCHAR(255),
    address TEXT,
    country CHAR(2),
    cost_per_night_eur NUMERIC(8, 2),

    -- Amenities
    has_power BOOLEAN DEFAULT FALSE,
    has_water BOOLEAN DEFAULT FALSE,
    has_wifi BOOLEAN DEFAULT FALSE,
    has_showers BOOLEAN DEFAULT FALSE,
    has_toilets BOOLEAN DEFAULT FALSE,
    has_waste_disposal BOOLEAN DEFAULT FALSE,

    -- VW California compatibility
    shore_power_hookup BOOLEAN DEFAULT FALSE,
    max_vehicle_length_m NUMERIC(4, 1),
    level_ground BOOLEAN,

    rating NUMERIC(2, 1) CHECK (rating >= 0 AND rating <= 5),
    review_count INTEGER DEFAULT 0,
    photos TEXT[] DEFAULT '{}',
    source VARCHAR(50) DEFAULT 'google_maps'
        CHECK (source IN ('google_maps', 'user_submitted', 'partner_db')),

    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Spatial index for proximity queries
CREATE INDEX idx_campings_location ON campings USING GIST(location);
CREATE INDEX idx_campings_country ON campings(country);
CREATE INDEX idx_campings_place_id ON campings(place_id);

-- -----------------------------------------------------------
-- 4. Daily Schedules
-- -----------------------------------------------------------
CREATE TABLE IF NOT EXISTS daily_schedules (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    trip_id UUID NOT NULL REFERENCES trips(id) ON DELETE CASCADE,
    day_number INTEGER NOT NULL CHECK (day_number > 0),
    schedule_date DATE,
    driving_hours NUMERIC(4, 1),
    driving_km NUMERIC(7, 1),

    -- Waypoints stored as JSONB array
    waypoints JSONB DEFAULT '[]',

    overnight_camping_id UUID REFERENCES campings(id),
    route_polyline TEXT,

    UNIQUE(trip_id, day_number)
);

CREATE INDEX idx_daily_schedules_trip_id ON daily_schedules(trip_id);

-- -----------------------------------------------------------
-- 5. Photos (Travel Memory)
-- -----------------------------------------------------------
CREATE TABLE IF NOT EXISTS photos (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    trip_id UUID REFERENCES trips(id) ON DELETE SET NULL,
    file_url TEXT NOT NULL,
    thumbnail_url TEXT,
    location GEOGRAPHY(POINT, 4326),
    lat NUMERIC(10, 7),
    lng NUMERIC(10, 7),
    captured_at TIMESTAMPTZ,

    -- EXIF metadata
    camera_make VARCHAR(100),
    camera_model VARCHAR(100),
    orientation INTEGER,
    original_filename VARCHAR(255),

    caption TEXT,
    tagged_day_schedule_id UUID REFERENCES daily_schedules(id)
        ON DELETE SET NULL,

    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Spatial index for proximity queries on photos
CREATE INDEX idx_photos_location ON photos USING GIST(location);
CREATE INDEX idx_photos_user_id ON photos(user_id);
CREATE INDEX idx_photos_trip_id ON photos(trip_id);

-- -----------------------------------------------------------
-- 6. Chat Messages (AI Conversation)
-- -----------------------------------------------------------
CREATE TABLE IF NOT EXISTS chat_messages (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    trip_id UUID NOT NULL REFERENCES trips(id) ON DELETE CASCADE,
    role VARCHAR(20) NOT NULL
        CHECK (role IN ('user', 'assistant', 'system')),
    content TEXT NOT NULL,

    -- Tool calls stored as JSONB array
    tool_calls JSONB DEFAULT '[]',

    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_chat_messages_trip_id ON chat_messages(trip_id);
CREATE INDEX idx_chat_messages_created_at
    ON chat_messages(trip_id, created_at);

-- -----------------------------------------------------------
-- 7. Trip Summaries (Shareable Export)
-- -----------------------------------------------------------
CREATE TABLE IF NOT EXISTS trip_summaries (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    trip_id UUID NOT NULL REFERENCES trips(id) ON DELETE CASCADE,
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    format VARCHAR(30) NOT NULL
        CHECK (format IN ('video', 'image_slideshow', 'pdf')),
    file_url TEXT NOT NULL,
    music_track VARCHAR(255),
    include_map_animation BOOLEAN DEFAULT TRUE,
    include_photos BOOLEAN DEFAULT TRUE,

    generated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_trip_summaries_trip_id ON trip_summaries(trip_id);

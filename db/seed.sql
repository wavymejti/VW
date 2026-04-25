-- =============================================================
-- VW California AI Trip Planner — Seed Data
-- Provides sample data for development and testing
-- =============================================================

-- -----------------------------------------------------------
-- Sample User
-- -----------------------------------------------------------
INSERT INTO users (id, email, display_name, vehicle_model,
                   max_daily_drive_hours, preferred_amenities,
                   budget_per_night_eur, hookup_type)
VALUES (
    'a1b2c3d4-e5f6-7890-abcd-ef1234567890',
    'traveler@example.com',
    'VW Explorer',
    'VW California Ocean 6.1',
    6.0,
    ARRAY['power', 'water', 'showers'],
    35.00,
    'shore_power'
);

-- -----------------------------------------------------------
-- Sample Campings (European VW California-friendly sites)
-- -----------------------------------------------------------

-- Camping Seiser Alm, Italy
INSERT INTO campings (id, name, lat, lng, location, place_id,
                      address, country, cost_per_night_eur,
                      has_power, has_water, has_wifi, has_showers,
                      has_toilets, has_waste_disposal,
                      shore_power_hookup, max_vehicle_length_m,
                      level_ground, rating, review_count, source)
VALUES (
    'c0000001-0000-0000-0000-000000000001',
    'Camping Seiser Alm',
    46.5413, 11.5576,
    ST_SetSRID(ST_MakePoint(11.5576, 46.5413), 4326)::geography,
    NULL,
    'Compatsch, 39040 Seiser Alm, South Tyrol, Italy',
    'IT', 32.00,
    TRUE, TRUE, TRUE, TRUE, TRUE, TRUE,
    TRUE, 7.0, TRUE,
    4.5, 128, 'user_submitted'
);

-- Camping Bled, Slovenia
INSERT INTO campings (id, name, lat, lng, location, place_id,
                      address, country, cost_per_night_eur,
                      has_power, has_water, has_wifi, has_showers,
                      has_toilets, has_waste_disposal,
                      shore_power_hookup, max_vehicle_length_m,
                      level_ground, rating, review_count, source)
VALUES (
    'c0000001-0000-0000-0000-000000000002',
    'Camping Bled',
    46.3576, 14.0986,
    ST_SetSRID(ST_MakePoint(14.0986, 46.3576), 4326)::geography,
    NULL,
    'Kidričeva cesta 10c, 4260 Bled, Slovenia',
    'SI', 28.00,
    TRUE, TRUE, TRUE, TRUE, TRUE, FALSE,
    TRUE, 7.5, TRUE,
    4.3, 245, 'user_submitted'
);

-- Camping Stobrec, Croatia
INSERT INTO campings (id, name, lat, lng, location, place_id,
                      address, country, cost_per_night_eur,
                      has_power, has_water, has_wifi, has_showers,
                      has_toilets, has_waste_disposal,
                      shore_power_hookup, max_vehicle_length_m,
                      level_ground, rating, review_count, source)
VALUES (
    'c0000001-0000-0000-0000-000000000003',
    'Camping Stobreč Split',
    43.5033, 16.5260,
    ST_SetSRID(ST_MakePoint(16.5260, 43.5033), 4326)::geography,
    NULL,
    'Sv. Lovre 6, 21311 Stobreč, Croatia',
    'HR', 25.00,
    TRUE, TRUE, TRUE, TRUE, TRUE, TRUE,
    TRUE, 8.0, TRUE,
    4.1, 312, 'user_submitted'
);

-- Stellplatz Walchensee, Germany
INSERT INTO campings (id, name, lat, lng, location, place_id,
                      address, country, cost_per_night_eur,
                      has_power, has_water, has_wifi, has_showers,
                      has_toilets, has_waste_disposal,
                      shore_power_hookup, max_vehicle_length_m,
                      level_ground, rating, review_count, source)
VALUES (
    'c0000001-0000-0000-0000-000000000004',
    'Stellplatz Walchensee',
    47.5969, 11.3574,
    ST_SetSRID(ST_MakePoint(11.3574, 47.5969), 4326)::geography,
    NULL,
    'Seestraße 1, 82432 Walchensee, Germany',
    'DE', 18.00,
    TRUE, TRUE, FALSE, FALSE, TRUE, FALSE,
    FALSE, 6.5, TRUE,
    3.8, 87, 'user_submitted'
);

-- -----------------------------------------------------------
-- Sample Trip
-- -----------------------------------------------------------
INSERT INTO trips (id, user_id, title, description,
                   origin_label, origin_lat, origin_lng,
                   destination_label, destination_lat, destination_lng,
                   start_date, end_date, status)
VALUES (
    'a0000001-0000-0000-0000-000000000001',
    'a1b2c3d4-e5f6-7890-abcd-ef1234567890',
    'Munich to Split Adventure',
    'A 5-day road trip from Munich through the Alps to the Croatian coast.',
    'Munich, Germany', 48.1351, 11.5820,
    'Split, Croatia', 43.5081, 16.4402,
    '2026-06-15', '2026-06-19',
    'planned'
);

-- -----------------------------------------------------------
-- Sample Daily Schedules
-- -----------------------------------------------------------

-- Day 1: Munich → Walchensee
INSERT INTO daily_schedules (id, trip_id, day_number, schedule_date,
                             driving_hours, driving_km, waypoints,
                             overnight_camping_id)
VALUES (
    'b0000001-0000-0000-0000-000000000001',
    'a0000001-0000-0000-0000-000000000001',
    1, '2026-06-15',
    1.5, 95,
    '[
        {"order": 1, "type": "start", "label": "Munich", "lat": 48.1351, "lng": 11.5820},
        {"order": 2, "type": "attraction", "label": "Starnberger See", "lat": 47.9122, "lng": 11.3144},
        {"order": 3, "type": "camping", "label": "Stellplatz Walchensee", "lat": 47.5969, "lng": 11.3574}
    ]',
    'c0000001-0000-0000-0000-000000000004'
);

-- Day 2: Walchensee → Seiser Alm
INSERT INTO daily_schedules (id, trip_id, day_number, schedule_date,
                             driving_hours, driving_km, waypoints,
                             overnight_camping_id)
VALUES (
    'b0000001-0000-0000-0000-000000000002',
    'a0000001-0000-0000-0000-000000000001',
    2, '2026-06-16',
    3.0, 180,
    '[
        {"order": 1, "type": "start", "label": "Walchensee", "lat": 47.5969, "lng": 11.3574},
        {"order": 2, "type": "attraction", "label": "Innsbruck Old Town", "lat": 47.2692, "lng": 11.3933},
        {"order": 3, "type": "camping", "label": "Camping Seiser Alm", "lat": 46.5413, "lng": 11.5576}
    ]',
    'c0000001-0000-0000-0000-000000000001'
);

-- Day 3: Seiser Alm → Lake Bled
INSERT INTO daily_schedules (id, trip_id, day_number, schedule_date,
                             driving_hours, driving_km, waypoints,
                             overnight_camping_id)
VALUES (
    'b0000001-0000-0000-0000-000000000003',
    'a0000001-0000-0000-0000-000000000001',
    3, '2026-06-17',
    3.5, 220,
    '[
        {"order": 1, "type": "start", "label": "Seiser Alm", "lat": 46.5413, "lng": 11.5576},
        {"order": 2, "type": "attraction", "label": "Lago di Braies", "lat": 46.6948, "lng": 12.0839},
        {"order": 3, "type": "camping", "label": "Camping Bled", "lat": 46.3576, "lng": 14.0986}
    ]',
    'c0000001-0000-0000-0000-000000000002'
);

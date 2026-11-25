-- How a trip was shaped: stops from the start form (in the user's order) and the points of a
-- line drawn on the map. modify_route re-plans with them so a change made later in the chat
-- keeps the order and the drawing. {"route_stops": [...], "via_points": [...]}
ALTER TABLE trips ADD COLUMN IF NOT EXISTS plan_params JSONB;

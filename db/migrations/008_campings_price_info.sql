-- Free or paid for every place to stay: keep park4night's spot type and price text
-- in the campings cache (they were dropped, so cached spots had no price at all).
ALTER TABLE campings ADD COLUMN IF NOT EXISTS spot_code VARCHAR(16);
ALTER TABLE campings ADD COLUMN IF NOT EXISTS price_info TEXT;

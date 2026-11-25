-- Allow overnight spots from park4night (via Apify, POC) in the campings cache.
ALTER TABLE campings DROP CONSTRAINT IF EXISTS campings_source_check;
ALTER TABLE campings ADD CONSTRAINT campings_source_check
    CHECK (source IN ('google_maps', 'user_submitted', 'partner_db', 'park4night'));

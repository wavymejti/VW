-- Sprint 5.1: Add user preferences memory

ALTER TABLE users 
ADD COLUMN IF NOT EXISTS preferences_json JSONB DEFAULT '{}';

-- =============================================================
-- VW California AI Trip Planner — Migration 004
-- Allow chat_messages to be linked directly to user_id (and trip_id nullable)
-- =============================================================

ALTER TABLE chat_messages ADD COLUMN IF NOT EXISTS user_id UUID REFERENCES users(id) ON DELETE CASCADE;

-- Drop NOT NULL constraint on trip_id if it exists
ALTER TABLE chat_messages ALTER COLUMN trip_id DROP NOT NULL;

-- Indexes for performance
CREATE INDEX IF NOT EXISTS idx_chat_messages_user_id ON chat_messages(user_id);
CREATE INDEX IF NOT EXISTS idx_chat_messages_user_created ON chat_messages(user_id, created_at);

-- =============================================================
-- VW California AI Trip Planner — Interaction Logs Schema
-- Migration 002: Table for global analysis logs
-- =============================================================

CREATE TABLE IF NOT EXISTS interaction_logs (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_message TEXT NOT NULL,
    model_response TEXT NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

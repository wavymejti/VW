-- =============================================================
-- VW California AI Trip Planner — Database Migration
-- Migration 002: Add password_hash to users table
-- =============================================================

ALTER TABLE users ADD COLUMN password_hash VARCHAR(255);

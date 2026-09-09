-- =============================================================
-- VW California AI Trip Planner — Migration 005
-- Personalized Long-Term Memory (RAG) for User Preferences
-- =============================================================

CREATE TABLE IF NOT EXISTS user_memories (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    
    -- Category and polarity for filtering and categorization
    category VARCHAR(50) NOT NULL DEFAULT 'general',
    polarity VARCHAR(20) NOT NULL DEFAULT 'like'
        CHECK (polarity IN ('like', 'dislike', 'constraint', 'habit')),
        
    -- Extracted natural language preference / fact
    content TEXT NOT NULL,
    
    -- Normalized embedding vector stored as JSONB array of floats (e.g. 1536 dims)
    embedding_json JSONB NOT NULL,
    
    -- Confidence score of extraction (0.0 to 1.0)
    confidence NUMERIC(3, 2) DEFAULT 1.00,
    
    -- Soft-delete / active status
    is_active BOOLEAN DEFAULT TRUE,
    
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Fast lookup by user
CREATE INDEX IF NOT EXISTS idx_user_memories_user_id ON user_memories(user_id);
CREATE INDEX IF NOT EXISTS idx_user_memories_active ON user_memories(user_id, is_active);

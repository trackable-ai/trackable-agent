-- Migration 003: Add OAuth tokens table and revert nullable user_id
-- Created: 2026-01-26
-- Description: Add secure storage for OAuth tokens with provider metadata

BEGIN;

-- =============================================================================
-- TABLE: oauth_tokens
-- Secure storage for OAuth access/refresh tokens and provider-specific metadata
-- Replaces gmail_connection JSONB in users table for Gmail connections
-- =============================================================================

CREATE TABLE oauth_tokens (
    -- Identity
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,

    -- Provider info
    provider VARCHAR(50) NOT NULL,  -- 'gmail', 'google', etc.
    provider_email VARCHAR(255),    -- Email associated with this provider account

    -- Tokens (encrypted at rest by Cloud SQL)
    access_token TEXT NOT NULL,
    refresh_token TEXT,
    token_type VARCHAR(50) DEFAULT 'Bearer',

    -- Token metadata
    scope TEXT,  -- Space-separated scopes
    expires_at TIMESTAMPTZ,

    -- Provider-specific metadata (for Gmail: sync state)
    last_sync TIMESTAMPTZ,           -- Last successful sync
    last_history_id VARCHAR(255),    -- Gmail historyId for incremental sync
    watch_expiration TIMESTAMPTZ,    -- Gmail push notification watch expiration

    -- Timestamps
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    -- One token per provider per user
    UNIQUE(user_id, provider)
);

CREATE INDEX idx_oauth_tokens_user ON oauth_tokens(user_id);
CREATE INDEX idx_oauth_tokens_provider ON oauth_tokens(provider);
CREATE INDEX idx_oauth_tokens_expires ON oauth_tokens(expires_at);
CREATE INDEX idx_oauth_tokens_watch ON oauth_tokens(watch_expiration) WHERE provider = 'gmail';

-- Add trigger for updated_at
CREATE TRIGGER update_oauth_tokens_updated_at BEFORE UPDATE ON oauth_tokens
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- =============================================================================
-- Clean up test data with NULL user_id before adding NOT NULL constraint
-- =============================================================================

-- Delete sources with NULL user_id (test data)
DELETE FROM sources WHERE user_id IS NULL;

-- Delete orders with NULL user_id (test data)
DELETE FROM orders WHERE user_id IS NULL;

-- =============================================================================
-- Revert user_id to NOT NULL
-- =============================================================================

-- Make user_id NOT NULL in sources table
ALTER TABLE sources ALTER COLUMN user_id SET NOT NULL;

-- Make user_id NOT NULL in orders table
ALTER TABLE orders ALTER COLUMN user_id SET NOT NULL;

-- =============================================================================
-- Remove gmail_connection from users table (now stored in oauth_tokens)
-- =============================================================================

ALTER TABLE users DROP COLUMN IF EXISTS gmail_connection;

COMMIT;

-- Migration 004: Add merchant aliases
-- Created: 2026-01-28
-- Description: Add support for merchant alias matching

BEGIN;

-- =============================================================================
-- Add aliases column to merchants table
-- Stores alternate names/variations for fuzzy matching
-- =============================================================================

ALTER TABLE merchants
ADD COLUMN IF NOT EXISTS aliases JSONB DEFAULT '[]';

-- Add index for alias lookups using GIN index for JSONB array contains
CREATE INDEX IF NOT EXISTS idx_merchants_aliases ON merchants USING GIN (aliases);

COMMIT;

-- Migration 007: Add policy_urls to merchants
-- Created: 2026-02-08
-- Description: Store manually found policy page URLs on merchant records

BEGIN;

-- =============================================================================
-- Add policy_urls column to merchants table
-- Stores URLs to return/exchange policy pages (manually curated)
-- =============================================================================

ALTER TABLE merchants
ADD COLUMN IF NOT EXISTS policy_urls JSONB DEFAULT '[]';

COMMIT;

-- Migration 002: Add unique constraint on merchants.domain
-- Created: 2026-01-26
-- Description: Add unique constraint to enable ON CONFLICT upsert

BEGIN;

-- Add unique constraint on merchants.domain for upsert support
-- First drop the existing index if it exists (we'll replace with unique constraint)
DROP INDEX IF EXISTS idx_merchants_domain;

-- Add unique constraint (which also creates an index)
ALTER TABLE merchants ADD CONSTRAINT merchants_domain_unique UNIQUE (domain);

-- Make user_id nullable in jobs table since we don't always have authenticated users
-- (user_id is already nullable per original schema)

-- Make user_id nullable in sources table for anonymous submissions
ALTER TABLE sources ALTER COLUMN user_id DROP NOT NULL;

-- Make user_id nullable in orders table for anonymous submissions
ALTER TABLE orders ALTER COLUMN user_id DROP NOT NULL;

COMMIT;

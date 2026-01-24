-- Migration 001: Initial Schema
-- Created: 2026-01-23
-- Description: Create all base tables for Trackable backend

BEGIN;

-- =============================================================================
-- TABLE: users
-- =============================================================================

CREATE TABLE users (
    -- Identity
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    email VARCHAR(255) UNIQUE NOT NULL,
    name VARCHAR(255),

    -- Status
    status VARCHAR(20) NOT NULL DEFAULT 'active',

    -- Gmail connection (JSONB from GmailConnection model)
    gmail_connection JSONB,

    -- Preferences (JSONB from UserPreferences model)
    preferences JSONB DEFAULT '{}',

    -- Statistics
    total_orders INT DEFAULT 0,
    active_orders INT DEFAULT 0,
    missed_return_windows INT DEFAULT 0,

    -- Timestamps
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    last_login TIMESTAMPTZ
);

CREATE INDEX idx_users_email ON users(email);
CREATE INDEX idx_users_status ON users(status);

-- =============================================================================
-- TABLE: merchants
-- =============================================================================

CREATE TABLE merchants (
    -- Identity
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(255) NOT NULL,
    domain VARCHAR(255),

    -- Support
    support_email VARCHAR(255),
    support_url TEXT,
    return_portal_url TEXT,

    -- Timestamps
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_merchants_name ON merchants(name);
CREATE INDEX idx_merchants_domain ON merchants(domain);

-- =============================================================================
-- TABLE: orders
-- =============================================================================

CREATE TABLE orders (
    -- Identity
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    merchant_id UUID NOT NULL REFERENCES merchants(id),

    -- Order details
    order_number VARCHAR(255),
    order_date TIMESTAMPTZ,
    status VARCHAR(50) NOT NULL DEFAULT 'detected',
    country_code VARCHAR(2),

    -- Items and pricing (JSONB)
    items JSONB NOT NULL DEFAULT '[]',
    subtotal JSONB,
    tax JSONB,
    shipping_cost JSONB,
    total JSONB,

    -- Return/exchange window tracking
    return_window_start TIMESTAMPTZ,
    return_window_end TIMESTAMPTZ,
    return_window_days INT,
    exchange_window_end TIMESTAMPTZ,
    is_monitored BOOLEAN DEFAULT TRUE,

    -- Source tracking
    source_type VARCHAR(20) NOT NULL,
    source_id VARCHAR(255),

    -- Agent metadata
    confidence_score DECIMAL(3, 2),
    needs_clarification BOOLEAN DEFAULT FALSE,
    clarification_questions JSONB DEFAULT '[]',

    -- URLs
    order_url TEXT,
    receipt_url TEXT,

    -- Refund tracking
    refund_initiated BOOLEAN DEFAULT FALSE,
    refund_amount JSONB,
    refund_completed_at TIMESTAMPTZ,

    -- Notes and agent reasoning
    notes JSONB DEFAULT '[]',
    last_agent_intervention TIMESTAMPTZ,

    -- Timestamps
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_orders_user ON orders(user_id);
CREATE INDEX idx_orders_merchant ON orders(merchant_id);
CREATE INDEX idx_orders_status ON orders(status);
CREATE INDEX idx_orders_source ON orders(source_type, source_id);
CREATE INDEX idx_orders_return_window ON orders(return_window_end) WHERE is_monitored = TRUE;
CREATE INDEX idx_orders_country ON orders(country_code);

-- =============================================================================
-- TABLE: shipments
-- =============================================================================

CREATE TABLE shipments (
    -- Identity
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    order_id UUID NOT NULL REFERENCES orders(id) ON DELETE CASCADE,

    -- Tracking
    tracking_number VARCHAR(255),
    carrier VARCHAR(50) NOT NULL DEFAULT 'unknown',
    status VARCHAR(50) NOT NULL DEFAULT 'pending',

    -- Addresses
    shipping_address TEXT,
    return_address TEXT,

    -- Timing
    shipped_at TIMESTAMPTZ,
    estimated_delivery TIMESTAMPTZ,
    delivered_at TIMESTAMPTZ,

    -- Tracking details
    tracking_url TEXT,
    events JSONB DEFAULT '[]',
    last_updated TIMESTAMPTZ,

    -- Timestamps
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_shipments_order ON shipments(order_id);
CREATE INDEX idx_shipments_tracking ON shipments(tracking_number);
CREATE INDEX idx_shipments_status ON shipments(status);
CREATE INDEX idx_shipments_carrier ON shipments(carrier);

-- =============================================================================
-- TABLE: policies
-- =============================================================================

CREATE TABLE policies (
    -- Identity
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    merchant_id UUID NOT NULL REFERENCES merchants(id),

    -- Policy classification
    policy_type VARCHAR(50) NOT NULL,
    country_code VARCHAR(2) NOT NULL,

    -- Basic metadata
    name VARCHAR(255) NOT NULL,
    description TEXT,
    version VARCHAR(50),
    effective_date TIMESTAMPTZ,

    -- Policy details (JSONB)
    return_policy JSONB,
    exchange_policy JSONB,

    -- Source tracking
    source_url TEXT,
    raw_text TEXT,

    -- Agent metadata
    confidence_score DECIMAL(3, 2),
    last_verified TIMESTAMPTZ,
    needs_verification BOOLEAN DEFAULT FALSE,
    interpretation_notes JSONB DEFAULT '[]',

    -- Timestamps
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    UNIQUE(merchant_id, policy_type, country_code)
);

CREATE INDEX idx_policies_merchant ON policies(merchant_id);
CREATE INDEX idx_policies_country ON policies(country_code);
CREATE INDEX idx_policies_type ON policies(policy_type);

-- =============================================================================
-- TABLE: jobs
-- =============================================================================

CREATE TABLE jobs (
    -- Identity
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID REFERENCES users(id) ON DELETE CASCADE,

    -- Job details
    job_type VARCHAR(50) NOT NULL,
    status VARCHAR(50) NOT NULL DEFAULT 'queued',

    -- Payload
    input_data JSONB DEFAULT '{}',
    output_data JSONB DEFAULT '{}',

    -- Error tracking
    error_message TEXT,
    retry_count INT DEFAULT 0,

    -- Cloud Tasks integration
    task_name VARCHAR(255),

    -- Timing
    queued_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    started_at TIMESTAMPTZ,
    completed_at TIMESTAMPTZ,

    -- Timestamps
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_jobs_user ON jobs(user_id);
CREATE INDEX idx_jobs_status ON jobs(status);
CREATE INDEX idx_jobs_type ON jobs(job_type);
CREATE INDEX idx_jobs_task ON jobs(task_name);

-- =============================================================================
-- TABLE: sources
-- =============================================================================

CREATE TABLE sources (
    -- Identity
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,

    -- Source type
    source_type VARCHAR(20) NOT NULL,

    -- Email source fields
    gmail_message_id VARCHAR(255),
    email_subject TEXT,
    email_from VARCHAR(255),
    email_date TIMESTAMPTZ,

    -- Screenshot source fields
    image_hash VARCHAR(64),
    image_url TEXT,

    -- Processing status
    processed BOOLEAN DEFAULT FALSE,
    order_id UUID REFERENCES orders(id) ON DELETE SET NULL,

    -- Timestamps
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_sources_user ON sources(user_id);
CREATE INDEX idx_sources_type ON sources(source_type);
CREATE INDEX idx_sources_gmail ON sources(gmail_message_id);
CREATE INDEX idx_sources_image_hash ON sources(image_hash);
CREATE INDEX idx_sources_order ON sources(order_id);

-- =============================================================================
-- TABLE: interventions
-- =============================================================================

CREATE TABLE interventions (
    -- Identity
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    order_id UUID REFERENCES orders(id) ON DELETE CASCADE,

    -- Intervention details
    intervention_type VARCHAR(50) NOT NULL,
    priority VARCHAR(20) NOT NULL DEFAULT 'medium',
    status VARCHAR(50) NOT NULL DEFAULT 'pending',

    -- Content
    title VARCHAR(255) NOT NULL,
    message TEXT NOT NULL,
    recommended_actions JSONB DEFAULT '[]',

    -- Context
    context JSONB DEFAULT '{}',
    reasoning TEXT,

    -- Timing
    triggered_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    scheduled_for TIMESTAMPTZ,
    sent_at TIMESTAMPTZ,
    seen_at TIMESTAMPTZ,
    acted_on_at TIMESTAMPTZ,

    -- Delivery
    delivery_channels JSONB DEFAULT '[]',
    delivered BOOLEAN DEFAULT FALSE,

    -- Metadata
    expires_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_interventions_user ON interventions(user_id);
CREATE INDEX idx_interventions_order ON interventions(order_id);
CREATE INDEX idx_interventions_status ON interventions(status);
CREATE INDEX idx_interventions_priority ON interventions(priority, triggered_at);
CREATE INDEX idx_interventions_scheduled ON interventions(scheduled_for) WHERE status = 'pending';

-- =============================================================================
-- TRIGGER FUNCTION: update_updated_at_column
-- =============================================================================

CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ language 'plpgsql';

-- =============================================================================
-- TRIGGERS: Apply updated_at trigger to all tables
-- =============================================================================

CREATE TRIGGER update_users_updated_at BEFORE UPDATE ON users
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_merchants_updated_at BEFORE UPDATE ON merchants
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_orders_updated_at BEFORE UPDATE ON orders
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_shipments_updated_at BEFORE UPDATE ON shipments
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_policies_updated_at BEFORE UPDATE ON policies
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_jobs_updated_at BEFORE UPDATE ON jobs
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_sources_updated_at BEFORE UPDATE ON sources
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_interventions_updated_at BEFORE UPDATE ON interventions
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

COMMIT;

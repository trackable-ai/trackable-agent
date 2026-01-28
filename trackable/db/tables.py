"""
SQLAlchemy Table definitions for Trackable database.

These Table objects mirror the schema defined in migrations/001_initial_schema.sql.
Uses SQLAlchemy Core (not ORM) for flexibility with Pydantic models.
"""

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    ForeignKey,
    Integer,
    MetaData,
    Numeric,
    String,
    Table,
    Text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID

metadata = MetaData()

# =============================================================================
# TABLE: users
# =============================================================================

users = Table(
    "users",
    metadata,
    Column("id", UUID, primary_key=True),
    Column("email", String(255), unique=True, nullable=False),
    Column("name", String(255)),
    Column("status", String(20), nullable=False, default="active"),
    Column("preferences", JSONB, default={}),
    Column("total_orders", Integer, default=0),
    Column("active_orders", Integer, default=0),
    Column("missed_return_windows", Integer, default=0),
    Column("created_at", DateTime(timezone=True), nullable=False),
    Column("updated_at", DateTime(timezone=True), nullable=False),
    Column("last_login", DateTime(timezone=True)),
)

# =============================================================================
# TABLE: merchants
# =============================================================================

merchants = Table(
    "merchants",
    metadata,
    Column("id", UUID, primary_key=True),
    Column("name", String(255), nullable=False),
    Column("domain", String(255), unique=True),
    Column("aliases", JSONB, default=[]),
    Column("support_email", String(255)),
    Column("support_url", Text),
    Column("return_portal_url", Text),
    Column("created_at", DateTime(timezone=True), nullable=False),
    Column("updated_at", DateTime(timezone=True), nullable=False),
)

# =============================================================================
# TABLE: orders
# =============================================================================

orders = Table(
    "orders",
    metadata,
    Column("id", UUID, primary_key=True),
    Column("user_id", UUID, ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
    Column("merchant_id", UUID, ForeignKey("merchants.id"), nullable=False),
    Column("order_number", String(255), nullable=False),
    Column("order_date", DateTime(timezone=True)),
    Column("status", String(50), nullable=False, default="detected"),
    Column("country_code", String(2)),
    # Items and pricing (JSONB)
    Column("items", JSONB, nullable=False, default=[]),
    Column("subtotal", JSONB),
    Column("tax", JSONB),
    Column("shipping_cost", JSONB),
    Column("total", JSONB),
    # Return/exchange window tracking
    Column("return_window_start", DateTime(timezone=True)),
    Column("return_window_end", DateTime(timezone=True)),
    Column("return_window_days", Integer),
    Column("exchange_window_end", DateTime(timezone=True)),
    Column("is_monitored", Boolean, default=True),
    # Source tracking
    Column("source_type", String(20), nullable=False),
    Column("source_id", String(255)),
    # Agent metadata
    Column("confidence_score", Numeric(3, 2)),
    Column("needs_clarification", Boolean, default=False),
    Column("clarification_questions", JSONB, default=[]),
    # URLs
    Column("order_url", Text),
    Column("receipt_url", Text),
    # Refund tracking
    Column("refund_initiated", Boolean, default=False),
    Column("refund_amount", JSONB),
    Column("refund_completed_at", DateTime(timezone=True)),
    # Notes
    Column("notes", JSONB, default=[]),
    Column("last_agent_intervention", DateTime(timezone=True)),
    # Timestamps
    Column("created_at", DateTime(timezone=True), nullable=False),
    Column("updated_at", DateTime(timezone=True), nullable=False),
)

# =============================================================================
# TABLE: shipments
# =============================================================================

shipments = Table(
    "shipments",
    metadata,
    Column("id", UUID, primary_key=True),
    Column(
        "order_id", UUID, ForeignKey("orders.id", ondelete="CASCADE"), nullable=False
    ),
    Column("tracking_number", String(255)),
    Column("carrier", String(50), nullable=False, default="unknown"),
    Column("status", String(50), nullable=False, default="pending"),
    Column("shipping_address", Text),
    Column("return_address", Text),
    Column("shipped_at", DateTime(timezone=True)),
    Column("estimated_delivery", DateTime(timezone=True)),
    Column("delivered_at", DateTime(timezone=True)),
    Column("tracking_url", Text),
    Column("events", JSONB, default=[]),
    Column("last_updated", DateTime(timezone=True)),
    Column("created_at", DateTime(timezone=True), nullable=False),
    Column("updated_at", DateTime(timezone=True), nullable=False),
)

# =============================================================================
# TABLE: policies
# =============================================================================

policies = Table(
    "policies",
    metadata,
    Column("id", UUID, primary_key=True),
    Column("merchant_id", UUID, ForeignKey("merchants.id"), nullable=False),
    Column("policy_type", String(50), nullable=False),
    Column("country_code", String(2), nullable=False),
    Column("name", String(255), nullable=False),
    Column("description", Text),
    Column("version", String(50)),
    Column("effective_date", DateTime(timezone=True)),
    Column("return_policy", JSONB),
    Column("exchange_policy", JSONB),
    Column("source_url", Text),
    Column("raw_text", Text),
    Column("confidence_score", Numeric(3, 2)),
    Column("last_verified", DateTime(timezone=True)),
    Column("needs_verification", Boolean, default=False),
    Column("interpretation_notes", JSONB, default=[]),
    Column("created_at", DateTime(timezone=True), nullable=False),
    Column("updated_at", DateTime(timezone=True), nullable=False),
)

# =============================================================================
# TABLE: jobs
# =============================================================================

jobs = Table(
    "jobs",
    metadata,
    Column("id", UUID, primary_key=True),
    Column("user_id", UUID, ForeignKey("users.id", ondelete="CASCADE")),
    Column("job_type", String(50), nullable=False),
    Column("status", String(50), nullable=False, default="queued"),
    Column("input_data", JSONB, default={}),
    Column("output_data", JSONB, default={}),
    Column("error_message", Text),
    Column("retry_count", Integer, default=0),
    Column("task_name", String(255)),
    Column("queued_at", DateTime(timezone=True), nullable=False),
    Column("started_at", DateTime(timezone=True)),
    Column("completed_at", DateTime(timezone=True)),
    Column("created_at", DateTime(timezone=True), nullable=False),
    Column("updated_at", DateTime(timezone=True), nullable=False),
)

# =============================================================================
# TABLE: sources
# =============================================================================

sources = Table(
    "sources",
    metadata,
    Column("id", UUID, primary_key=True),
    Column("user_id", UUID, ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
    Column("source_type", String(20), nullable=False),
    # Email source fields
    Column("gmail_message_id", String(255)),
    Column("email_subject", Text),
    Column("email_from", String(255)),
    Column("email_date", DateTime(timezone=True)),
    # Screenshot source fields
    Column("image_hash", String(64)),
    Column("image_url", Text),
    # Processing status
    Column("processed", Boolean, default=False),
    Column("order_id", UUID, ForeignKey("orders.id", ondelete="SET NULL")),
    Column("created_at", DateTime(timezone=True), nullable=False),
    Column("updated_at", DateTime(timezone=True), nullable=False),
)

# =============================================================================
# TABLE: interventions
# =============================================================================

interventions = Table(
    "interventions",
    metadata,
    Column("id", UUID, primary_key=True),
    Column("user_id", UUID, ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
    Column("order_id", UUID, ForeignKey("orders.id", ondelete="CASCADE")),
    Column("intervention_type", String(50), nullable=False),
    Column("priority", String(20), nullable=False, default="medium"),
    Column("status", String(50), nullable=False, default="pending"),
    Column("title", String(255), nullable=False),
    Column("message", Text, nullable=False),
    Column("recommended_actions", JSONB, default=[]),
    Column("context", JSONB, default={}),
    Column("reasoning", Text),
    Column("triggered_at", DateTime(timezone=True), nullable=False),
    Column("scheduled_for", DateTime(timezone=True)),
    Column("sent_at", DateTime(timezone=True)),
    Column("seen_at", DateTime(timezone=True)),
    Column("acted_on_at", DateTime(timezone=True)),
    Column("delivery_channels", JSONB, default=[]),
    Column("delivered", Boolean, default=False),
    Column("expires_at", DateTime(timezone=True)),
    Column("created_at", DateTime(timezone=True), nullable=False),
    Column("updated_at", DateTime(timezone=True), nullable=False),
)

# =============================================================================
# TABLE: oauth_tokens
# =============================================================================

oauth_tokens = Table(
    "oauth_tokens",
    metadata,
    Column("id", UUID, primary_key=True),
    Column("user_id", UUID, ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
    # Provider info
    Column("provider", String(50), nullable=False),
    Column("provider_email", String(255)),
    # Tokens
    Column("access_token", Text, nullable=False),
    Column("refresh_token", Text),
    Column("token_type", String(50), default="Bearer"),
    # Token metadata
    Column("scope", Text),
    Column("expires_at", DateTime(timezone=True)),
    # Provider-specific metadata (Gmail)
    Column("last_sync", DateTime(timezone=True)),
    Column("last_history_id", String(255)),
    Column("watch_expiration", DateTime(timezone=True)),
    # Timestamps
    Column("created_at", DateTime(timezone=True), nullable=False),
    Column("updated_at", DateTime(timezone=True), nullable=False),
)

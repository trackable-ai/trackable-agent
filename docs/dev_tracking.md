# Trackable Development Tracking

**Status**: In Progress
**Last Updated**: 2026-01-26

## Overview

This document tracks the implementation progress of the Trackable Personal Shopping Agent backend service.

**For architecture and design details, see:**

- [design.md](./design.md) - Architecture decisions and data flows
- [database_schema.md](./database_schema.md) - Database design
- [worker_service.md](./worker_service.md) - Worker service documentation
- [deployment.md](./deployment.md) - Deployment guide
- [PRD.md](./PRD.md) - Product requirements
- [../CLAUDE.md](../CLAUDE.md) - Development guide for Claude Code

## Progress Tracking

### ✅ Completed

#### Foundation & Infrastructure

- [x] Directory structure (`trackable/api/`, `trackable/worker/`, `trackable/agents/`, `trackable/models/`)
- [x] Dependencies added to `pyproject.toml`
- [x] Database schema design (`docs/database_schema.md`) - 8 tables
- [x] Migration scripts (`migrations/001_initial_schema.sql`)
- [x] Successfully applied migration to Cloud SQL instance
- [x] IAM authentication configured with service account

#### Data Models

- [x] Core Pydantic models (`trackable/models/`)
    - `order.py` - Order, Merchant, Item, Shipment, Money
    - `policy.py` - Policy, ReturnRule, ExchangeRule
    - `user.py` - User, UserPreferences
    - `intervention.py` - Intervention
    - `job.py` - Job tracking for Cloud Tasks
    - `source.py` - Email/screenshot sources
    - `task.py` - Cloud Tasks payload models
    - `oauth.py` - OAuth token storage

#### Agents

- [x] **Input Processor Agent** (`trackable/agents/input_processor.py`)
    - Email and image processing with internal routing
    - Structured output with ExtractedOrderData
    - Helper function to convert to Order models
    - Vision-capable (gemini-2.5-flash)
    - Comprehensive tests (9 passing tests)
- [x] **Chatbot Agent** (`trackable/agents/chatbot.py`)
    - Vanilla chat agent using Google ADK

#### Ingress Service (API)

- [x] **FastAPI Application** (`trackable/api/`)
    - Health check endpoint
    - Chat API endpoint (OpenAI-compatible):
        - `POST /api/v1/chat/completions` - Supports streaming and non-streaming
    - Ingest API endpoints (`trackable/api/routes/ingest.py`):
        - `POST /api/v1/ingest/email` - Manual email submission
        - `POST /api/v1/ingest/image` - Manual screenshot submission
    - Cloud Tasks client (`trackable/api/cloud_tasks.py`):
        - Creates parse-email tasks for Worker service
        - Creates parse-image tasks for Worker service
        - Supports local development mode (no GCP required)
    - CORS configuration for frontend access
    - Dockerfile for Cloud Run deployment
    - Successfully tested locally (12 ingest tests passing)
    - API usage examples documented
    - Order management APIs (`trackable/api/routes/orders.py`):
        - `GET /api/v1/orders` - List user orders with filtering/pagination
        - `GET /api/v1/orders/{id}` - Get order details
        - `PATCH /api/v1/orders/{id}` - Update order (status, notes, monitoring)
        - `DELETE /api/v1/orders/{id}` - Delete order
    - 15 order API tests passing
    - Pub/Sub handlers (`trackable/api/routes/pubsub.py`):
        - `POST /pubsub/gmail` - Gmail notification handler (creates Job record)
        - `POST /pubsub/policy` - Policy refresh trigger (creates Job records per merchant)
    - Cloud Tasks client extended with `create_gmail_sync_task()` and `create_policy_refresh_task()`
    - Job tracking for Pub/Sub triggered tasks (GMAIL_SYNC, POLICY_REFRESH types)
    - 15 Pub/Sub handler tests passing

#### Worker Service

- [x] **FastAPI Application** (`trackable/worker/`)
    - Health check endpoint
    - Cloud Tasks endpoints:
        - `POST /tasks/gmail-sync` - Gmail sync task
        - `POST /tasks/parse-email` - Email parsing task
        - `POST /tasks/parse-image` - Screenshot parsing task
        - `POST /tasks/test` - Test endpoint for local development
    - Task handlers with input processor agent integration
    - MIME type auto-detection for images
    - Dockerfile for Cloud Run deployment
    - Comprehensive tests with real samples (email + screenshot)
    - Worker service documentation

#### Documentation

- [x] `docs/design.md` - Architecture and data flows
- [x] `docs/database_schema.md` - Database design
- [x] `docs/deployment.md` - Cloud Run deployment guide
- [x] `docs/worker_service.md` - Worker service documentation
- [x] `docs/api_examples.md` - API usage examples
- [x] `docs/openapi.yaml` - OpenAPI specification
- [x] `CLAUDE.md` - Development guide

#### Cloud Infrastructure

- [x] Cloud Tasks queue (`order-parsing-tasks`) in GCP Console
- [x] IAM permissions for service-to-service authentication
- [x] Retry policies (3 attempts, exponential backoff)

#### Deployment

- [x] Cloud Run Deployment
    - Deploy Ingress service
    - Deploy Worker service
    - Configure environment variables and secrets
    - Set up service-to-service IAM authentication
    - GitHub + Cloud Build CD integration

#### API Refactoring

- [x] Refactored chat APIs to OpenAI-compatible format (`trackable/api/routes/chat.py`)
    - `POST /api/v1/chat/completions` - OpenAI-compatible endpoint
    - Request format: `{model, messages: [{role, content}], stream?, temperature?}`
    - Response format: `{id, choices: [{message, finish_reason}], usage}`
    - Streaming format: `data: {"choices": [{"delta": {"content": "..."}}]}`
    - Models in `trackable/models/chat.py`

#### Data Access Layer

- [x] **SQLAlchemy Core + Repository Pattern** (`trackable/db/`)
    - `connection.py` - Cloud SQL connection pool with IAM auth
    - `tables.py` - SQLAlchemy Table definitions (9 tables)
    - `unit_of_work.py` - Transaction coordination
    - Repositories:
        - `base.py` - Generic CRUD operations, JSONB helpers
        - `merchant.py` - Upsert by domain
        - `job.py` - Status tracking (mark started/completed/failed)
        - `source.py` - Duplicate detection by gmail_message_id or image_hash
        - `order.py` - Order CRUD with JSONB items/money
        - `shipment.py` - Shipment tracking events
        - `oauth_token.py` - OAuth token storage and refresh
- [x] Database initialization in `worker/main.py` and `api/main.py`
- [x] Refactored `worker/handlers.py` to use repositories
    - Save parsed orders to database
    - Update job status in real-time
    - Duplicate image detection via SHA-256 hash
- [x] Updated `api/routes/ingest.py` to use repositories
    - Creates Job and Source records before Cloud Task
    - Early duplicate image detection in API
    - Utility function `compute_sha256` in `trackable/utils/hash.py`
- [x] Integration tests (`tests/integration/test_db_integration.py`)
    - Repository CRUD operations
    - Merchant upsert by domain
    - Job status lifecycle
    - Order with nested items
    - Full email ingest workflow

### 🔄 In Progress

(No tasks currently in progress)

### ⏸️ Not Started

#### Authentication & Session Management

- [ ] Implement user authentication
    - [ ] JWT/OIDC token validation middleware
    - [ ] Extract `user_id` from authentication token (replace hardcoded parameter)
    - [ ] Session management for chat conversations
- [ ] Update API routes to use authenticated user
    - [ ] `trackable/api/routes/orders.py` - Remove `user_id` parameter
    - [ ] `trackable/api/routes/ingest.py` - Remove `user_id` parameter
    - [ ] `trackable/api/routes/chat.py` - Remove `user_id` parameter
- [ ] User registration/login flow (if self-hosted auth)

#### Chatbot Enhancement

- [ ] Extend chatbot agent (`trackable/agents/chatbot.py`)
    - Query and explore user orders
    - Check order status and delivery information
    - Calculate return/exchange time windows
    - Query merchant return policies
    - Answer questions about specific orders
    - Provide personalized recommendations

#### Worker Service - Additional Task Handlers

- [ ] Gmail sync handler (`trackable/worker/handlers.py`)
    - [ ] Implement `handle_gmail_sync()` function
    - [ ] Gmail API integration with incremental sync
    - [ ] Email filtering for order confirmations
    - [ ] Batch processing of multiple emails
- [ ] Policy refresh handler (`trackable/worker/handlers.py`)
    - [ ] Implement `handle_policy_refresh()` function
    - [ ] Web scraping for merchant policy pages
    - [ ] Policy parsing and extraction
    - [ ] Hash-based change detection

#### Integration & Testing

- [ ] Gmail API Setup
    - [ ] OAuth 2.0 flow for user Gmail authorization
    - [ ] Gmail Pub/Sub watch setup for push notifications
    - [ ] History ID-based incremental sync
- [ ] End-to-End Workflow Tests (`tests/integration/`)
    - [x] Database repository integration tests (completed)
    - [ ] Test Gmail notification → Worker → Database flow
    - [ ] Test manual submission → Worker → Database flow
    - [ ] Test policy refresh → Worker → Database flow
    - [ ] Test chatbot querying database for orders
- [ ] Cloud Infrastructure Setup
    - [ ] Set up dead letter queue for failed tasks
    - [ ] Configure Cloud Scheduler for policy refresh (daily/weekly)

#### Deployment & Operations

- [ ] Monitoring & Observability
    - [ ] Cloud Logging setup and log analysis
    - [ ] Cloud Monitoring dashboards
    - [ ] Alerts for error rates and latency
    - [ ] Dead letter queue monitoring

## Recent Updates

### 2026-01-26

- ✅ Implemented Pub/Sub handlers (`trackable/api/routes/pubsub.py`)
    - `POST /pubsub/gmail` - Gmail notification handler (decodes notification, looks up user by email, creates Job record, creates Cloud Task)
    - `POST /pubsub/policy` - Policy refresh trigger (lists merchants, creates Job records, creates Cloud Tasks with staggered delays)
    - Creates Job records (GMAIL_SYNC / POLICY_REFRESH) to track async processing
    - Returns job_id(s) in response for tracking
    - Pub/Sub message models (`trackable/models/pubsub.py`)
    - Cloud Tasks creators: `create_gmail_sync_task()`, `create_policy_refresh_task()`
    - Added `get_by_provider_email()` to OAuthTokenRepository for user lookup
    - Added `list_all()` to MerchantRepository for policy refresh
    - 15 Pub/Sub handler tests passing
- ✅ Implemented Order Management APIs (`trackable/api/routes/orders.py`)
    - `GET /api/v1/orders` - List with status filter and pagination
    - `GET /api/v1/orders/{id}` - Get order details
    - `PATCH /api/v1/orders/{id}` - Update status, add notes, toggle monitoring
    - `DELETE /api/v1/orders/{id}` - Delete order
    - User-scoped queries with `get_by_id_for_user()` for security
    - Request/response models: `OrderListResponse`, `OrderUpdateRequest`
    - 15 unit tests with mocked database layer
- ✅ Implemented Data Access Layer (`trackable/db/`)
    - SQLAlchemy Core with Repository Pattern
    - Cloud SQL connection pool with IAM authentication
    - Unit of Work for transaction coordination
    - 6 repositories: Merchant, Job, Source, Order, Shipment, OAuthToken
    - JSONB helpers for Pydantic model serialization
    - DB initialization in FastAPI lifespan for both services
    - Refactored worker handlers to persist orders and track jobs
    - Updated ingest API to create Job/Source before Cloud Tasks
    - Early duplicate image detection in ingest API
- ✅ Added OAuth token storage (`oauth_tokens` table)
    - Replaces `gmail_connection` JSONB in users table
    - Stores access_token, refresh_token, scope, expires_at
    - Gmail sync metadata: last_sync, last_history_id, watch_expiration
    - OAuthTokenRepository with upsert and token refresh methods
- ✅ Schema improvements
    - Made `user_id` NOT NULL in orders and sources tables
    - Added unique constraint on merchants.domain
    - Migration 003: oauth_tokens table + schema fixes
- ✅ Integration tests for database operations
    - Tests for all repositories (merchant, job, source, order)
    - Full workflow test (job → source → order lifecycle)
    - Auto-grant postgres user access after migrations
- ✅ Refactored chat APIs to OpenAI-compatible format
    - New endpoint: `POST /api/v1/chat/completions`
    - OpenAI-compatible request/response models (`trackable/models/chat.py`)
    - Streaming support with `data: {"choices": [{"delta": {...}}]}` format
    - Updated tests for new API format
- ✅ Completed Cloud Run deployment with GitHub + Cloud Build CD
- ✅ Configured Cloud Tasks retry policies

### 2026-01-25

- ✅ Created comprehensive development guide (`CLAUDE.md`)
- ✅ Completed Worker service implementation
    - All Cloud Tasks endpoints implemented and tested
    - Real sample data testing (Amazon email + screenshot)
    - Vision capabilities working correctly
    - Documentation completed
- ✅ Refactored `dev_tracking.md` to focus on progress tracking only
    - Moved architecture details to other documentation
    - Organized progress into clear categories
    - Added structured "Not Started" section for remaining work
    - Removed out-of-scope items (carrier tracking tools, main orchestrator agent)
    - Clarified chatbot enhancement approach
    - Detailed remaining work by functional area
- ✅ Implemented Ingest API endpoints and Cloud Tasks integration
    - `POST /api/v1/ingest/email` - Manual email submission
    - `POST /api/v1/ingest/image` - Manual screenshot submission
    - Cloud Tasks client (`trackable/api/cloud_tasks.py`)
        - Auto-detects service account from credentials
        - Auto-detects project number via Cloud Resource Manager API
        - Builds Worker service URL: `https://{name}-{project-number}.{location}.run.app`
        - Local development mode (skips task creation when no PROJECT_ID)
    - Request/response models (`trackable/models/ingest.py`)
    - 12 tests passing for ingest endpoints
    - Added `google-cloud-tasks` and `google-cloud-resource-manager` dependencies
- ✅ Created Cloud Tasks queue (`order-parsing-tasks`) in GCP
    - Configured in `us-central1` region
    - Granted `roles/cloudtasks.enqueuer` to service account

# Trackable Development Tracking

**Status**: In Progress
**Last Updated**: 2026-02-01

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
    - Google ADK agent with database-backed tools
    - 5 custom tools for order/merchant queries (`trackable/agents/tools/`)
    - `get_user_orders` - List/filter orders by status
    - `get_order_details` - Full order detail with items, shipments, pricing
    - `check_return_windows` - Find orders with expiring return deadlines
    - `get_merchant_info` - Merchant support info and return portal lookup
    - `search_order_by_number` - Find order by merchant order number
    - `search_orders` - Fuzzy search orders by item name, merchant, or order number
    - User_id injection in chat API for tool context
    - `OrderRepository.search()` with JOIN + ILIKE across order numbers, merchant names, and item names (JSONB `jsonb_array_elements`)
    - 6 integration tests for search (item name, merchant name, order number, case-insensitive, empty, user scoping)
    - 30 chatbot tool tests (unit + scenario)

#### Ingress Service (API)

- [x] **FastAPI Application** (`trackable/api/`)
    - Health check endpoint
    - Chat API endpoint (OpenAI-compatible):
        - `POST /api/v1/chat/completions` - Supports streaming and non-streaming
    - Ingest API endpoints (`trackable/api/routes/ingest.py`):
        - `POST /api/v1/ingest/email` - Manual email submission
        - `POST /api/v1/ingest/image` - Manual screenshot submission
        - `POST /api/v1/ingest/email/batch` - Batch email submission (max 50)
        - `POST /api/v1/ingest/image/batch` - Batch image submission (max 50)
    - Cloud Tasks client (`trackable/api/cloud_tasks.py`):
        - Creates parse-email tasks for Worker service
        - Creates parse-image tasks for Worker service
        - Supports local development mode (no GCP required)
    - CORS configuration for frontend access
    - Dockerfile for Cloud Run deployment
    - Successfully tested locally (23 ingest tests passing)
    - API usage examples documented
    - Order management APIs (`trackable/api/routes/orders.py`):
        - `GET /api/v1/orders` - List user orders with filtering/pagination/deduplication
        - `GET /api/v1/orders/{id}/latest` - Get latest order status
        - `GET /api/v1/orders/{id}/history` - Get full order timeline
        - `PATCH /api/v1/orders/{id}` - Update order (status, notes, monitoring)
        - `DELETE /api/v1/orders/{id}` - Delete order
    - 18 order API tests passing
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

#### Merchant Matching & Normalization

- [x] **Merchant matching and normalization** (`trackable/utils/merchant.py`, `trackable/db/repositories/merchant.py`)
    - Merchant name normalization utility with known merchant mappings
    - Domain normalization (removes www., shop., store. prefixes)
    - Automatic alias generation for fuzzy matching
    - `get_by_name_or_domain()` method for flexible lookup
    - Updated `upsert_by_domain()` to normalize names and store aliases
    - Migration 004: Added `aliases` JSONB column to merchants table
    - Updated Merchant model with `aliases` field
    - 45 unit tests for merchant utilities
    - 6 integration tests for normalization (11 total merchant tests)

#### Order Upsert & History Preservation

- [x] **Order upsert by order number** (`trackable/db/repositories/order.py`, `trackable/worker/handlers.py`)
    - `get_by_unique_key()` method to find orders by user_id + merchant_id + order_number + status
    - `upsert_by_order_number()` method: same status merges, different status creates new row
    - `_merge_orders()` method with intelligent data merging (within same status):
        - Notes appended (with deduplication)
        - Higher confidence score used
        - Items replaced with new data
        - Return windows preserved if already set
        - URLs and refund info updated
    - Updated worker handlers (`handle_parse_email`, `handle_parse_image`) to use upsert
    - Returns `is_new_order` flag in handler responses
    - Migration 005: Added NOT NULL constraint on `order_number` + unique constraint on `(user_id, merchant_id, order_number)`
    - Migration 006: Extended unique constraint to `(user_id, merchant_id, order_number, status)` for order history
    - Updated Order model to require `order_number` (no longer optional)
    - ValueError raised in `convert_extracted_to_order()` when order number cannot be extracted
- [x] **Order history preservation** (`trackable/db/repositories/order.py`, `trackable/api/routes/orders.py`)
    - Each status transition creates a new row, preserving full order timeline
    - `get_order_history()` - All status rows for an order, ordered by progression
    - `get_latest_order()` - Highest-status row for an order
    - `get_by_user()` with DISTINCT ON deduplication (returns latest status per order by default)
    - `get_by_order_number()` returns latest-status row
    - `include_history` param on `get_by_user()` and `count_by_user()` for full history
    - `OrderTimelineEntry` and `OrderHistoryResponse` response models
    - API endpoints:
        - `GET /api/v1/orders/{id}/history` - Full order timeline
        - `GET /api/v1/orders/{id}/latest` - Latest order status (replaces old `GET /orders/{id}`)
        - `GET /api/v1/orders?include_history=true` - List with all status rows
    - Index `idx_orders_latest_status` for efficient latest-status queries
    - 26 unit tests for repository, 18 API tests, 3 model tests
    - Integration tests updated for status-aware upsert semantics

### 🔄 In Progress

(No tasks currently in progress)

### ⏸️ Not Started

#### Authentication & Session Management

- [ ] Implement user authentication
    - [ ] JWT/OIDC token validation middleware
    - [ ] Extract `user_id` from authentication token (replace hardcoded parameter)
    - [ ] Session management for chat conversations
        - [ ] Support multiple sessions per user (current `_user_sessions` dict in `chat.py` only allows one session per user)
- [ ] Update API routes to use authenticated user
    - [ ] `trackable/api/routes/orders.py` - Remove `user_id` parameter
    - [ ] `trackable/api/routes/ingest.py` - Remove `user_id` parameter
    - [ ] `trackable/api/routes/chat.py` - Remove `user_id` parameter
- [ ] User registration/login flow (if self-hosted auth)

#### Chatbot Enhancement (Remaining)

- [ ] Query merchant return policies (requires PolicyRepository - not yet built)
- [ ] Provide personalized recommendations (requires order history analysis)

#### Ingress Service - Email Filtering

- [ ] Rule-based email filtering before Cloud Task creation (`trackable/api/`)
    - [ ] Filter by sender domain (whitelist known merchant domains)
    - [ ] Filter by subject line patterns (e.g., "order confirmation", "shipping notification")
    - [ ] Filter by email headers (e.g., `X-Mailer`, `List-Unsubscribe`)
    - [ ] Skip promotional/marketing emails early
    - [ ] Configurable filter rules (database or config file)
    - [ ] Log filtered-out emails for debugging/tuning

#### Worker Service - Additional Task Handlers

- [ ] Handle non-order emails gracefully (`trackable/worker/handlers.py`)
    - [ ] Detect when input processor returns empty/no order data
    - [ ] Mark job as completed with appropriate status (e.g., "no_order_found")
    - [ ] Update source record to indicate non-order content
    - [ ] Avoid creating empty order records in database
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

### 2026-02-01

- ✅ **Order History Preservation** - Full order timeline tracking
    - Migration 006: Extended unique constraint to `(user_id, merchant_id, order_number, status)`
    - Each status transition creates a new row instead of overwriting
    - New repository methods: `get_order_history()`, `get_latest_order()`
    - `get_by_user()` deduplicates with DISTINCT ON by default
    - New API endpoints: `GET /orders/{id}/history`, `GET /orders/{id}/latest`
    - `GET /orders?include_history=true` returns all status rows
    - New models: `OrderTimelineEntry`, `OrderHistoryResponse`
    - Updated merge logic to only merge within same-status rows
    - 167 unit tests passing, integration tests updated
    - Fixed: Test helper now uses `Decimal` instead of strings for Money amounts (type correctness)
    - Updated OpenAPI spec with new endpoints and schemas (`/latest`, `/history`, `OrderTimelineEntry`, `OrderHistoryResponse`)
- ✅ Added integration tests for `OrderRepository.search()` — 6 tests covering item name, merchant name, order number, case-insensitivity, empty results, and user scoping
- ✅ **Fuzzy Order Search** - Added `search_orders` tool and `OrderRepository.search()` for fuzzy matching
    - `search_orders` tool: fuzzy search by item name, merchant name, or order number
    - `OrderRepository.search()`: JOINs orders+merchants, ILIKE on order_number/merchant name/item names via `jsonb_array_elements`
    - Updated chatbot agent instructions to prefer `search_orders` for natural language queries (e.g., "my MacBook order", "Nike shoes")
    - 7 new tests: 3 unit tests, 2 scenario tests, 1 tool registration test, 1 chatbot wiring test
    - Total: 171 passing tests (+ 1 pre-existing integration failure)
- ✅ **Chatbot Enhancement** - Added database-backed tools to chatbot agent (`trackable/agents/chatbot.py`, `trackable/agents/tools/`)
    - Created `trackable/agents/tools/` package with 5 tool functions:
        - `get_user_orders` - List/filter user orders by status with pagination
        - `get_order_details` - Full order detail with items, shipments, pricing, return windows
        - `check_return_windows` - Find orders with expiring return deadlines, calculates days remaining
        - `get_merchant_info` - Look up merchant support info and return portal URLs
        - `search_order_by_number` - Find order by merchant-assigned order number
    - Tools use `UnitOfWork` pattern for database queries (read-only)
    - Google ADK auto-wraps plain Python functions as `FunctionTool` objects
    - Updated chatbot agent instructions with tool usage guidance
    - Injected `user_id` context into chat prompts for tool parameter passing
    - 23 new tests: 16 tool unit tests, 3 scenario tests, 2 wiring tests, 2 user_id injection tests

### 2026-01-28

- ✅ Implemented order upsert by order number (`trackable/db/repositories/order.py`, `trackable/worker/handlers.py`)
    - `get_by_unique_key()` method to find orders by user_id + merchant_id + order_number
    - `upsert_by_order_number()` method to insert or update existing orders
    - Intelligent merge logic: status progression (never regresses), notes deduplication, higher confidence used
    - Items replaced, return windows preserved, URLs and refund info updated
    - Updated worker handlers (`handle_parse_email`, `handle_parse_image`) to use upsert
    - Migration 005: Added NOT NULL constraint on order_number + unique constraint on (user_id, merchant_id, order_number)
    - Updated Order model to require order_number (no longer optional)
    - ValueError raised when order number cannot be extracted from source
    - 17 unit tests for merge logic, 4 integration tests for upsert
    - Total: 129 unit tests + 16 integration tests passing
- ✅ Implemented merchant matching and normalization (`trackable/utils/merchant.py`, `trackable/db/repositories/merchant.py`)
    - Merchant name normalization utility with 50+ known merchant mappings (Amazon, Nike, Target, etc.)
    - Domain normalization (removes www., shop., store. prefixes, lowercases)
    - Automatic alias generation for fuzzy matching (handles spaces, hyphens, apostrophes, ampersands)
    - `get_by_name_or_domain()` method for flexible lookup by name, domain, or alias
    - Updated `upsert_by_domain()` to normalize names and generate/store aliases
    - Migration 004: Added `aliases` JSONB column to merchants table with GIN index
    - Updated Merchant model with `aliases` field
    - Updated worker handlers to use normalized merchant creation
    - 45 unit tests for merchant utilities (all passing)
    - 6 integration tests for merchant normalization (11 total)
- 📝 Added TODO: Rule-based email filtering in ingress service before creating Cloud Tasks
- 📝 Added TODO: Handle non-order emails gracefully in worker handlers (detect empty results, mark job appropriately, avoid empty records)

### 2026-01-27

- ✅ Implemented batch ingest endpoints (`trackable/api/routes/ingest.py`)
    - `POST /api/v1/ingest/email/batch` - Submit multiple emails (max 50 items)
    - `POST /api/v1/ingest/image/batch` - Submit multiple images (max 50 items)
    - Partial success handling (individual failures don't block other items)
    - Per-item transaction isolation
    - New models: `BatchEmailItem`, `BatchImageItem`, `IngestBatchEmailRequest`, `IngestBatchImageRequest`, `BatchItemResult`, `IngestBatchResponse`, `BatchItemStatus`
    - Refactored existing endpoints to use shared helper functions
    - 11 new tests for batch endpoints (23 total ingest tests)
    - All 66 tests passing

### 2026-01-26

- 📝 Added TODO: Support multiple chat sessions per user (current implementation only allows one session)
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

# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Trackable is a Personal Shopping Agent for post-purchase management. It runs on **Google Cloud Platform** using a **two-service Cloud Run architecture**:

- **Ingress Service** (`trackable/api/`): API routing, Pub/Sub handlers, chatbot interface, Cloud Tasks creation
- **Worker Service** (`trackable/worker/`): Async job processing for order parsing and policy extraction

The system uses **Cloud Tasks** for async job processing, **Cloud SQL (PostgreSQL)** for data storage, and **Google Agent Development Kit (ADK)** with Gemini models for AI capabilities.

## Progress Tracking

- Always refer to [dev_tracking.md](../docs/dev_tracking.md) for the progress.
- Three status: Completed, In Progress, Not Started
- Always add new TODOs to the progress tracking file in time
- Always update the task status once tasks are complete or in progress
- Always move completed or pending tasks to the correct sections

## Essential Commands

### Project Setup

```bash
# Install dependencies (creates virtual environment)
uv sync

# Set up environment variables
cp .env.example .env
# Edit .env with your configuration (Google AI Studio API key OR Vertex AI)
```

### Dependency Management

**Always use `uv add` to add new dependencies** - never manually edit `pyproject.toml`:

```bash
# Add a new dependency
uv add <package-name>

# Add a dev dependency
uv add --dev <package-name>

# Remove a dependency
uv remove <package-name>
```

### Running Services Locally

```bash
# Run ADK agent in CLI
adk run trackable

# Run ADK agent with web UI
adk web

# Run Ingress API service (port 8080)
uv run uvicorn trackable.api.main:app --reload --port 8080

# Run Worker service (port 8081)
uv run uvicorn trackable.worker.main:app --reload --port 8081
```

### Testing

```bash
# Run all tests (excludes tests marked as 'manual')
uv run pytest .

# Run only manual tests (LLM-dependent tests)
uv run pytest -m manual

# Run specific test file
uv run pytest tests/worker/test_tasks.py -v

# Run with coverage
uv run pytest --cov=trackable --cov-report=html
```

### Code Formatting

```bash
# Format Python code with black
uv run black .

# Sort Python imports with isort
uv run isort .
```

### Database Operations

```bash
# Run database migrations
uv run python scripts/run_migration.py migrations/001_initial_schema.sql

# Connect to Cloud SQL directly (requires IAM auth)
gcloud sql connect trackable-db --user=postgres --database=trackable
```

### Deployment

```bash
# Deploy Ingress service to Cloud Run
# ./scripts/deploy_ingress.sh
# I will manually deploy the service

# Deploy Worker service to Cloud Run
# ./scripts/deploy_worker.sh
# I will manually deploy the service

# Test deployed service (internal - requires auth token)
TOKEN=$(gcloud auth print-identity-token)
SERVICE_URL=$(gcloud run services describe trackable-ingress --region us-central1 --format 'value(status.url)')
curl -H "Authorization: Bearer $TOKEN" $SERVICE_URL/health
```

## Architecture Overview

### Two-Service Pattern

**Ingress Service** responsibilities:

- Handle HTTP API requests from frontend
- Process Pub/Sub push notifications (Gmail, Cloud Scheduler)
- Create Cloud Tasks for async processing
- Provide chatbot interface with streaming SSE
- CRUD operations on orders, policies, users

**Worker Service** responsibilities:

- Process Cloud Tasks asynchronously
- Execute heavy LLM operations (order parsing, policy extraction)
- Update database with parsed results
- Handle retries and failures

### Three Data Flows

1. **Gmail Notification (Automatic)**: Gmail → Pub/Sub → Ingress → Cloud Task (`gmail_sync`) → Worker → Parse emails → Database

2. **Manual Submission**: User uploads email/screenshot → Ingress → Create Job → Cloud Task (`parse_email`/`parse_image`) → Worker → Parse → Database

3. **Policy Refresh (Scheduled)**: Cloud Scheduler → Pub/Sub → Ingress → Cloud Task (`policy_refresh`) → Worker → Crawl/parse policy → Database

### Google ADK Agent Pattern

Agents are created using `google.adk.agents.llm_agent.Agent`:

```python
from google.adk.agents.llm_agent import Agent
from google.adk.runners import InMemoryRunner

# Define agent
agent = Agent(
    name="agent_name",
    description="Brief description",
    instruction="Detailed instructions...",
    model="gemini-2.5-flash",
    output_schema=OutputModel,  # Pydantic model for structured output
)

# Run agent
runner = InMemoryRunner(agent=agent, app_name="app-name")
session = await runner.session_service.create_session(...)
async for event in runner.run_async(...):
    # Process streaming events
```

**Important**: To extract agent output, iterate through `event.content.parts` and collect text:

```python
result_text = ""
async for event in runner.run_async(...):
    if event.content and event.content.parts:
        for part in event.content.parts:
            if part.text:
                result_text = part.text

result = json.loads(result_text)  # Parse JSON response
```

### Vision Capabilities

Gemini 2.5 Flash has built-in vision. To process images, create a `Part` with `inline_data`:

```python
from google.genai.types import Blob, Content, Part

# Detect MIME type from image bytes
mime_type = detect_image_mime_type(image_bytes)

# Create content with text prompt + image
parts = [
    Part(text="Extract order information from this image..."),
    Part(inline_data=Blob(data=image_bytes, mime_type=mime_type))
]
content = Content(parts=parts)

# Send to agent
async for event in runner.run_async(new_message=content):
    ...
```

## Code Organization Principles

### Model Location

**All Pydantic models must go in the `trackable/models/` directory**, not in route files or handlers.

Structure:

- `models/order.py` - Order, Merchant, Item, Shipment, etc.
- `models/policy.py` - Policy, ReturnRule, ExchangeRule
- `models/user.py` - User, GmailConnection, Preferences
- `models/task.py` - Cloud Tasks payload models
- `models/job.py` - Job tracking for async tasks
- `models/source.py` - Email/screenshot sources

### Test Data Management

Use **pytest-datadir** plugin with the `shared_datadir` fixture for test data:

```python
from pathlib import Path

@pytest.fixture(scope="module")
def sample_email_content(shared_datadir: Path) -> str:
    """Load sample email content from test data"""
    email_path = shared_datadir / "sample_email.eml"
    return email_path.read_text(encoding="utf-8")
```

Test data files go in `tests/<module>/data/` directories.

### Type Annotations

**All functions, fixtures, and methods must have proper type annotations:**

For functions that return nothing, we can omit `-> None`.

```python
def my_function(param: str, count: int = 5) -> dict[str, Any]:
    ...

@pytest.fixture
def client() -> TestClient:
    return TestClient(app)

class TestExample:
    def test_something(self, client: TestClient):
        ...
```

### Manual Tests

Tests that call LLMs or external APIs should be marked with `@pytest.mark.manual`:

```python
pytestmark = pytest.mark.manual  # Mark entire file

# OR per test
@pytest.mark.manual
def test_with_llm():
    ...
```

These tests are **excluded by default** (`pytest .`) and run explicitly with `pytest -m manual`.

## Important Patterns and Conventions

### Input Processor Agent

The `input_processor_agent` in `trackable/agents/input_processor.py` handles both email and image inputs:

- Uses `output_schema` for structured JSON output
- Returns `InputProcessorOutput` with list of `ExtractedOrderData`
- Helper function `convert_extracted_to_order()` converts to full `Order` model
- Vision-capable (gemini-2.5-flash) for screenshot parsing

### Chatbot Agent

The `chatbot_agent` in `trackable/agents/chatbot.py` provides conversational interface:

- Currently: Vanilla chat agent for general conversation
- Future: Will be enhanced with database access to query orders, policies, and provide recommendations
- No separate "main orchestrator agent" - the chatbot IS the main user-facing agent

### Cloud Tasks Integration

Worker endpoints in `trackable/worker/routes/tasks.py` receive Cloud Task payloads:

- `POST /tasks/gmail-sync` - Gmail sync task
- `POST /tasks/parse-email` - Email parsing task
- `POST /tasks/parse-image` - Screenshot parsing task

Task payloads use models from `trackable/models/task.py`.

### MIME Type Detection

For image processing, **detect MIME type from magic bytes** rather than hard-coding:

```python
def detect_image_mime_type(image_bytes: bytes) -> str:
    if image_bytes.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png"
    elif image_bytes.startswith(b"\xff\xd8\xff"):
        return "image/jpeg"
    # ... etc
```

### Database Migrations

Migrations are SQL files in `migrations/` directory:

- Run with `uv run python scripts/run_migration.py <migration_file>`
- Uses SQLAlchemy + Cloud SQL Python Connector
- IAM authentication (no passwords)
- Connection pattern: `postgresql+pg8000://user@/dbname?unix_sock=...`

### FastAPI SSE Streaming

Chat endpoints support Server-Sent Events for streaming:

```python
from fastapi.responses import StreamingResponse

async def generate():
    async for event in runner.run_async(...):
        yield f"data: {json.dumps(event_data)}\n\n"

return StreamingResponse(generate(), media_type="text/event-stream")
```

## Environment Configuration

### Google AI Studio (Simple Try)

```bash
GOOGLE_GENAI_USE_VERTEXAI=0
GOOGLE_API_KEY="your-api-key"
```

### Vertex AI (Development & Production)

```bash
GOOGLE_GENAI_USE_VERTEXAI=1
GOOGLE_CLOUD_PROJECT="gen-lang-client-0659747538"
GOOGLE_CLOUD_LOCATION="us-central1"
```

## Key Files

- `trackable/agents/input_processor.py` - Order extraction agent (email + image)
- `trackable/worker/handlers.py` - Cloud Tasks business logic
- `trackable/api/routes/chat.py` - Chatbot endpoints (standard + streaming)
- `docs/design.md` - Architecture decisions and data flows
- `docs/worker_service.md` - Worker service documentation
- `docs/database_schema.md` - Database schema and migrations
- `docs/dev_tracking.md` - Development progress tracking

## Common Issues and Solutions

### "No result from input processor agent"

**Cause**: Incorrect event parsing - trying to access `event.data` which doesn't exist.

**Fix**: Iterate through `event.content.parts` and collect text:

```python
result_text = ""
async for event in runner.run_async(...):
    if event.content and event.content.parts:
        for part in event.content.parts:
            if part.text:
                result_text = part.text
```

### Vision model not processing images

**Cause**: Image not properly passed to model.

**Fix**: Use `Part(inline_data=Blob(data=bytes, mime_type=type))` structure with proper MIME detection.

### Import errors in tests

**Cause**: Using relative imports or incorrect module paths.

**Fix**: Always use absolute imports: `from trackable.models.order import Order`

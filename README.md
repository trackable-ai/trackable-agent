# Trackable Agent

**The brain behind the operation.**

This service powers the intelligence of Trackable. It's not just a chatbot—it's an agentic system that perceives, remembers, and acts on post-purchase data.

It digests messy inputs (emails, screenshots, return policies) and turns them into structured order data and actionable advice.

## What it does

*   **🕵️‍♀️ Perception**: Ingests order confirmations via Gmail or screenshots and extracts structured data (items, prices, dates, tracking numbers).
*   **🧠 Reasoning**: Understands complex return policies. It knows that "30 days from delivery" means a different deadline than "30 days from order."
*   **💬 Conversation**: Talks to users naturally. You can ask "Can I return these Nikes?" and it checks the specific order, the policy, and the current date to give a real answer.
*   **⚙️ Background Work**: Uses Cloud Tasks to process heavy lifting asynchronously so the chat stays fast.

## Tech Stack

*   **Core**: Python 3.14+, FastAPI, Google GenAI (Gemini / Vertex AI)
*   **Database**: PostgreSQL with `pgvector` (via Supabase)
*   **Async**: Google Cloud Tasks for background jobs (email parsing, image analysis)
*   **Tooling**: `uv` for dependency management

## Get Started

### Prerequisites

*   Python 3.14+
*   `uv` (fast Python package manager)
*   Google Cloud Project (for Vertex AI & Tasks)

### Setup

1.  **Install dependencies**:
    ```bash
    uv sync
    ```

2.  **Configure Environment**:
    Copy `.env.example` to `.env`. You need either a Google AI Studio key OR Vertex AI access.

    **Option A: Google AI Studio (Easiest)**
    ```env
    GOOGLE_GENAI_USE_VERTEXAI=0
    GOOGLE_API_KEY="your-api-key"
    ```

    **Option B: Vertex AI (Production)**
    ```env
    GOOGLE_GENAI_USE_VERTEXAI=1
    GOOGLE_CLOUD_PROJECT="your-project-id"
    GOOGLE_CLOUD_LOCATION="us-central1"
    ```

3.  **Run it**:
    ```bash
    # Run the API server
    adk run trackable

    # OR run the web UI playground
    adk web
    ```

## Testing

We have both automated and manual (LLM-based) tests.

```bash
pytest .          # Run standard unit/integration tests
pytest -m manual  # Run manual tests (hits real LLMs, costs money)
```

---

Built by the Trackable AI team.

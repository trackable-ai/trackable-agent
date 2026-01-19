# Trackable

## Get Started

### Prerequisites

- Install `uv`
- Python 3.14+
- Google Cloud CLI (if using Vertex AI)

On macOS, we can directly use `Brewfile` to manage installations:

```bash
brew bundle install
```

### Project Initialization

Using `uv` to create Python virtual environment and install the project dependencies:

```bash
uv sync
```

### Configuration

#### Google AI Studio (API Key)

The API key can be obtained from [Google AI Studio](https://aistudio.google.com/app/api-keys). Then, copy `.env.example` to `.env` and set `.env` as below:

```txt
GOOGLE_GENAI_USE_VERTEXAI=0
GOOGLE_API_KEY="YOUR_API_KEY_HERE"
```

#### Google Cloud Vertex AI

First, check if we have already set up the Google Cloud account.

```bash
gcloud auth list
gcloud config get project
```

If not, authenticate the Google Cloud account:

```bash
gcloud auth application-default login
```

Then, copy `.env.example` to `.env` and set `.env` as below:

```txt
GOOGLE_GENAI_USE_VERTEXAI=1
GOOGLE_CLOUD_PROJECT="YOUR_PROJECT_ID"
GOOGLE_CLOUD_LOCATION="YOUR_VERTEX_AI_LOCATION" # e.g., us-central1
```

## Run Agent

```bash
# Run agent in the command line
adk run trackable

# Run agent web UI
adk web
```

## Run Tests

```bash
pytest .  # run all tests (excluding manual ones)
pytest -m manual  # run all manual tests (especially llm-related ones)
```

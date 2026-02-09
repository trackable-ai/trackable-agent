"""
Trackable Ingress API - Main FastAPI Application.

Provides REST APIs for the frontend chatbot interface.
"""

import os
from contextlib import asynccontextmanager

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.openapi.utils import get_openapi

from trackable.config import DEFAULT_MODEL
from trackable.utils.logging import setup_logging

# Load environment variables
load_dotenv()

# Configure logging early
setup_logging("trackable-ingress")


def _init_database():
    """Initialize database connection if configured."""
    from trackable.db import DatabaseConnection

    instance_connection_name = os.getenv("INSTANCE_CONNECTION_NAME")
    if not instance_connection_name:
        print("   Database: Not configured (INSTANCE_CONNECTION_NAME not set)")
        return False

    try:
        DatabaseConnection.initialize()
        print("   Database: Connected to Cloud SQL")
        return True
    except Exception as e:
        print(f"   Database: Failed to connect - {e}")
        return False


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan context manager for startup and shutdown events."""
    # Startup
    print("🚀 Starting Trackable Ingress API...")
    print(f"   Environment: {os.getenv('GOOGLE_CLOUD_PROJECT', 'local')}")
    print(f"   Model: {DEFAULT_MODEL}")

    db_initialized = _init_database()

    yield

    # Shutdown
    if db_initialized:
        from trackable.db import DatabaseConnection

        DatabaseConnection.close()
        print("   Database: Connection closed")

    print("👋 Shutting down Trackable Ingress API...")


# OpenAPI tag descriptions (shown in /docs and /openapi.json)
OPENAPI_TAGS = [
    {
        "name": "chat",
        "description": "OpenAI-compatible chat completions API",
    },
    {
        "name": "orders",
        "description": "Order management endpoints (requires X-User-ID header)",
    },
    {
        "name": "shipments",
        "description": "Shipment tracking and update endpoints (requires X-User-ID header)",
    },
    {
        "name": "ingest",
        "description": "Manual email and image submission endpoints (requires X-User-ID header)",
    },
    {
        "name": "pubsub",
        "description": "Pub/Sub push endpoints for Gmail notifications and policy refresh jobs",
    },
    {
        "name": "system",
        "description": "System health and information endpoints",
    },
]

# Create FastAPI application
app = FastAPI(
    title="Trackable Ingress API",
    description=(
        "Personal shopping assistant API for post-purchase order management.\n\n"
        "This API provides conversational AI capabilities for managing online shopping orders, "
        "tracking shipments, understanding merchant policies, and monitoring return/exchange deadlines.\n\n"
        "**Authentication:** This is an internal Cloud Run service requiring GCP IAM authentication. "
        "Include an identity token in the `Authorization: Bearer <token>` header.\n\n"
        "**User scoping:** Order, shipment, and ingest endpoints require an `X-User-ID` header (UUID).\n\n"
        "**Model:** Powered by Gemini 2.5 Flash via Google ADK"
    ),
    version="0.1.0",
    lifespan=lifespan,
    openapi_tags=OPENAPI_TAGS,
)

# Configure CORS for frontend access
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # TODO: Configure specific origins in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/", tags=["system"], operation_id="getServiceInfo")
async def root():
    """Return basic information about the API service."""
    return {
        "service": "Trackable Ingress API",
        "version": "0.1.0",
        "status": "operational",
        "description": "Personal shopping assistant for post-purchase management",
    }


@app.get("/health", tags=["system"], operation_id="healthCheck")
async def health_check():
    """Check service health status (used by Cloud Run monitoring)."""
    return {
        "status": "healthy",
        "service": "trackable-ingress",
        "environment": os.getenv("GOOGLE_CLOUD_PROJECT", "local"),
    }


# Import and include routers
from trackable.api.routes import chat, ingest, orders, pubsub, shipments

app.include_router(chat.router, prefix="/api/v1", tags=["chat"])
app.include_router(ingest.router, prefix="/api/v1", tags=["ingest"])
app.include_router(orders.router, prefix="/api/v1", tags=["orders"])
app.include_router(shipments.router, prefix="/api/v1", tags=["shipments"])
app.include_router(pubsub.router, tags=["pubsub"])


def custom_openapi():
    """Override OpenAPI schema to add security schemes."""
    if app.openapi_schema:
        return app.openapi_schema

    openapi_schema = get_openapi(
        title=app.title,
        version=app.version,
        description=app.description,
        routes=app.routes,
        tags=app.openapi_tags,
    )

    # Add security schemes
    openapi_schema["components"]["securitySchemes"] = {
        "BearerAuth": {
            "type": "http",
            "scheme": "bearer",
            "bearerFormat": "JWT",
            "description": (
                "GCP Identity Token for authentication.\n\n"
                "To obtain a token:\n"
                "```bash\n"
                "TOKEN=$(gcloud auth print-identity-token)\n"
                "```"
            ),
        },
        "UserIdAuth": {
            "type": "apiKey",
            "in": "header",
            "name": "X-User-ID",
            "description": (
                "User identifier (UUID format) for user-scoped operations.\n\n"
                "Required for orders, shipments, and ingest endpoints."
            ),
        },
    }

    # Apply global security requirement
    openapi_schema["security"] = [{"BearerAuth": []}]

    app.openapi_schema = openapi_schema
    return app.openapi_schema


app.openapi = custom_openapi

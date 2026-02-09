"""
Trackable Worker API - Main FastAPI Application.

Processes Cloud Tasks for async background jobs.
"""

import os
from contextlib import asynccontextmanager

from dotenv import load_dotenv
from fastapi import FastAPI

from trackable.config import DEFAULT_MODEL
from trackable.utils.logging import setup_logging

# Load environment variables
load_dotenv()

# Configure logging early
setup_logging("trackable-worker")


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
    print("🔨 Starting Trackable Worker Service...")
    print(f"   Environment: {os.getenv('GOOGLE_CLOUD_PROJECT', 'local')}")
    print(f"   Model: {DEFAULT_MODEL}")

    db_initialized = _init_database()

    yield

    # Shutdown
    if db_initialized:
        from trackable.db import DatabaseConnection

        DatabaseConnection.close()
        print("   Database: Connection closed")

    print("👋 Shutting down Trackable Worker Service...")


# Create FastAPI application
app = FastAPI(
    title="Trackable Worker API",
    description="Background worker for processing async order parsing tasks via Cloud Tasks",
    version="0.1.0",
    lifespan=lifespan,
)


@app.get("/")
async def root():
    """Root endpoint - service information."""
    return {
        "service": "Trackable Worker API",
        "version": "0.1.0",
        "status": "operational",
        "description": "Background worker for order parsing tasks",
    }


@app.get("/health")
async def health_check():
    """
    Health check endpoint for Cloud Run.

    Returns:
        dict: Health status
    """
    return {
        "status": "healthy",
        "service": "trackable-worker",
        "environment": os.getenv("GOOGLE_CLOUD_PROJECT", "local"),
    }


# Import and include task routers
from trackable.worker.routes import tasks

app.include_router(tasks.router, prefix="/tasks", tags=["tasks"])

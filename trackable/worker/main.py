"""
Trackable Worker API - Main FastAPI Application.

Processes Cloud Tasks for async background jobs.
"""

import os
from contextlib import asynccontextmanager

from dotenv import load_dotenv
from fastapi import FastAPI

# Load environment variables
load_dotenv()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan context manager for startup and shutdown events."""
    # Startup
    print("🔨 Starting Trackable Worker Service...")
    print(f"   Environment: {os.getenv('GOOGLE_CLOUD_PROJECT', 'local')}")
    print(f"   Model: gemini-2.5-flash")

    yield

    # Shutdown
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

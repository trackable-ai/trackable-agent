"""
Trackable Ingress API - Main FastAPI Application.

Provides REST APIs for the frontend chatbot interface.
"""

import os
from contextlib import asynccontextmanager

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

# Load environment variables
load_dotenv()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan context manager for startup and shutdown events."""
    # Startup
    print("🚀 Starting Trackable Ingress API...")
    print(f"   Environment: {os.getenv('GOOGLE_CLOUD_PROJECT', 'local')}")
    print(f"   Model: gemini-2.5-flash")

    yield

    # Shutdown
    print("👋 Shutting down Trackable Ingress API...")


# Create FastAPI application
app = FastAPI(
    title="Trackable Ingress API",
    description="Personal shopping assistant API for post-purchase order management",
    version="0.1.0",
    lifespan=lifespan,
)

# Configure CORS for frontend access
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # TODO: Configure specific origins in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
async def root():
    """Root endpoint - API information."""
    return {
        "service": "Trackable Ingress API",
        "version": "0.1.0",
        "status": "operational",
        "description": "Personal shopping assistant for post-purchase management",
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
        "service": "trackable-ingress",
        "environment": os.getenv("GOOGLE_CLOUD_PROJECT", "local"),
    }


# Import and include routers
from trackable.api.routes import chat, ingest

app.include_router(chat.router, prefix="/api/v1", tags=["chat"])
app.include_router(ingest.router, prefix="/api/v1", tags=["ingest"])

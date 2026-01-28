"""
Ingest API request/response models.

These models define the structure of requests and responses for the
manual email/screenshot submission endpoints.
"""

from enum import StrEnum

from pydantic import BaseModel, Field

# Constants
MAX_BATCH_SIZE = 50


class BatchItemStatus(StrEnum):
    """Status of a single item in a batch operation."""

    SUCCESS = "success"
    DUPLICATE = "duplicate"  # For images only
    FAILED = "failed"


class IngestEmailRequest(BaseModel):
    """Request body for manual email submission."""

    email_content: str = Field(
        description="Raw email content (EML format or plain text)",
        min_length=1,
    )
    email_subject: str | None = Field(
        default=None,
        description="Email subject line (optional, extracted from content)",
    )
    email_from: str | None = Field(
        default=None, description="Sender email address (optional)"
    )


class IngestImageRequest(BaseModel):
    """Request body for manual screenshot submission."""

    image_data: str = Field(
        description="Base64 encoded image data",
        min_length=1,
    )
    filename: str | None = Field(
        default=None, description="Original filename (optional)"
    )


class IngestResponse(BaseModel):
    """Response for ingest endpoints."""

    job_id: str = Field(description="Job ID for tracking processing status")
    source_id: str = Field(description="Source ID for the submitted content")
    status: str = Field(
        description="Initial status ('queued' or 'duplicate' for images)"
    )
    message: str = Field(description="Human-readable status message")


# Batch request/response models


class BatchEmailItem(BaseModel):
    """Single email item in a batch request."""

    email_content: str = Field(
        description="Raw email content (EML format or plain text)",
        min_length=1,
    )
    email_subject: str | None = Field(
        default=None,
        description="Email subject line (optional)",
    )
    email_from: str | None = Field(
        default=None,
        description="Sender email address (optional)",
    )


class BatchImageItem(BaseModel):
    """Single image item in a batch request."""

    image_data: str = Field(
        description="Base64 encoded image data",
        min_length=1,
    )
    filename: str | None = Field(
        default=None,
        description="Original filename (optional)",
    )


class IngestBatchEmailRequest(BaseModel):
    """Request body for batch email submission."""

    items: list[BatchEmailItem] = Field(
        description="List of emails to ingest",
        min_length=1,
        max_length=MAX_BATCH_SIZE,
    )


class IngestBatchImageRequest(BaseModel):
    """Request body for batch image submission."""

    items: list[BatchImageItem] = Field(
        description="List of images to ingest",
        min_length=1,
        max_length=MAX_BATCH_SIZE,
    )


class BatchItemResult(BaseModel):
    """Result for a single item in a batch operation."""

    index: int = Field(description="Zero-based index of item in the request")
    status: BatchItemStatus = Field(description="Processing status for this item")
    job_id: str | None = Field(
        default=None,
        description="Job ID for tracking (null if failed)",
    )
    source_id: str | None = Field(
        default=None,
        description="Source ID for the submitted content (null if failed)",
    )
    error: str | None = Field(
        default=None,
        description="Error message if status is 'failed'",
    )
    message: str | None = Field(
        default=None,
        description="Additional info (e.g., for duplicates)",
    )


class IngestBatchResponse(BaseModel):
    """Response for batch ingest endpoints."""

    total: int = Field(description="Total items in request")
    succeeded: int = Field(description="Number of items successfully queued")
    duplicates: int = Field(description="Number of duplicate items (images only)")
    failed: int = Field(description="Number of items that failed")
    results: list[BatchItemResult] = Field(description="Individual results per item")

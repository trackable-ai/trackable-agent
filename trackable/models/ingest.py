"""
Ingest API request/response models.

These models define the structure of requests and responses for the
manual email/screenshot submission endpoints.
"""

from pydantic import BaseModel, Field


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
    status: str = Field(description="Initial job status (always 'queued')")
    message: str = Field(description="Human-readable status message")

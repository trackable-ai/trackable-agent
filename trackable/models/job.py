from datetime import datetime, timezone
from enum import StrEnum
from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, Field


class JobType(StrEnum):
    """Type of async processing job"""

    PARSE_EMAIL = "parse_email"  # Parse email content
    PARSE_IMAGE = "parse_image"  # Parse screenshot
    GMAIL_SYNC = "gmail_sync"  # Sync emails from Gmail
    POLICY_REFRESH = "policy_refresh"  # Refresh merchant policy


class JobStatus(StrEnum):
    """Status of async job"""

    QUEUED = "queued"  # Job queued for processing
    PROCESSING = "processing"  # Job currently being processed
    COMPLETED = "completed"  # Job completed successfully
    FAILED = "failed"  # Job failed with error
    CANCELLED = "cancelled"  # Job was cancelled


class Job(BaseModel):
    """
    Async job tracking model for Cloud Tasks.

    Tracks the lifecycle of async processing jobs (email parsing,
    image parsing, Gmail sync, policy refresh).
    """

    # Identity
    id: str = Field(description="Internal job identifier (UUID)")
    user_id: Optional[str] = Field(
        default=None, description="User who initiated job (nullable for system jobs)"
    )

    # Job details
    job_type: JobType = Field(description="Type of processing job")
    status: JobStatus = Field(
        default=JobStatus.QUEUED, description="Current job status"
    )

    # Payload
    input_data: dict[str, Any] = Field(
        default_factory=dict, description="Job input parameters"
    )
    output_data: dict[str, Any] = Field(default_factory=dict, description="Job results")

    # Error tracking
    error_message: Optional[str] = Field(
        default=None, description="Error details if job failed"
    )
    retry_count: int = Field(default=0, description="Number of retry attempts")

    # Cloud Tasks integration
    task_name: Optional[str] = Field(
        default=None, description="Cloud Task name for tracking"
    )

    # Timing
    queued_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="When job was queued",
    )
    started_at: Optional[datetime] = Field(
        default=None, description="When job started processing"
    )
    completed_at: Optional[datetime] = Field(
        default=None, description="When job completed"
    )

    # Timestamps
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="Record creation time",
    )
    updated_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="Last update time",
    )

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "id": "job_abc123",
                "user_id": "usr_xyz789",
                "job_type": "parse_email",
                "status": "completed",
                "input_data": {
                    "email_id": "gmail_msg_456",
                    "subject": "Your order confirmation",
                },
                "output_data": {
                    "order_id": "ord_def789",
                    "confidence_score": 0.95,
                },
                "task_name": "parse_email:job_abc123",
                "queued_at": "2026-01-23T10:00:00Z",
                "started_at": "2026-01-23T10:00:05Z",
                "completed_at": "2026-01-23T10:00:15Z",
            }
        }
    )

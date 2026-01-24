from datetime import datetime, timezone
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field, HttpUrl

from trackable.models.order import SourceType


class Source(BaseModel):
    """
    Source tracking model for emails and screenshots.

    Tracks the origin of order information and enables duplicate detection.
    """

    # Identity
    id: str = Field(description="Internal source identifier (UUID)")
    user_id: str = Field(description="User who owns this source")

    # Source type
    source_type: SourceType = Field(description="Type of source (email or screenshot)")

    # Email source fields
    gmail_message_id: Optional[str] = Field(
        default=None, description="Gmail message ID for email sources"
    )
    email_subject: Optional[str] = Field(default=None, description="Email subject line")
    email_from: Optional[str] = Field(default=None, description="Email sender address")
    email_date: Optional[datetime] = Field(default=None, description="Email date")

    # Screenshot source fields
    image_hash: Optional[str] = Field(
        default=None,
        description="Perceptual hash for screenshot duplicate detection (SHA-256)",
    )
    image_url: Optional[HttpUrl] = Field(
        default=None, description="Storage URL for uploaded screenshot"
    )

    # Processing status
    processed: bool = Field(default=False, description="Whether source has been parsed")
    order_id: Optional[str] = Field(
        default=None, description="Associated order ID (if created)"
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
                "id": "src_abc123",
                "user_id": "usr_xyz789",
                "source_type": "email",
                "gmail_message_id": "gmail_msg_456",
                "email_subject": "Your Nike order confirmation",
                "email_from": "orders@nike.com",
                "email_date": "2026-01-23T10:00:00Z",
                "processed": True,
                "order_id": "ord_def789",
                "created_at": "2026-01-23T10:00:00Z",
            }
        }
    )

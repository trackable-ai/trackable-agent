"""
Cloud Task payload models.

These models define the structure of task payloads sent by Cloud Tasks
to the worker service endpoints.
"""

from pydantic import BaseModel, Field


class GmailSyncTask(BaseModel):
    """Gmail sync task payload"""

    user_email: str = Field(description="User's email address to sync")
    user_id: str = Field(description="Internal user ID")
    history_id: str | None = Field(
        default=None, description="Last history ID for incremental sync"
    )


class ParseEmailTask(BaseModel):
    """Email parsing task payload"""

    job_id: str = Field(description="Job ID in database")
    user_id: str = Field(description="User ID who submitted the email")
    source_id: str = Field(description="Source ID for the email")
    email_content: str = Field(description="Email content to parse")


class ParseImageTask(BaseModel):
    """Image parsing task payload"""

    job_id: str = Field(description="Job ID in database")
    user_id: str = Field(description="User ID who uploaded the image")
    source_id: str = Field(description="Source ID for the image")
    image_url: str | None = Field(
        default=None, description="GCS URL or public URL of image"
    )
    image_data: str | None = Field(
        default=None, description="Base64 encoded image data"
    )


class PolicyRefreshTask(BaseModel):
    """Policy refresh task payload"""

    job_id: str = Field(description="Job ID in database")
    merchant_id: str = Field(description="Merchant ID to refresh policy for")
    merchant_domain: str = Field(description="Merchant domain for logging")
    force_refresh: bool = Field(
        default=False, description="Force refresh even if policy unchanged"
    )

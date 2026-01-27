"""
Pub/Sub message models.

These models define the structure of Pub/Sub push messages received
from Gmail notifications and Cloud Scheduler.
"""

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class PubSubMessageData(BaseModel):
    """Inner message data from Pub/Sub push."""

    attributes: dict[str, str] = Field(
        default_factory=dict, description="Message attributes"
    )
    data: str = Field(description="Base64-encoded message payload")
    messageId: str = Field(description="Pub/Sub message ID")
    publishTime: datetime | None = Field(
        default=None, description="When the message was published"
    )


class PubSubPushMessage(BaseModel):
    """
    Pub/Sub push message envelope.

    This is the structure of HTTP POST requests sent by Pub/Sub
    to push subscribers (Cloud Run endpoints).
    """

    message: PubSubMessageData = Field(description="The Pub/Sub message")
    subscription: str = Field(description="Subscription resource name")


class GmailNotificationPayload(BaseModel):
    """
    Decoded payload from Gmail Pub/Sub notifications.

    Gmail watch sends this data when new emails arrive.
    """

    emailAddress: str = Field(description="User's Gmail address")
    historyId: str = Field(description="Gmail history ID for incremental sync")


class PolicyRefreshPayload(BaseModel):
    """
    Decoded payload from Cloud Scheduler policy refresh trigger.

    Can be empty or contain optional configuration.
    """

    refresh_all: bool = Field(
        default=True, description="Whether to refresh all merchants"
    )
    merchant_ids: list[str] = Field(
        default_factory=list,
        description="Specific merchant IDs to refresh (if not refresh_all)",
    )


class PubSubResponse(BaseModel):
    """Response for Pub/Sub handlers."""

    status: str = Field(description="Processing status")
    message: str = Field(description="Status message")
    tasks_created: int = Field(default=0, description="Number of Cloud Tasks created")
    details: dict[str, Any] = Field(
        default_factory=dict, description="Additional details"
    )

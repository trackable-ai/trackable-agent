from datetime import datetime, timezone
from enum import StrEnum
from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, Field, HttpUrl


class InterventionType(StrEnum):
    """Type of agent intervention"""

    DEADLINE_REMINDER = "deadline_reminder"  # Return/exchange deadline approaching
    DELIVERY_CONFIRMATION = (
        "delivery_confirmation"  # Package delivered, return window starts
    )
    REFUND_DELAYED = "refund_delayed"  # Expected refund hasn't arrived
    SHIPMENT_DELAYED = "shipment_delayed"  # Shipment is delayed
    POLICY_CLARIFICATION = "policy_clarification"  # Unclear policy needs attention
    ACTION_RECOMMENDATION = "action_recommendation"  # Recommend specific action
    INFORMATION_REQUEST = "information_request"  # Need user input/clarification
    STATUS_UPDATE = "status_update"  # Informational status update


class InterventionPriority(StrEnum):
    """Priority level of intervention"""

    LOW = "low"  # Informational
    MEDIUM = "medium"  # Important but not urgent
    HIGH = "high"  # Urgent, deadline approaching
    CRITICAL = "critical"  # Critical deadline imminent


class InterventionStatus(StrEnum):
    """Status of intervention"""

    PENDING = "pending"  # Not yet delivered
    SENT = "sent"  # Delivered to user
    SEEN = "seen"  # User has seen it
    ACTED_ON = "acted_on"  # User took action
    DISMISSED = "dismissed"  # User dismissed it
    EXPIRED = "expired"  # No longer relevant


class ActionType(StrEnum):
    """Types of actions the agent can recommend"""

    INITIATE_RETURN = "initiate_return"
    INITIATE_EXCHANGE = "initiate_exchange"
    CONTACT_SUPPORT = "contact_support"
    TRACK_SHIPMENT = "track_shipment"
    REVIEW_POLICY = "review_policy"
    CONFIRM_DELIVERY = "confirm_delivery"
    UPDATE_ORDER = "update_order"
    NO_ACTION_NEEDED = "no_action_needed"


class RecommendedAction(BaseModel):
    """Action recommended by the agent"""

    action_type: ActionType = Field(description="Type of action to take")
    description: str = Field(description="Human-readable action description")
    deep_link: Optional[HttpUrl] = Field(
        default=None, description="Deep link to perform action"
    )
    estimated_time_minutes: Optional[int] = Field(
        default=None, description="Estimated time to complete"
    )
    deadline: Optional[datetime] = Field(
        default=None, description="Deadline to take this action"
    )
    pre_drafted_message: Optional[str] = Field(
        default=None, description="Pre-drafted message for support contact"
    )


class Intervention(BaseModel):
    """
    Agent intervention model.

    Represents proactive agent actions to notify, remind, or guide users.
    """

    # Identity
    id: str = Field(description="Internal intervention identifier")
    user_id: str = Field(description="User this intervention is for")
    order_id: Optional[str] = Field(
        default=None, description="Associated order ID if applicable"
    )

    # Intervention details
    intervention_type: InterventionType = Field(description="Type of intervention")
    priority: InterventionPriority = Field(description="Priority level")
    status: InterventionStatus = Field(
        default=InterventionStatus.PENDING, description="Current status"
    )

    # Content
    title: str = Field(description="Intervention title/headline")
    message: str = Field(description="Intervention message content")
    recommended_actions: list[RecommendedAction] = Field(
        default_factory=list, description="Actions the agent recommends"
    )

    # Context
    context: dict[str, Any] = Field(
        default_factory=dict, description="Additional context data"
    )
    reasoning: Optional[str] = Field(
        default=None, description="Agent's reasoning for this intervention"
    )

    # Timing
    triggered_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="When intervention was triggered",
    )
    scheduled_for: Optional[datetime] = Field(
        default=None, description="When to deliver this intervention"
    )
    sent_at: Optional[datetime] = Field(
        default=None, description="When intervention was sent"
    )
    seen_at: Optional[datetime] = Field(default=None, description="When user saw it")
    acted_on_at: Optional[datetime] = Field(
        default=None, description="When user took action"
    )

    # Delivery
    delivery_channels: list[str] = Field(
        default_factory=list,
        description="Channels used for delivery (email, push, etc.)",
    )
    delivered: bool = Field(
        default=False, description="Whether intervention was delivered"
    )

    # Metadata
    expires_at: Optional[datetime] = Field(
        default=None,
        description="When this intervention is no longer relevant",
    )
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
                "id": "int_abc123",
                "user_id": "usr_xyz789",
                "order_id": "ord_def456",
                "intervention_type": "deadline_reminder",
                "priority": "high",
                "status": "sent",
                "title": "Return Window Closing Soon",
                "message": "Your Nike Air Max 90 return window closes in 3 days (Feb 12). Would you like to return these shoes?",
                "recommended_actions": [
                    {
                        "action_type": "initiate_return",
                        "description": "Start return process",
                        "deep_link": "https://nike.com/returns/123",
                        "estimated_time_minutes": 5,
                        "deadline": "2024-02-12T23:59:59Z",
                    }
                ],
                "reasoning": "Return window closes in 3 days and user has ordered a different size",
                "triggered_at": "2024-02-09T10:00:00Z",
                "sent_at": "2024-02-09T10:00:00Z",
            }
        }
    )

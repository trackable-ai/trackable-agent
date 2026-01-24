from datetime import datetime, timezone
from enum import StrEnum
from typing import Optional

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class UserStatus(StrEnum):
    """User account status"""

    ACTIVE = "active"
    INACTIVE = "inactive"
    SUSPENDED = "suspended"
    DELETED = "deleted"


class NotificationPreference(StrEnum):
    """Notification delivery preferences"""

    EMAIL = "email"
    PUSH = "push"
    IN_APP = "in_app"
    SMS = "sms"
    NONE = "none"


class ReminderSensitivity(StrEnum):
    """How aggressively the agent should remind users"""

    LOW = "low"  # Only critical deadlines
    MEDIUM = "medium"  # Important deadlines
    HIGH = "high"  # All deadlines with multiple reminders


class GmailConnection(BaseModel):
    """Gmail OAuth connection details"""

    connected: bool = Field(description="Whether Gmail is connected")
    email: Optional[EmailStr] = Field(
        default=None, description="Connected Gmail address"
    )
    connected_at: Optional[datetime] = Field(
        default=None, description="Connection timestamp"
    )
    last_sync: Optional[datetime] = Field(
        default=None, description="Last email sync timestamp"
    )
    last_history_id: Optional[str] = Field(
        default=None, description="Last Gmail historyId for incremental sync"
    )
    watch_expiration: Optional[datetime] = Field(
        default=None, description="Gmail push notification watch expiration"
    )
    scopes: list[str] = Field(default_factory=list, description="OAuth scopes granted")
    token_valid: bool = Field(
        default=True, description="Whether OAuth token is still valid"
    )


class UserPreferences(BaseModel):
    """User preferences for agent behavior"""

    # Notification preferences
    notification_channels: list[NotificationPreference] = Field(
        default_factory=lambda: [
            NotificationPreference.EMAIL,
            NotificationPreference.IN_APP,
        ],
        description="Preferred notification channels",
    )
    reminder_sensitivity: ReminderSensitivity = Field(
        default=ReminderSensitivity.MEDIUM,
        description="Reminder frequency preference",
    )

    # Reminder timing
    days_before_deadline_reminder: list[int] = Field(
        default_factory=lambda: [7, 3, 1],
        description="Days before deadline to send reminders",
    )
    quiet_hours_start: Optional[int] = Field(
        default=22, ge=0, le=23, description="Quiet hours start (hour 0-23)"
    )
    quiet_hours_end: Optional[int] = Field(
        default=8, ge=0, le=23, description="Quiet hours end (hour 0-23)"
    )

    # Agent behavior
    auto_detect_orders: bool = Field(
        default=True, description="Automatically detect orders from Gmail"
    )
    proactive_interventions: bool = Field(
        default=True, description="Allow agent to proactively intervene"
    )
    require_confirmation: bool = Field(
        default=True, description="Require user confirmation for actions"
    )

    # Display preferences
    timezone: str = Field(default="UTC", description="User's timezone")
    currency: str = Field(default="USD", description="Preferred currency")


class User(BaseModel):
    """
    User model representing a Trackable user.

    Users own orders and have preferences that guide agent behavior.
    """

    # Identity
    id: str = Field(description="Internal user identifier (UUID)")
    email: EmailStr = Field(description="User's email address")
    name: Optional[str] = Field(default=None, description="User's full name")

    # Status
    status: UserStatus = Field(default=UserStatus.ACTIVE, description="Account status")

    # Connections
    gmail_connection: Optional[GmailConnection] = Field(
        default=None, description="Gmail connection details"
    )

    # Preferences
    preferences: UserPreferences = Field(
        default_factory=UserPreferences, description="User preferences"
    )

    # Statistics
    total_orders: int = Field(default=0, description="Total orders tracked")
    active_orders: int = Field(
        default=0, description="Active orders with pending actions"
    )
    missed_return_windows: int = Field(
        default=0, description="Count of missed return windows"
    )

    # Timestamps
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="Account creation time",
    )
    updated_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="Last update time",
    )
    last_login: Optional[datetime] = Field(
        default=None, description="Last login timestamp"
    )

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "id": "usr_abc123",
                "email": "user@example.com",
                "name": "Jane Doe",
                "status": "active",
                "gmail_connection": {
                    "connected": True,
                    "email": "user@gmail.com",
                    "connected_at": "2024-01-15T10:00:00Z",
                    "last_sync": "2024-01-20T14:30:00Z",
                    "scopes": ["https://www.googleapis.com/auth/gmail.readonly"],
                    "token_valid": True,
                },
                "preferences": {
                    "notification_channels": ["email", "in_app"],
                    "reminder_sensitivity": "medium",
                    "days_before_deadline_reminder": [7, 3, 1],
                },
                "total_orders": 42,
                "active_orders": 3,
            }
        }
    )

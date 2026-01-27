from datetime import datetime, timezone
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


class OAuthToken(BaseModel):
    """
    OAuth token storage model.

    Stores OAuth access/refresh tokens and provider-specific metadata.
    """

    # Identity
    id: str = Field(description="Internal token identifier (UUID)")
    user_id: str = Field(description="User who owns this token")

    # Provider info
    provider: str = Field(description="OAuth provider (gmail, google, etc.)")
    provider_email: Optional[str] = Field(
        default=None, description="Email associated with this provider account"
    )

    # Tokens
    access_token: str = Field(description="OAuth access token")
    refresh_token: Optional[str] = Field(
        default=None, description="OAuth refresh token"
    )
    token_type: str = Field(default="Bearer", description="Token type")

    # Token metadata
    scope: Optional[str] = Field(
        default=None, description="Space-separated OAuth scopes"
    )
    expires_at: Optional[datetime] = Field(
        default=None, description="Token expiration time"
    )

    # Provider-specific metadata (Gmail)
    last_sync: Optional[datetime] = Field(
        default=None, description="Last successful sync"
    )
    last_history_id: Optional[str] = Field(
        default=None, description="Gmail historyId for incremental sync"
    )
    watch_expiration: Optional[datetime] = Field(
        default=None, description="Gmail push notification watch expiration"
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

    @property
    def is_expired(self) -> bool:
        """Check if the access token is expired."""
        if self.expires_at is None:
            return False
        return datetime.now(timezone.utc) >= self.expires_at

    @property
    def scopes(self) -> list[str]:
        """Get scopes as a list."""
        if self.scope is None:
            return []
        return self.scope.split()

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "id": "tok_abc123",
                "user_id": "usr_xyz789",
                "provider": "gmail",
                "provider_email": "user@gmail.com",
                "access_token": "ya29.xxx",
                "refresh_token": "1//xxx",
                "token_type": "Bearer",
                "scope": "https://www.googleapis.com/auth/gmail.readonly",
                "expires_at": "2026-01-26T12:00:00Z",
                "last_sync": "2026-01-26T10:00:00Z",
                "last_history_id": "12345",
            }
        }
    )

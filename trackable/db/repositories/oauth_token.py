"""
OAuth token repository for database operations.

Handles secure storage and retrieval of OAuth tokens.
"""

from datetime import datetime, timezone
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import Table, select

from trackable.db.repositories.base import BaseRepository
from trackable.db.tables import oauth_tokens
from trackable.models.oauth import OAuthToken


class OAuthTokenRepository(BaseRepository[OAuthToken]):
    """Repository for OAuth token operations."""

    @property
    def table(self) -> Table:
        return oauth_tokens

    def _row_to_model(self, row: Any) -> OAuthToken:
        """Convert database row to OAuthToken model."""
        return OAuthToken(
            id=str(row.id),
            user_id=str(row.user_id),
            provider=row.provider,
            provider_email=row.provider_email,
            access_token=row.access_token,
            refresh_token=row.refresh_token,
            token_type=row.token_type or "Bearer",
            scope=row.scope,
            expires_at=row.expires_at,
            last_sync=row.last_sync,
            last_history_id=row.last_history_id,
            watch_expiration=row.watch_expiration,
            created_at=row.created_at,
            updated_at=row.updated_at,
        )

    def _model_to_dict(self, model: OAuthToken) -> dict:
        """Convert OAuthToken model to database dict."""
        now = datetime.now(timezone.utc)
        return {
            "id": UUID(model.id) if model.id else uuid4(),
            "user_id": UUID(model.user_id),
            "provider": model.provider,
            "provider_email": model.provider_email,
            "access_token": model.access_token,
            "refresh_token": model.refresh_token,
            "token_type": model.token_type,
            "scope": model.scope,
            "expires_at": model.expires_at,
            "last_sync": model.last_sync,
            "last_history_id": model.last_history_id,
            "watch_expiration": model.watch_expiration,
            "created_at": now,
            "updated_at": now,
        }

    def get_by_provider(self, user_id: str, provider: str) -> OAuthToken | None:
        """
        Get OAuth token by user and provider.

        Args:
            user_id: User ID
            provider: OAuth provider (e.g., 'gmail')

        Returns:
            OAuthToken or None if not found
        """
        stmt = select(self.table).where(
            self.table.c.user_id == UUID(user_id),
            self.table.c.provider == provider,
        )
        result = self.session.execute(stmt)
        row = result.fetchone()

        if row is None:
            return None

        return self._row_to_model(row)

    def upsert(self, token: OAuthToken) -> OAuthToken:
        """
        Insert or update OAuth token.

        Uses provider + user_id as unique key.

        Args:
            token: OAuth token to upsert

        Returns:
            Upserted token
        """
        from sqlalchemy.dialects.postgresql import insert

        data = self._model_to_dict(token)
        stmt = insert(self.table).values(**data)

        # On conflict, update everything except id and created_at
        update_data = {k: v for k, v in data.items() if k not in ("id", "created_at")}
        stmt = stmt.on_conflict_do_update(
            index_elements=["user_id", "provider"],
            set_=update_data,
        )

        result = self.session.execute(stmt.returning(self.table))
        row = result.fetchone()
        return self._row_to_model(row)

    def update_tokens(
        self,
        user_id: str,
        provider: str,
        access_token: str,
        refresh_token: str | None = None,
        expires_at: datetime | None = None,
    ) -> bool:
        """
        Update access and refresh tokens.

        Args:
            user_id: User ID
            provider: OAuth provider
            access_token: New access token
            refresh_token: New refresh token (optional)
            expires_at: Token expiration time (optional)

        Returns:
            True if token was updated
        """
        existing = self.get_by_provider(user_id, provider)
        if existing is None:
            return False

        now = datetime.now(timezone.utc)
        update_data: dict[str, Any] = {
            "access_token": access_token,
            "updated_at": now,
        }

        if refresh_token is not None:
            update_data["refresh_token"] = refresh_token
        if expires_at is not None:
            update_data["expires_at"] = expires_at

        return self.update_by_id(existing.id, **update_data)

    def update_sync_state(
        self,
        user_id: str,
        provider: str,
        last_sync: datetime | None = None,
        last_history_id: str | None = None,
    ) -> bool:
        """
        Update sync state for a provider.

        Args:
            user_id: User ID
            provider: OAuth provider
            last_sync: Last sync time
            last_history_id: Provider-specific history ID

        Returns:
            True if token was updated
        """
        existing = self.get_by_provider(user_id, provider)
        if existing is None:
            return False

        now = datetime.now(timezone.utc)
        update_data: dict[str, Any] = {"updated_at": now}

        if last_sync is not None:
            update_data["last_sync"] = last_sync
        if last_history_id is not None:
            update_data["last_history_id"] = last_history_id

        return self.update_by_id(existing.id, **update_data)

    def delete_by_provider(self, user_id: str, provider: str) -> bool:
        """
        Delete OAuth token by user and provider.

        Args:
            user_id: User ID
            provider: OAuth provider

        Returns:
            True if token was deleted
        """
        existing = self.get_by_provider(user_id, provider)
        if existing is None:
            return False

        return self.delete_by_id(existing.id)

    def get_expiring_tokens(self, minutes: int = 5) -> list[OAuthToken]:
        """
        Get tokens expiring within the specified minutes.

        Useful for proactive token refresh.

        Args:
            minutes: Minutes until expiration

        Returns:
            List of tokens expiring soon
        """
        from datetime import timedelta

        now = datetime.now(timezone.utc)
        threshold = now + timedelta(minutes=minutes)

        stmt = select(self.table).where(
            self.table.c.expires_at.isnot(None),
            self.table.c.expires_at <= threshold,
            self.table.c.expires_at > now,
        )

        result = self.session.execute(stmt)
        return [self._row_to_model(row) for row in result.fetchall()]

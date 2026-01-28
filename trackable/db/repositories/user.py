"""
User repository for database operations.

Handles user CRUD and lookup operations.
"""

from datetime import datetime, timezone
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import Table

from trackable.db.repositories.base import (
    BaseRepository,
    jsonb_to_model,
    model_to_jsonb,
)
from trackable.db.tables import users
from trackable.models.user import User, UserPreferences, UserStatus


class UserRepository(BaseRepository[User]):
    """Repository for User operations."""

    @property
    def table(self) -> Table:
        return users

    def _row_to_model(self, row: Any) -> User:
        """Convert database row to User model."""
        preferences = jsonb_to_model(row.preferences, UserPreferences)
        return User(
            id=str(row.id),
            email=row.email,
            name=row.name,
            status=UserStatus(row.status),
            preferences=preferences or UserPreferences(),
            total_orders=row.total_orders or 0,
            active_orders=row.active_orders or 0,
            missed_return_windows=row.missed_return_windows or 0,
            created_at=row.created_at,
            updated_at=row.updated_at,
            last_login=row.last_login,
        )

    def _model_to_dict(self, model: User) -> dict:
        """Convert User model to database dict."""
        now = datetime.now(timezone.utc)
        return {
            "id": UUID(model.id) if model.id else uuid4(),
            "email": model.email,
            "name": model.name,
            "status": model.status.value,
            "preferences": model_to_jsonb(model.preferences),
            "total_orders": model.total_orders,
            "active_orders": model.active_orders,
            "missed_return_windows": model.missed_return_windows,
            "created_at": model.created_at or now,
            "updated_at": model.updated_at or now,
            "last_login": model.last_login,
        }

    def get_or_create(self, user_id: str) -> User:
        """
        Get user by ID, creating if not exists.

        For auto-created users, a placeholder email is generated.

        Args:
            user_id: User ID (UUID string)

        Returns:
            Existing or newly created User
        """
        user = self.get_by_id(user_id)
        if user is not None:
            return user

        # Create user with placeholder email
        now = datetime.now(timezone.utc)
        user = User(
            id=user_id,
            email=f"{user_id}@placeholder.com",
            name=None,
            status=UserStatus.ACTIVE,
            preferences=UserPreferences(),
            total_orders=0,
            active_orders=0,
            missed_return_windows=0,
            created_at=now,
            updated_at=now,
        )

        return self.create(user)

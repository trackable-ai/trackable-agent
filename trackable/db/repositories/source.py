"""
Source repository for database operations.

Handles source CRUD and duplicate detection.
"""

from datetime import datetime, timezone
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import Table, select

from trackable.db.repositories.base import BaseRepository
from trackable.db.tables import sources
from trackable.models.order import SourceType
from trackable.models.source import Source


class SourceRepository(BaseRepository[Source]):
    """Repository for Source operations with duplicate detection."""

    @property
    def table(self) -> Table:
        return sources

    def _row_to_model(self, row: Any) -> Source:
        """Convert database row to Source model."""
        return Source(
            id=str(row.id),
            user_id=str(row.user_id),
            source_type=SourceType(row.source_type),
            gmail_message_id=row.gmail_message_id,
            email_subject=row.email_subject,
            email_from=row.email_from,
            email_date=row.email_date,
            image_hash=row.image_hash,
            image_url=row.image_url,
            processed=row.processed or False,
            order_id=str(row.order_id) if row.order_id else None,
            created_at=row.created_at,
            updated_at=row.updated_at,
        )

    def _model_to_dict(self, model: Source) -> dict:
        """Convert Source model to database dict."""
        now = datetime.now(timezone.utc)
        return {
            "id": UUID(model.id) if model.id else uuid4(),
            "user_id": UUID(model.user_id),
            "source_type": model.source_type.value,
            "gmail_message_id": model.gmail_message_id,
            "email_subject": model.email_subject,
            "email_from": model.email_from,
            "email_date": model.email_date,
            "image_hash": model.image_hash,
            "image_url": str(model.image_url) if model.image_url else None,
            "processed": model.processed,
            "order_id": UUID(model.order_id) if model.order_id else None,
            "created_at": now,
            "updated_at": now,
        }

    def find_by_gmail_message_id(
        self, user_id: str, gmail_message_id: str
    ) -> Source | None:
        """
        Find source by Gmail message ID.

        Used for email duplicate detection.

        Args:
            user_id: User ID
            gmail_message_id: Gmail message ID

        Returns:
            Source if found, None otherwise
        """
        stmt = select(self.table).where(
            self.table.c.user_id == UUID(user_id),
            self.table.c.gmail_message_id == gmail_message_id,
        )
        result = self.session.execute(stmt)
        row = result.fetchone()

        if row is None:
            return None

        return self._row_to_model(row)

    def find_by_image_hash(self, user_id: str, image_hash: str) -> Source | None:
        """
        Find source by image hash.

        Used for screenshot duplicate detection.

        Args:
            user_id: User ID
            image_hash: SHA-256 hash of the image

        Returns:
            Source if found, None otherwise
        """
        stmt = select(self.table).where(
            self.table.c.user_id == UUID(user_id),
            self.table.c.image_hash == image_hash,
        )
        result = self.session.execute(stmt)
        row = result.fetchone()

        if row is None:
            return None

        return self._row_to_model(row)

    def is_email_duplicate(self, user_id: str, gmail_message_id: str) -> bool:
        """
        Check if an email source already exists.

        Args:
            user_id: User ID
            gmail_message_id: Gmail message ID

        Returns:
            True if duplicate exists
        """
        return self.find_by_gmail_message_id(user_id, gmail_message_id) is not None

    def is_image_duplicate(self, user_id: str, image_hash: str) -> bool:
        """
        Check if an image source already exists.

        Args:
            user_id: User ID
            image_hash: SHA-256 hash of the image

        Returns:
            True if duplicate exists
        """
        return self.find_by_image_hash(user_id, image_hash) is not None

    def mark_processed(self, source_id: str | UUID, order_id: str | UUID) -> bool:
        """
        Mark source as processed and link to order.

        Args:
            source_id: Source ID
            order_id: Created order ID

        Returns:
            True if source was updated
        """
        now = datetime.now(timezone.utc)
        order_uuid = UUID(order_id) if isinstance(order_id, str) else order_id

        return self.update_by_id(
            source_id,
            processed=True,
            order_id=order_uuid,
            updated_at=now,
        )

    def get_unprocessed(
        self, user_id: str | None = None, limit: int = 100
    ) -> list[Source]:
        """
        Get unprocessed sources.

        Args:
            user_id: Optional user ID filter
            limit: Maximum number of sources to return

        Returns:
            List of unprocessed sources
        """
        stmt = select(self.table).where(self.table.c.processed == False)  # noqa: E712

        if user_id:
            stmt = stmt.where(self.table.c.user_id == UUID(user_id))

        stmt = stmt.order_by(self.table.c.created_at.asc()).limit(limit)

        result = self.session.execute(stmt)
        return [self._row_to_model(row) for row in result.fetchall()]

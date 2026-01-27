"""
Merchant repository for database operations.

Handles merchant CRUD and upsert by domain.
"""

from datetime import datetime, timezone
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import Table, select
from sqlalchemy.dialects.postgresql import insert

from trackable.db.repositories.base import BaseRepository
from trackable.db.tables import merchants
from trackable.models.order import Merchant


class MerchantRepository(BaseRepository[Merchant]):
    """Repository for Merchant operations."""

    @property
    def table(self) -> Table:
        return merchants

    def _row_to_model(self, row: Any) -> Merchant:
        """Convert database row to Merchant model."""
        return Merchant(
            id=str(row.id),
            name=row.name,
            domain=row.domain,
            support_email=row.support_email,
            support_url=row.support_url,
            return_portal_url=row.return_portal_url,
        )

    def _model_to_dict(self, model: Merchant) -> dict:
        """Convert Merchant model to database dict."""
        now = datetime.now(timezone.utc)
        return {
            "id": UUID(model.id) if model.id else uuid4(),
            "name": model.name,
            "domain": model.domain,
            "support_email": model.support_email,
            "support_url": str(model.support_url) if model.support_url else None,
            "return_portal_url": (
                str(model.return_portal_url) if model.return_portal_url else None
            ),
            "created_at": now,
            "updated_at": now,
        }

    def get_by_domain(self, domain: str) -> Merchant | None:
        """
        Get merchant by domain.

        Args:
            domain: Merchant domain (e.g., "nike.com")

        Returns:
            Merchant or None if not found
        """
        stmt = select(self.table).where(self.table.c.domain == domain)
        result = self.session.execute(stmt)
        row = result.fetchone()

        if row is None:
            return None

        return self._row_to_model(row)

    def upsert_by_domain(self, merchant: Merchant) -> Merchant:
        """
        Insert or update merchant by domain.

        If a merchant with the same domain exists, updates the existing record.
        Otherwise, creates a new merchant.

        Args:
            merchant: Merchant model to upsert

        Returns:
            Created or updated Merchant
        """
        now = datetime.now(timezone.utc)
        merchant_id = UUID(merchant.id) if merchant.id else uuid4()

        insert_data = {
            "id": merchant_id,
            "name": merchant.name,
            "domain": merchant.domain,
            "support_email": merchant.support_email,
            "support_url": str(merchant.support_url) if merchant.support_url else None,
            "return_portal_url": (
                str(merchant.return_portal_url) if merchant.return_portal_url else None
            ),
            "created_at": now,
            "updated_at": now,
        }

        # PostgreSQL upsert: ON CONFLICT (domain) DO UPDATE
        stmt = (
            insert(self.table)
            .values(**insert_data)
            .on_conflict_do_update(
                index_elements=["domain"],
                set_={
                    "name": merchant.name,
                    "support_email": merchant.support_email,
                    "support_url": (
                        str(merchant.support_url) if merchant.support_url else None
                    ),
                    "return_portal_url": (
                        str(merchant.return_portal_url)
                        if merchant.return_portal_url
                        else None
                    ),
                    "updated_at": now,
                },
            )
            .returning(self.table)
        )

        result = self.session.execute(stmt)
        row = result.fetchone()
        return self._row_to_model(row)

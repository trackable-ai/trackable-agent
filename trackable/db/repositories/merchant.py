"""
Merchant repository for database operations.

Handles merchant CRUD, upsert by domain, and name normalization.
"""

from datetime import datetime, timezone
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import Table, func, select
from sqlalchemy.dialects.postgresql import insert

from trackable.db.repositories.base import BaseRepository
from trackable.db.tables import merchants
from trackable.models.order import Merchant
from trackable.utils.merchant import (
    generate_merchant_aliases,
    normalize_domain,
    normalize_merchant_name,
)


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
            aliases=row.aliases or [],
            support_email=row.support_email,
            support_url=row.support_url,
            return_portal_url=row.return_portal_url,
            policy_urls=row.policy_urls or [],
        )

    def _model_to_dict(self, model: Merchant) -> dict:
        """Convert Merchant model to database dict."""
        now = datetime.now(timezone.utc)
        return {
            "id": UUID(model.id) if model.id else uuid4(),
            "name": model.name,
            "domain": model.domain,
            "aliases": model.aliases,
            "support_email": model.support_email,
            "support_url": str(model.support_url) if model.support_url else None,
            "return_portal_url": (
                str(model.return_portal_url) if model.return_portal_url else None
            ),
            "policy_urls": model.policy_urls,
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
        # Normalize the domain for lookup
        normalized = normalize_domain(domain)
        if not normalized:
            return None

        stmt = select(self.table).where(self.table.c.domain == normalized)
        result = self.session.execute(stmt)
        row = result.fetchone()

        if row is None:
            return None

        return self._row_to_model(row)

    def get_by_name_or_domain(
        self, name: str | None = None, domain: str | None = None
    ) -> Merchant | None:
        """
        Get merchant by name, domain, or alias.

        Searches in order of priority:
        1. Exact domain match (normalized)
        2. Exact name match (case-insensitive)
        3. Alias match (checks if query exists in aliases array)

        Args:
            name: Merchant name to search for
            domain: Merchant domain to search for

        Returns:
            Merchant or None if not found
        """
        # Try domain lookup first (most reliable)
        if domain:
            normalized_domain = normalize_domain(domain)
            if normalized_domain:
                stmt = select(self.table).where(
                    self.table.c.domain == normalized_domain
                )
                result = self.session.execute(stmt)
                row = result.fetchone()
                if row:
                    return self._row_to_model(row)

        # Try name lookup (case-insensitive)
        if name:
            name_lower = name.lower().strip()

            # Exact name match (case-insensitive)
            stmt = select(self.table).where(func.lower(self.table.c.name) == name_lower)
            result = self.session.execute(stmt)
            row = result.fetchone()
            if row:
                return self._row_to_model(row)

            # Alias match - check if name is in aliases array
            # PostgreSQL: aliases @> '["name"]'::jsonb
            stmt = select(self.table).where(self.table.c.aliases.contains([name_lower]))
            result = self.session.execute(stmt)
            row = result.fetchone()
            if row:
                return self._row_to_model(row)

        return None

    def list_all(self, limit: int = 100, offset: int = 0) -> list[Merchant]:
        """
        List all merchants with pagination.

        Args:
            limit: Maximum number of merchants to return
            offset: Number of merchants to skip

        Returns:
            List of Merchant models
        """
        stmt = select(self.table).limit(limit).offset(offset)
        result = self.session.execute(stmt)
        return [self._row_to_model(row) for row in result.fetchall()]

    def upsert_by_domain(self, merchant: Merchant, normalize: bool = True) -> Merchant:
        """
        Insert or update merchant by domain with name normalization.

        If a merchant with the same domain exists, updates the existing record.
        Otherwise, creates a new merchant.

        When normalizing:
        - Merchant name is normalized to canonical form (e.g., "AMAZON" -> "Amazon")
        - Domain is normalized (e.g., "www.amazon.com" -> "amazon.com")
        - Aliases are generated for fuzzy matching

        Args:
            merchant: Merchant model to upsert
            normalize: Whether to normalize name and generate aliases (default: True)

        Returns:
            Created or updated Merchant
        """
        now = datetime.now(timezone.utc)
        merchant_id = UUID(merchant.id) if merchant.id else uuid4()

        # Normalize domain
        normalized_domain = (
            normalize_domain(merchant.domain) if merchant.domain else None
        )

        # Normalize name and generate aliases
        if normalize:
            normalized_name = normalize_merchant_name(merchant.name, normalized_domain)
            aliases = generate_merchant_aliases(normalized_name, normalized_domain)
        else:
            normalized_name = merchant.name
            aliases = merchant.aliases or []

        insert_data = {
            "id": merchant_id,
            "name": normalized_name,
            "domain": normalized_domain,
            "aliases": aliases,
            "support_email": merchant.support_email,
            "support_url": str(merchant.support_url) if merchant.support_url else None,
            "return_portal_url": (
                str(merchant.return_portal_url) if merchant.return_portal_url else None
            ),
            "policy_urls": merchant.policy_urls,
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
                    "name": normalized_name,
                    "aliases": aliases,
                    "support_email": merchant.support_email,
                    "support_url": (
                        str(merchant.support_url) if merchant.support_url else None
                    ),
                    "return_portal_url": (
                        str(merchant.return_portal_url)
                        if merchant.return_portal_url
                        else None
                    ),
                    "policy_urls": merchant.policy_urls,
                    "updated_at": now,
                },
            )
            .returning(self.table)
        )

        result = self.session.execute(stmt)
        row = result.fetchone()
        return self._row_to_model(row)

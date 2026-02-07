"""
Policy repository for database operations.

Handles policy CRUD with hash-based change detection to avoid unnecessary updates.
"""

import json
from datetime import datetime, timezone
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import Table, select
from sqlalchemy.dialects.postgresql import insert

from trackable.db.repositories.base import BaseRepository
from trackable.db.tables import policies
from trackable.models.policy import Policy, PolicyType
from trackable.utils.hash import compute_sha256


class PolicyRepository(BaseRepository[Policy]):
    """Repository for Policy operations."""

    @property
    def table(self) -> Table:
        return policies

    def _row_to_model(self, row: Any) -> Policy:
        """Convert database row to Policy model."""
        return Policy(
            id=str(row.id),
            merchant_id=str(row.merchant_id),
            policy_type=PolicyType(row.policy_type),
            country_code=row.country_code,
            name=row.name,
            description=row.description,
            version=row.version,
            effective_date=row.effective_date,
            return_policy=row.return_policy,
            exchange_policy=row.exchange_policy,
            source_url=row.source_url,
            raw_text=row.raw_text,
            confidence_score=(
                float(row.confidence_score) if row.confidence_score else None
            ),
            last_verified=row.last_verified,
            needs_verification=row.needs_verification,
            interpretation_notes=row.interpretation_notes or [],
            created_at=row.created_at,
            updated_at=row.updated_at,
        )

    def _model_to_dict(self, model: Policy) -> dict:
        """Convert Policy model to database dict."""
        now = datetime.now(timezone.utc)
        return {
            "id": UUID(model.id) if model.id else uuid4(),
            "merchant_id": UUID(model.merchant_id),
            "policy_type": model.policy_type.value,
            "country_code": model.country_code,
            "name": model.name,
            "description": model.description,
            "version": model.version,
            "effective_date": model.effective_date,
            "return_policy": (
                json.loads(model.return_policy.model_dump_json())
                if model.return_policy
                else None
            ),
            "exchange_policy": (
                json.loads(model.exchange_policy.model_dump_json())
                if model.exchange_policy
                else None
            ),
            "source_url": str(model.source_url) if model.source_url else None,
            "raw_text": model.raw_text,
            "confidence_score": model.confidence_score,
            "last_verified": model.last_verified,
            "needs_verification": model.needs_verification,
            "interpretation_notes": model.interpretation_notes,
            "created_at": now,
            "updated_at": now,
        }

    def get_by_merchant(
        self, merchant_id: str, policy_type: PolicyType, country_code: str = "US"
    ) -> Policy | None:
        """
        Get specific policy by merchant, type, and country.

        Args:
            merchant_id: Merchant ID
            policy_type: Policy type (return, exchange, etc.)
            country_code: Country code (default: "US")

        Returns:
            Policy or None if not found
        """
        stmt = select(self.table).where(
            self.table.c.merchant_id == UUID(merchant_id),
            self.table.c.policy_type == policy_type.value,
            self.table.c.country_code == country_code,
        )
        result = self.session.execute(stmt)
        row = result.fetchone()

        if row is None:
            return None

        return self._row_to_model(row)

    def list_by_merchant(self, merchant_id: str) -> list[Policy]:
        """
        Get all policies for a merchant.

        Args:
            merchant_id: Merchant ID

        Returns:
            List of Policy models
        """
        stmt = select(self.table).where(self.table.c.merchant_id == UUID(merchant_id))
        result = self.session.execute(stmt)
        return [self._row_to_model(row) for row in result.fetchall()]

    def upsert_by_merchant_and_type(self, policy: Policy) -> Policy:
        """
        Insert or update policy using unique constraint on (merchant_id, policy_type, country_code).

        Implements hash-based change detection: if raw_text hasn't changed, skip update.

        Args:
            policy: Policy model to upsert

        Returns:
            Created or updated Policy
        """
        # Check if policy exists and if raw_text has changed
        existing = self.get_by_merchant(
            policy.merchant_id, policy.policy_type, policy.country_code
        )

        if existing and existing.raw_text and policy.raw_text:
            existing_hash = compute_sha256(existing.raw_text.encode())
            new_hash = compute_sha256(policy.raw_text.encode())
            if existing_hash == new_hash:
                # No changes detected, return existing
                return existing

        # Changes detected or no existing policy, proceed with upsert
        now = datetime.now(timezone.utc)
        policy_id = UUID(policy.id) if policy.id else uuid4()

        insert_data = {
            "id": policy_id,
            "merchant_id": UUID(policy.merchant_id),
            "policy_type": policy.policy_type.value,
            "country_code": policy.country_code,
            "name": policy.name,
            "description": policy.description,
            "version": policy.version,
            "effective_date": policy.effective_date,
            "return_policy": (
                json.loads(policy.return_policy.model_dump_json())
                if policy.return_policy
                else None
            ),
            "exchange_policy": (
                json.loads(policy.exchange_policy.model_dump_json())
                if policy.exchange_policy
                else None
            ),
            "source_url": str(policy.source_url) if policy.source_url else None,
            "raw_text": policy.raw_text,
            "confidence_score": policy.confidence_score,
            "last_verified": policy.last_verified or now,
            "needs_verification": policy.needs_verification,
            "interpretation_notes": policy.interpretation_notes,
            "created_at": now,
            "updated_at": now,
        }

        # PostgreSQL upsert: ON CONFLICT (merchant_id, policy_type, country_code) DO UPDATE
        stmt = (
            insert(self.table)
            .values(**insert_data)
            .on_conflict_do_update(
                index_elements=["merchant_id", "policy_type", "country_code"],
                set_={
                    "name": policy.name,
                    "description": policy.description,
                    "version": policy.version,
                    "effective_date": policy.effective_date,
                    "return_policy": (
                        json.loads(policy.return_policy.model_dump_json())
                        if policy.return_policy
                        else None
                    ),
                    "exchange_policy": (
                        json.loads(policy.exchange_policy.model_dump_json())
                        if policy.exchange_policy
                        else None
                    ),
                    "source_url": str(policy.source_url) if policy.source_url else None,
                    "raw_text": policy.raw_text,
                    "confidence_score": policy.confidence_score,
                    "last_verified": policy.last_verified or now,
                    "needs_verification": policy.needs_verification,
                    "interpretation_notes": policy.interpretation_notes,
                    "updated_at": now,
                },
            )
            .returning(self.table)
        )

        result = self.session.execute(stmt)
        row = result.fetchone()
        return self._row_to_model(row)

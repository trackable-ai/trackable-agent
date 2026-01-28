"""
Unit of Work pattern for transaction coordination.

Provides a clean way to work with multiple repositories within a single transaction.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from trackable.db.connection import DatabaseConnection
from trackable.db.repositories.job import JobRepository
from trackable.db.repositories.merchant import MerchantRepository
from trackable.db.repositories.oauth_token import OAuthTokenRepository
from trackable.db.repositories.order import OrderRepository
from trackable.db.repositories.shipment import ShipmentRepository
from trackable.db.repositories.source import SourceRepository
from trackable.db.repositories.user import UserRepository

if TYPE_CHECKING:
    from sqlalchemy.orm import Session


class UnitOfWork:
    """
    Unit of Work for managing database transactions.

    Coordinates multiple repositories within a single transaction,
    ensuring atomic operations with automatic commit/rollback.

    Usage:
        with UnitOfWork() as uow:
            merchant = uow.merchants.upsert_by_domain(merchant_data)
            order = uow.orders.create(order_data)
            uow.commit()  # Explicit commit

        # Auto-rollback on exception:
        with UnitOfWork() as uow:
            uow.jobs.mark_started(job_id)
            raise Exception("Something went wrong")
            # Transaction is automatically rolled back
    """

    def __init__(self):
        self._session: Session | None = None
        self._jobs: JobRepository | None = None
        self._merchants: MerchantRepository | None = None
        self._oauth_tokens: OAuthTokenRepository | None = None
        self._orders: OrderRepository | None = None
        self._shipments: ShipmentRepository | None = None
        self._sources: SourceRepository | None = None
        self._users: UserRepository | None = None

    def __enter__(self) -> UnitOfWork:
        self._session = DatabaseConnection.get_session()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if exc_type is not None:
            self.rollback()
        self._close()
        return False  # Don't suppress exceptions

    @property
    def session(self) -> Session:
        """Get current session (raises if not in context)."""
        if self._session is None:
            raise RuntimeError("UnitOfWork must be used within a context manager")
        return self._session

    @property
    def jobs(self) -> JobRepository:
        """Job repository for this unit of work."""
        if self._jobs is None:
            self._jobs = JobRepository(self.session)
        return self._jobs

    @property
    def merchants(self) -> MerchantRepository:
        """Merchant repository for this unit of work."""
        if self._merchants is None:
            self._merchants = MerchantRepository(self.session)
        return self._merchants

    @property
    def oauth_tokens(self) -> OAuthTokenRepository:
        """OAuth token repository for this unit of work."""
        if self._oauth_tokens is None:
            self._oauth_tokens = OAuthTokenRepository(self.session)
        return self._oauth_tokens

    @property
    def orders(self) -> OrderRepository:
        """Order repository for this unit of work."""
        if self._orders is None:
            self._orders = OrderRepository(self.session)
        return self._orders

    @property
    def shipments(self) -> ShipmentRepository:
        """Shipment repository for this unit of work."""
        if self._shipments is None:
            self._shipments = ShipmentRepository(self.session)
        return self._shipments

    @property
    def sources(self) -> SourceRepository:
        """Source repository for this unit of work."""
        if self._sources is None:
            self._sources = SourceRepository(self.session)
        return self._sources

    @property
    def users(self) -> UserRepository:
        """User repository for this unit of work."""
        if self._users is None:
            self._users = UserRepository(self.session)
        return self._users

    def commit(self):
        """Commit the current transaction."""
        self.session.commit()

    def rollback(self):
        """Rollback the current transaction."""
        self.session.rollback()

    def _close(self):
        """Close the session."""
        if self._session is not None:
            self._session.close()
            self._session = None
            self._jobs = None
            self._merchants = None
            self._oauth_tokens = None
            self._orders = None
            self._shipments = None
            self._sources = None
            self._users = None

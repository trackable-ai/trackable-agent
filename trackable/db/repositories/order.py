"""
Order repository for database operations.

Handles order CRUD with JSONB serialization for nested models.
"""

from datetime import datetime, timezone
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import Table, select

from trackable.db.repositories.base import (
    BaseRepository,
    jsonb_to_model,
    jsonb_to_models,
    model_to_jsonb,
    models_to_jsonb,
)
from trackable.db.tables import orders
from trackable.models.order import (
    Item,
    Merchant,
    Money,
    Order,
    OrderStatus,
    SourceType,
)


class OrderRepository(BaseRepository[Order]):
    """Repository for Order operations with JSONB handling."""

    @property
    def table(self) -> Table:
        return orders

    def _row_to_model(self, row: Any) -> Order:
        """Convert database row to Order model."""
        # Reconstruct Merchant (minimal - need merchant repo for full data)
        merchant = Merchant(
            id=str(row.merchant_id),
            name="",  # Will be populated from merchant table if needed
        )

        return Order(
            id=str(row.id),
            user_id=str(row.user_id),
            merchant=merchant,
            order_number=row.order_number,
            order_date=row.order_date,
            status=OrderStatus(row.status),
            country_code=row.country_code,
            items=jsonb_to_models(row.items, Item),
            subtotal=jsonb_to_model(row.subtotal, Money),
            tax=jsonb_to_model(row.tax, Money),
            shipping_cost=jsonb_to_model(row.shipping_cost, Money),
            total=jsonb_to_model(row.total, Money),
            return_window_start=row.return_window_start,
            return_window_end=row.return_window_end,
            return_window_days=row.return_window_days,
            exchange_window_end=row.exchange_window_end,
            is_monitored=row.is_monitored if row.is_monitored is not None else True,
            source_type=SourceType(row.source_type),
            source_id=row.source_id,
            confidence_score=(
                float(row.confidence_score) if row.confidence_score else None
            ),
            needs_clarification=row.needs_clarification or False,
            clarification_questions=row.clarification_questions or [],
            order_url=row.order_url,
            receipt_url=row.receipt_url,
            refund_initiated=row.refund_initiated or False,
            refund_amount=jsonb_to_model(row.refund_amount, Money),
            refund_completed_at=row.refund_completed_at,
            notes=row.notes or [],
            last_agent_intervention=row.last_agent_intervention,
            created_at=row.created_at,
            updated_at=row.updated_at,
        )

    def _model_to_dict(self, model: Order) -> dict:
        """Convert Order model to database dict."""
        now = datetime.now(timezone.utc)
        return {
            "id": UUID(model.id) if model.id else uuid4(),
            "user_id": UUID(model.user_id),
            "merchant_id": UUID(model.merchant.id),
            "order_number": model.order_number,
            "order_date": model.order_date,
            "status": model.status.value,
            "country_code": model.country_code,
            "items": models_to_jsonb(model.items),
            "subtotal": model_to_jsonb(model.subtotal),
            "tax": model_to_jsonb(model.tax),
            "shipping_cost": model_to_jsonb(model.shipping_cost),
            "total": model_to_jsonb(model.total),
            "return_window_start": model.return_window_start,
            "return_window_end": model.return_window_end,
            "return_window_days": model.return_window_days,
            "exchange_window_end": model.exchange_window_end,
            "is_monitored": model.is_monitored,
            "source_type": model.source_type.value,
            "source_id": model.source_id,
            "confidence_score": model.confidence_score,
            "needs_clarification": model.needs_clarification,
            "clarification_questions": model.clarification_questions,
            "order_url": str(model.order_url) if model.order_url else None,
            "receipt_url": str(model.receipt_url) if model.receipt_url else None,
            "refund_initiated": model.refund_initiated,
            "refund_amount": model_to_jsonb(model.refund_amount),
            "refund_completed_at": model.refund_completed_at,
            "notes": model.notes,
            "last_agent_intervention": model.last_agent_intervention,
            "created_at": now,
            "updated_at": now,
        }

    def get_by_user(
        self,
        user_id: str,
        status: OrderStatus | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[Order]:
        """
        Get orders for a user.

        Args:
            user_id: User ID
            status: Optional status filter
            limit: Maximum number of orders
            offset: Pagination offset

        Returns:
            List of orders
        """
        stmt = select(self.table).where(self.table.c.user_id == UUID(user_id))

        if status:
            stmt = stmt.where(self.table.c.status == status.value)

        stmt = stmt.order_by(self.table.c.created_at.desc()).limit(limit).offset(offset)

        result = self.session.execute(stmt)
        return [self._row_to_model(row) for row in result.fetchall()]

    def get_by_order_number(self, user_id: str, order_number: str) -> Order | None:
        """
        Get order by merchant order number.

        Args:
            user_id: User ID
            order_number: Merchant order number

        Returns:
            Order or None
        """
        stmt = select(self.table).where(
            self.table.c.user_id == UUID(user_id),
            self.table.c.order_number == order_number,
        )
        result = self.session.execute(stmt)
        row = result.fetchone()

        if row is None:
            return None

        return self._row_to_model(row)

    def get_monitored_orders(self, user_id: str | None = None) -> list[Order]:
        """
        Get orders that are being actively monitored.

        Args:
            user_id: Optional user ID filter

        Returns:
            List of monitored orders
        """
        stmt = select(self.table).where(self.table.c.is_monitored == True)  # noqa: E712

        if user_id:
            stmt = stmt.where(self.table.c.user_id == UUID(user_id))

        stmt = stmt.order_by(self.table.c.return_window_end.asc())

        result = self.session.execute(stmt)
        return [self._row_to_model(row) for row in result.fetchall()]

    def get_orders_with_expiring_return_window(
        self, days_until_expiry: int, user_id: str | None = None
    ) -> list[Order]:
        """
        Get orders with return windows expiring within specified days.

        Args:
            days_until_expiry: Days until return window expires
            user_id: Optional user ID filter

        Returns:
            List of orders with expiring return windows
        """
        from datetime import timedelta

        now = datetime.now(timezone.utc)
        expiry_threshold = now + timedelta(days=days_until_expiry)

        stmt = select(self.table).where(
            self.table.c.is_monitored == True,  # noqa: E712
            self.table.c.return_window_end.isnot(None),
            self.table.c.return_window_end <= expiry_threshold,
            self.table.c.return_window_end > now,
        )

        if user_id:
            stmt = stmt.where(self.table.c.user_id == UUID(user_id))

        stmt = stmt.order_by(self.table.c.return_window_end.asc())

        result = self.session.execute(stmt)
        return [self._row_to_model(row) for row in result.fetchall()]

    def update_status(self, order_id: str | UUID, status: OrderStatus) -> bool:
        """
        Update order status.

        Args:
            order_id: Order ID
            status: New status

        Returns:
            True if order was updated
        """
        now = datetime.now(timezone.utc)
        return self.update_by_id(
            order_id,
            status=status.value,
            updated_at=now,
        )

    def add_note(self, order_id: str | UUID, note: str) -> bool:
        """
        Add a note to order.

        Args:
            order_id: Order ID
            note: Note text

        Returns:
            True if note was added
        """
        order = self.get_by_id(order_id)
        if order is None:
            return False

        now = datetime.now(timezone.utc)
        notes = order.notes + [note]

        return self.update_by_id(
            order_id,
            notes=notes,
            last_agent_intervention=now,
            updated_at=now,
        )

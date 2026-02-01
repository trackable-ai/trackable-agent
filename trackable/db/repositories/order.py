"""
Order repository for database operations.

Handles order CRUD with JSONB serialization for nested models.
"""

from datetime import datetime, timezone
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import Table, and_, case, func, or_, select, text

from trackable.db.repositories.base import (
    BaseRepository,
    jsonb_to_model,
    jsonb_to_models,
    model_to_jsonb,
    models_to_jsonb,
)
from trackable.db.tables import merchants, orders
from trackable.models.order import Item, Merchant, Money, Order, OrderStatus, SourceType

# Order status progression - higher index = later in lifecycle
# Used to prevent status regression during upsert
ORDER_STATUS_PROGRESSION = [
    OrderStatus.UNKNOWN,
    OrderStatus.DETECTED,
    OrderStatus.CONFIRMED,
    OrderStatus.SHIPPED,
    OrderStatus.IN_TRANSIT,
    OrderStatus.DELIVERED,
    OrderStatus.RETURNED,
    OrderStatus.REFUNDED,
    OrderStatus.CANCELLED,
]


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
        include_history: bool = False,
    ) -> list[Order]:
        """
        Get orders for a user.

        By default, deduplicates using DISTINCT ON to return only the latest
        status per order. Set include_history=True to return all rows.

        Args:
            user_id: User ID
            status: Optional status filter
            limit: Maximum number of orders
            offset: Pagination offset
            include_history: If True, return all status rows

        Returns:
            List of orders
        """
        if include_history:
            stmt = select(self.table).where(self.table.c.user_id == UUID(user_id))
            if status:
                stmt = stmt.where(self.table.c.status == status.value)
            stmt = (
                stmt.order_by(self.table.c.created_at.desc())
                .limit(limit)
                .offset(offset)
            )
        else:
            status_order = self._status_order_expression()
            stmt = (
                select(self.table)
                .distinct(
                    self.table.c.user_id,
                    self.table.c.merchant_id,
                    self.table.c.order_number,
                )
                .where(self.table.c.user_id == UUID(user_id))
                .order_by(
                    self.table.c.user_id,
                    self.table.c.merchant_id,
                    self.table.c.order_number,
                    status_order.desc(),
                )
            )
            if status:
                subq = stmt.subquery()
                stmt = select(subq).where(subq.c.status == status.value)
            stmt = stmt.limit(limit).offset(offset)

        result = self.session.execute(stmt)
        return [self._row_to_model(row) for row in result.fetchall()]

    def count_by_user(
        self,
        user_id: str,
        status: OrderStatus | None = None,
        include_history: bool = False,
    ) -> int:
        """
        Count orders for a user.

        By default counts distinct orders (one per order_number+merchant).
        Set include_history=True to count all status rows.

        Args:
            user_id: User ID
            status: Optional status filter
            include_history: If True, count all status rows

        Returns:
            Number of orders
        """
        if include_history:
            stmt = (
                select(func.count())
                .select_from(self.table)
                .where(self.table.c.user_id == UUID(user_id))
            )
            if status:
                stmt = stmt.where(self.table.c.status == status.value)
        else:
            # Count distinct (user_id, merchant_id, order_number) combos
            status_order = self._status_order_expression()
            subq = (
                select(self.table)
                .distinct(
                    self.table.c.user_id,
                    self.table.c.merchant_id,
                    self.table.c.order_number,
                )
                .where(self.table.c.user_id == UUID(user_id))
                .order_by(
                    self.table.c.user_id,
                    self.table.c.merchant_id,
                    self.table.c.order_number,
                    status_order.desc(),
                )
                .subquery()
            )
            if status:
                stmt = (
                    select(func.count())
                    .select_from(subq)
                    .where(subq.c.status == status.value)
                )
            else:
                stmt = select(func.count()).select_from(subq)

        result = self.session.execute(stmt)
        return result.scalar() or 0

    def get_by_id_for_user(self, order_id: str, user_id: str) -> Order | None:
        """
        Get latest-status order by ID, scoped to a specific user.

        Args:
            order_id: Order ID
            user_id: User ID (for authorization)

        Returns:
            Order if found and belongs to user, None otherwise
        """
        status_order = self._status_order_expression()
        stmt = (
            select(self.table)
            .where(
                self.table.c.id == UUID(order_id),
                self.table.c.user_id == UUID(user_id),
            )
            .order_by(status_order.desc())
            .limit(1)
        )
        result = self.session.execute(stmt)
        row = result.fetchone()

        if row is None:
            return None

        return self._row_to_model(row)

    def get_by_order_number(self, user_id: str, order_number: str) -> Order | None:
        """
        Get latest-status order by merchant order number.

        With order history, multiple rows can share the same order_number.
        This returns the row with the highest status in the progression.

        Args:
            user_id: User ID
            order_number: Merchant order number

        Returns:
            Order with the highest status, or None
        """
        status_order = self._status_order_expression()
        stmt = (
            select(self.table)
            .where(
                self.table.c.user_id == UUID(user_id),
                self.table.c.order_number == order_number,
            )
            .order_by(status_order.desc())
            .limit(1)
        )
        result = self.session.execute(stmt)
        row = result.fetchone()

        if row is None:
            return None

        return self._row_to_model(row)

    def search(self, user_id: str, query: str, limit: int = 20) -> list[Order]:
        """
        Search orders by partial match on order number, merchant name, or item name.

        Uses case-insensitive partial matching (ILIKE) across:
        - Order number
        - Merchant name (via JOIN)
        - Item names (via JSONB array extraction)

        Args:
            user_id: User ID (authorization scope)
            query: Search string
            limit: Maximum results (default 20)

        Returns:
            List of matching orders with merchant name populated.
        """
        pattern = f"%{query}%"

        stmt = (
            select(
                self.table,
                merchants.c.name.label("merchant_name"),
                merchants.c.domain.label("merchant_domain"),
            )
            .join(merchants, self.table.c.merchant_id == merchants.c.id)
            .where(self.table.c.user_id == UUID(user_id))
            .where(
                or_(
                    self.table.c.order_number.ilike(pattern),
                    merchants.c.name.ilike(pattern),
                    text(
                        "EXISTS (SELECT 1 FROM jsonb_array_elements(orders.items) elem "
                        "WHERE elem->>'name' ILIKE :item_pattern)"
                    ),
                )
            )
            .order_by(self.table.c.created_at.desc())
            .limit(limit)
        )

        result = self.session.execute(stmt, {"item_pattern": pattern})
        results = []
        for row in result.fetchall():
            order = self._row_to_model(row)
            order.merchant.name = row.merchant_name
            order.merchant.domain = row.merchant_domain
            results.append(order)
        return results

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

    def get_by_unique_key(
        self,
        user_id: str,
        merchant_id: str,
        order_number: str,
        status: OrderStatus | None = None,
    ) -> Order | None:
        """
        Get order by unique key: user_id + merchant_id + order_number + (optional) status.

        Args:
            user_id: User ID
            merchant_id: Merchant ID
            order_number: Merchant order number
            status: Optional status for the composite unique key

        Returns:
            Order or None if not found
        """
        conditions = [
            self.table.c.user_id == UUID(user_id),
            self.table.c.merchant_id == UUID(merchant_id),
            self.table.c.order_number == order_number,
        ]
        if status is not None:
            conditions.append(self.table.c.status == status.value)

        stmt = select(self.table).where(and_(*conditions))
        result = self.session.execute(stmt)
        row = result.fetchone()

        if row is None:
            return None

        return self._row_to_model(row)

    def _merge_orders(self, existing: Order, incoming: Order) -> dict:
        """
        Merge incoming order data with existing order.

        Under the new order history model, merge only happens between rows
        with the same status (status is part of the unique key). Status is
        never changed during merge.

        Merge strategy:
        - Items: Replace with incoming if provided
        - Notes: Append new notes
        - Money fields: Use incoming if provided, else keep existing
        - Return windows: Preserve existing if set, else use incoming
        - Confidence: Use higher score
        - URLs: Use incoming if provided
        - Other fields: Use incoming if provided, else keep existing

        Args:
            existing: Existing order in database
            incoming: New order data from parsing

        Returns:
            Dictionary of fields to update
        """
        now = datetime.now(timezone.utc)
        updates: dict[str, Any] = {"updated_at": now}

        # Order date - use incoming if existing is None
        if existing.order_date is None and incoming.order_date is not None:
            updates["order_date"] = incoming.order_date

        # Country code - use incoming if existing is None
        if existing.country_code is None and incoming.country_code is not None:
            updates["country_code"] = incoming.country_code

        # Items - replace with incoming if provided
        if incoming.items:
            updates["items"] = models_to_jsonb(incoming.items)

        # Money fields - use incoming if provided
        if incoming.subtotal is not None:
            updates["subtotal"] = model_to_jsonb(incoming.subtotal)
        if incoming.tax is not None:
            updates["tax"] = model_to_jsonb(incoming.tax)
        if incoming.shipping_cost is not None:
            updates["shipping_cost"] = model_to_jsonb(incoming.shipping_cost)
        if incoming.total is not None:
            updates["total"] = model_to_jsonb(incoming.total)

        # Return windows - preserve existing if set
        if existing.return_window_start is None and incoming.return_window_start:
            updates["return_window_start"] = incoming.return_window_start
        if existing.return_window_end is None and incoming.return_window_end:
            updates["return_window_end"] = incoming.return_window_end
        if existing.return_window_days is None and incoming.return_window_days:
            updates["return_window_days"] = incoming.return_window_days
        if existing.exchange_window_end is None and incoming.exchange_window_end:
            updates["exchange_window_end"] = incoming.exchange_window_end

        # Confidence score - use higher value
        if incoming.confidence_score is not None:
            if (
                existing.confidence_score is None
                or incoming.confidence_score > existing.confidence_score
            ):
                updates["confidence_score"] = incoming.confidence_score

        # Clarification - update if incoming needs clarification
        if incoming.needs_clarification:
            updates["needs_clarification"] = True
            # Append new questions, avoid duplicates
            all_questions = list(existing.clarification_questions)
            for q in incoming.clarification_questions:
                if q not in all_questions:
                    all_questions.append(q)
            if all_questions != existing.clarification_questions:
                updates["clarification_questions"] = all_questions

        # URLs - use incoming if provided
        if incoming.order_url is not None:
            updates["order_url"] = str(incoming.order_url)
        if incoming.receipt_url is not None:
            updates["receipt_url"] = str(incoming.receipt_url)

        # Refund tracking - update if incoming has refund info
        if incoming.refund_initiated and not existing.refund_initiated:
            updates["refund_initiated"] = True
        if incoming.refund_amount is not None:
            updates["refund_amount"] = model_to_jsonb(incoming.refund_amount)
        if incoming.refund_completed_at is not None:
            updates["refund_completed_at"] = incoming.refund_completed_at

        # Notes - append new notes (avoid duplicates)
        if incoming.notes:
            all_notes = list(existing.notes)
            for note in incoming.notes:
                if note not in all_notes:
                    all_notes.append(note)
            if all_notes != existing.notes:
                updates["notes"] = all_notes

        return updates

    def upsert_by_order_number(self, order: Order) -> tuple[Order, bool]:
        """
        Insert or update order by unique key (user_id + merchant_id + order_number + status).

        If an order with the same order_number, merchant_id, user_id, and status
        exists, the existing order is updated with merged data. Otherwise, a new
        order row is created. This means a new status for the same order creates
        a new row (preserving order history).

        Args:
            order: Order to upsert

        Returns:
            Tuple of (Order, is_new) where is_new is True if a new order was created
        """
        # Check for existing order by unique key (now includes status)
        existing = self.get_by_unique_key(
            user_id=order.user_id,
            merchant_id=order.merchant.id,
            order_number=order.order_number,
            status=order.status,
        )

        if existing is None:
            # No existing order - create new
            return self.create(order), True

        # Merge and update existing order
        updates = self._merge_orders(existing, order)

        if updates and len(updates) > 1:  # More than just updated_at
            self.update_by_id(existing.id, **updates)
            # Fetch updated order
            updated = self.get_by_id(existing.id)
            if updated is None:
                # Should not happen, but return existing as fallback
                return existing, False
            return updated, False

        # No changes needed
        return existing, False

    def _status_order_expression(self):
        """Build a CASE expression that maps status to progression index."""
        return case(
            {s.value: i for i, s in enumerate(ORDER_STATUS_PROGRESSION)},
            value=self.table.c.status,
            else_=len(ORDER_STATUS_PROGRESSION),
        )

    def get_order_history(
        self, user_id: str, merchant_id: str, order_number: str
    ) -> list[Order]:
        """Get all status rows for an order, ordered by status progression."""
        status_order = self._status_order_expression()
        stmt = (
            select(self.table)
            .where(
                and_(
                    self.table.c.user_id == UUID(user_id),
                    self.table.c.merchant_id == UUID(merchant_id),
                    self.table.c.order_number == order_number,
                )
            )
            .order_by(status_order.asc())
        )
        result = self.session.execute(stmt)
        return [self._row_to_model(row) for row in result.fetchall()]

    def get_latest_order(
        self, user_id: str, merchant_id: str, order_number: str
    ) -> Order | None:
        """Get the highest-status row for an order."""
        status_order = self._status_order_expression()
        stmt = (
            select(self.table)
            .where(
                and_(
                    self.table.c.user_id == UUID(user_id),
                    self.table.c.merchant_id == UUID(merchant_id),
                    self.table.c.order_number == order_number,
                )
            )
            .order_by(status_order.desc())
            .limit(1)
        )
        result = self.session.execute(stmt)
        row = result.fetchone()
        if row is None:
            return None
        return self._row_to_model(row)

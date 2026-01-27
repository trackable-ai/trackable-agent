"""
Shipment repository for database operations.

Handles shipment CRUD with tracking event JSONB handling.
"""

from datetime import datetime, timezone
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import Table, select

from trackable.db.repositories.base import (
    BaseRepository,
    jsonb_to_models,
    models_to_jsonb,
)
from trackable.db.tables import shipments
from trackable.models.order import (
    Carrier,
    Shipment,
    ShipmentStatus,
    TrackingEvent,
)


class ShipmentRepository(BaseRepository[Shipment]):
    """Repository for Shipment operations with tracking event handling."""

    @property
    def table(self) -> Table:
        return shipments

    def _row_to_model(self, row: Any) -> Shipment:
        """Convert database row to Shipment model."""
        return Shipment(
            id=str(row.id),
            order_id=str(row.order_id),
            tracking_number=row.tracking_number,
            carrier=Carrier(row.carrier) if row.carrier else Carrier.UNKNOWN,
            status=ShipmentStatus(row.status) if row.status else ShipmentStatus.PENDING,
            shipping_address=row.shipping_address,
            return_address=row.return_address,
            shipped_at=row.shipped_at,
            estimated_delivery=row.estimated_delivery,
            delivered_at=row.delivered_at,
            tracking_url=row.tracking_url,
            events=jsonb_to_models(row.events, TrackingEvent),
            last_updated=row.last_updated,
        )

    def _model_to_dict(self, model: Shipment) -> dict:
        """Convert Shipment model to database dict."""
        now = datetime.now(timezone.utc)
        return {
            "id": UUID(model.id) if model.id else uuid4(),
            "order_id": UUID(model.order_id),
            "tracking_number": model.tracking_number,
            "carrier": model.carrier.value,
            "status": model.status.value,
            "shipping_address": model.shipping_address,
            "return_address": model.return_address,
            "shipped_at": model.shipped_at,
            "estimated_delivery": model.estimated_delivery,
            "delivered_at": model.delivered_at,
            "tracking_url": str(model.tracking_url) if model.tracking_url else None,
            "events": models_to_jsonb(model.events),
            "last_updated": model.last_updated,
            "created_at": now,
            "updated_at": now,
        }

    def get_by_order(self, order_id: str | UUID) -> list[Shipment]:
        """
        Get all shipments for an order.

        Args:
            order_id: Order ID

        Returns:
            List of shipments
        """
        if isinstance(order_id, str):
            order_id = UUID(order_id)

        stmt = select(self.table).where(self.table.c.order_id == order_id)
        stmt = stmt.order_by(self.table.c.created_at.asc())

        result = self.session.execute(stmt)
        return [self._row_to_model(row) for row in result.fetchall()]

    def get_by_tracking_number(self, tracking_number: str) -> Shipment | None:
        """
        Get shipment by tracking number.

        Args:
            tracking_number: Carrier tracking number

        Returns:
            Shipment or None
        """
        stmt = select(self.table).where(self.table.c.tracking_number == tracking_number)
        result = self.session.execute(stmt)
        row = result.fetchone()

        if row is None:
            return None

        return self._row_to_model(row)

    def update_status(
        self,
        shipment_id: str | UUID,
        status: ShipmentStatus,
        delivered_at: datetime | None = None,
    ) -> bool:
        """
        Update shipment status.

        Args:
            shipment_id: Shipment ID
            status: New status
            delivered_at: Optional delivery timestamp

        Returns:
            True if shipment was updated
        """
        now = datetime.now(timezone.utc)
        update_fields = {
            "status": status.value,
            "last_updated": now,
            "updated_at": now,
        }

        if delivered_at:
            update_fields["delivered_at"] = delivered_at

        return self.update_by_id(shipment_id, **update_fields)

    def add_tracking_event(self, shipment_id: str | UUID, event: TrackingEvent) -> bool:
        """
        Add a tracking event to shipment.

        Args:
            shipment_id: Shipment ID
            event: Tracking event to add

        Returns:
            True if event was added
        """
        shipment = self.get_by_id(shipment_id)
        if shipment is None:
            return False

        now = datetime.now(timezone.utc)
        events = shipment.events + [event]

        return self.update_by_id(
            shipment_id,
            events=models_to_jsonb(events),
            status=event.status.value,
            last_updated=now,
            updated_at=now,
        )

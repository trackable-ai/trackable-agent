"""
Shipment management API routes.

These endpoints allow updating shipment status and tracking events.
Shipments are accessed through their parent orders for authorization.
"""

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException

from trackable.api.auth import get_user_id
from trackable.db import DatabaseConnection, UnitOfWork
from trackable.models.order import Shipment

router = APIRouter()


def _check_db_available():
    """Check if database is available, raise 503 if not."""
    if not DatabaseConnection.is_initialized():
        raise HTTPException(
            status_code=503,
            detail="Database not available",
        )


@router.get("/orders/{order_id}/shipments/{shipment_id}", response_model=Shipment)
async def get_shipment(
    order_id: str,
    shipment_id: str,
    user_id: str = Depends(get_user_id),
) -> Shipment:
    """
    Get shipment details by ID.

    Args:
        order_id: Parent order UUID
        shipment_id: Shipment UUID
        user_id: User ID from X-User-ID header

    Returns:
        Shipment details

    Raises:
        404: Order or shipment not found
    """
    _check_db_available()

    with UnitOfWork() as uow:
        # Verify order exists and belongs to user
        order = uow.orders.get_by_id_for_user(order_id, user_id)
        if order is None:
            raise HTTPException(
                status_code=404,
                detail=f"Order not found: {order_id}",
            )

        shipment = uow.shipments.get_by_id(shipment_id)
        if shipment is None or shipment.order_id != order_id:
            raise HTTPException(
                status_code=404,
                detail=f"Shipment not found: {shipment_id}",
            )

        return shipment

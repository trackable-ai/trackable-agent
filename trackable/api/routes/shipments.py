"""
Shipment management API routes.

These endpoints allow updating shipment status and tracking events.
Shipments are accessed through their parent orders for authorization.
"""

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException

from trackable.api.auth import get_user_id
from trackable.db import DatabaseConnection, UnitOfWork
from trackable.models.order import Shipment, ShipmentStatus, ShipmentUpdateRequest

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


@router.patch("/orders/{order_id}/shipments/{shipment_id}", response_model=Shipment)
async def update_shipment(
    order_id: str,
    shipment_id: str,
    request: ShipmentUpdateRequest,
    user_id: str = Depends(get_user_id),
) -> Shipment:
    """
    Update shipment details.

    Allows updating:
    - status: Change shipment status
    - tracking_number: Update tracking number
    - carrier: Update carrier
    - estimated_delivery: Update estimated delivery
    - delivered_at: Set delivery timestamp

    Args:
        order_id: Parent order UUID
        shipment_id: Shipment UUID
        request: Fields to update
        user_id: User ID from X-User-ID header

    Returns:
        Updated shipment

    Raises:
        404: Order or shipment not found
    """
    _check_db_available()

    try:
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

            # Handle status update via dedicated method
            if request.status is not None:
                uow.shipments.update_status(
                    shipment_id,
                    request.status,
                    delivered_at=request.delivered_at,
                )

            # Build update fields for other properties
            now = datetime.now(timezone.utc)
            update_fields: dict = {"updated_at": now}

            if request.tracking_number is not None:
                update_fields["tracking_number"] = request.tracking_number

            if request.carrier is not None:
                update_fields["carrier"] = request.carrier.value

            if request.estimated_delivery is not None:
                update_fields["estimated_delivery"] = request.estimated_delivery

            # Only update if there are fields to update
            if len(update_fields) > 1:  # More than just updated_at
                uow.shipments.update_by_id(shipment_id, **update_fields)

            uow.commit()

            # Fetch updated shipment
            updated_shipment = uow.shipments.get_by_id(shipment_id)
            if updated_shipment is None:
                raise HTTPException(
                    status_code=500,
                    detail="Failed to retrieve updated shipment",
                )

            return updated_shipment

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to update shipment: {str(e)}",
        )

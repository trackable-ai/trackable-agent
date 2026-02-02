"""
Shipment management API routes.

These endpoints allow updating shipment status and tracking events.
Shipments are accessed through their parent orders for authorization.
"""

from datetime import datetime, timezone
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException

from trackable.api.auth import get_user_id
from trackable.db import DatabaseConnection, UnitOfWork
from trackable.models.order import (
    Shipment,
    ShipmentCreateRequest,
    ShipmentStatus,
    ShipmentUpdateRequest,
    TrackingEvent,
    TrackingEventRequest,
)

router = APIRouter()


def _check_db_available():
    """Check if database is available, raise 503 if not."""
    if not DatabaseConnection.is_initialized():
        raise HTTPException(
            status_code=503,
            detail="Database not available",
        )


@router.get("/orders/{order_id}/shipments", response_model=list[Shipment])
async def list_shipments(
    order_id: str,
    user_id: str = Depends(get_user_id),
) -> list[Shipment]:
    """
    List all shipments for an order.

    Args:
        order_id: Parent order UUID
        user_id: User ID from X-User-ID header

    Returns:
        List of shipments

    Raises:
        404: Order not found
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

        return uow.shipments.get_by_order(order_id)


@router.post("/orders/{order_id}/shipments", response_model=Shipment, status_code=201)
async def create_shipment(
    order_id: str,
    request: ShipmentCreateRequest,
    user_id: str = Depends(get_user_id),
) -> Shipment:
    """
    Create a new shipment for an order.

    Args:
        order_id: Parent order UUID
        request: Shipment creation data
        user_id: User ID from X-User-ID header

    Returns:
        Created shipment

    Raises:
        404: Order not found
        409: Shipment with tracking number already exists
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

            # Check for duplicate tracking number
            if request.tracking_number:
                existing = uow.shipments.get_by_tracking_number(request.tracking_number)
                if existing is not None:
                    raise HTTPException(
                        status_code=409,
                        detail=f"Shipment with tracking number already exists: {request.tracking_number}",
                    )

            # Create shipment model
            shipment = Shipment(
                id=str(uuid4()),
                order_id=order_id,
                tracking_number=request.tracking_number,
                carrier=request.carrier,
                status=request.status,
                shipping_address=request.shipping_address,
                return_address=request.return_address,
                estimated_delivery=request.estimated_delivery,
            )

            created = uow.shipments.create(shipment)
            uow.commit()

            return created

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to create shipment: {str(e)}",
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


@router.post(
    "/orders/{order_id}/shipments/{shipment_id}/events", response_model=Shipment
)
async def add_tracking_event(
    order_id: str,
    shipment_id: str,
    request: TrackingEventRequest,
    user_id: str = Depends(get_user_id),
) -> Shipment:
    """
    Add a tracking event to a shipment.

    This appends a new event to the shipment's tracking history
    and updates the shipment status to match the event status.

    Args:
        order_id: Parent order UUID
        shipment_id: Shipment UUID
        request: Tracking event data
        user_id: User ID from X-User-ID header

    Returns:
        Updated shipment with new event

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

            # Create tracking event
            event = TrackingEvent(
                timestamp=request.timestamp or datetime.now(timezone.utc),
                status=request.status,
                location=request.location,
                description=request.description,
            )

            # Add event (this also updates shipment status)
            success = uow.shipments.add_tracking_event(shipment_id, event)
            if not success:
                raise HTTPException(
                    status_code=500,
                    detail="Failed to add tracking event",
                )

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
            detail=f"Failed to add tracking event: {str(e)}",
        )

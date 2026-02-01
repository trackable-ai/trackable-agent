"""
Order management API routes.

These endpoints allow users to view, update, and delete their orders.
"""

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query

from trackable.api.auth import get_user_id
from trackable.db import DatabaseConnection, UnitOfWork
from trackable.models.order import (
    Order,
    OrderHistoryResponse,
    OrderListResponse,
    OrderStatus,
    OrderTimelineEntry,
    OrderUpdateRequest,
)

router = APIRouter()


def _check_db_available():
    """Check if database is available, raise 503 if not."""
    if not DatabaseConnection.is_initialized():
        raise HTTPException(
            status_code=503,
            detail="Database not available",
        )


@router.get("/orders", response_model=OrderListResponse)
async def list_orders(
    user_id: str = Depends(get_user_id),
    status: str | None = Query(default=None, description="Filter by order status"),
    limit: int = Query(default=100, le=500, description="Maximum orders to return"),
    offset: int = Query(default=0, ge=0, description="Number of orders to skip"),
    include_history: bool = Query(
        default=False, description="If true, return all status rows per order"
    ),
) -> OrderListResponse:
    """
    List user's orders with optional filtering and pagination.

    By default, returns one row per order (the latest status). Set
    include_history=true to return all status rows.

    Args:
        user_id: User ID from X-User-ID header
        status: Optional status filter (e.g., "delivered", "shipped")
        limit: Maximum number of orders to return (max 500)
        offset: Number of orders to skip for pagination
        include_history: Return all status rows when true

    Returns:
        OrderListResponse with orders and pagination info
    """
    _check_db_available()

    # Parse status filter if provided
    order_status = None
    if status:
        try:
            order_status = OrderStatus(status)
        except ValueError:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid status: {status}. Valid values: {[s.value for s in OrderStatus]}",
            )

    with UnitOfWork() as uow:
        orders = uow.orders.get_by_user(
            user_id=user_id,
            status=order_status,
            limit=limit,
            offset=offset,
            include_history=include_history,
        )

        # Get total count for pagination
        total = uow.orders.count_by_user(
            user_id=user_id,
            status=order_status,
            include_history=include_history,
        )

        return OrderListResponse(
            orders=orders,
            total=total,
            limit=limit,
            offset=offset,
        )


@router.get("/orders/{order_id}/history", response_model=OrderHistoryResponse)
async def get_order_history(
    order_id: str,
    user_id: str = Depends(get_user_id),
) -> OrderHistoryResponse:
    """
    Get full order history timeline.

    Returns all status transitions for the order, ordered by status
    progression (earliest to latest).

    Args:
        order_id: Order UUID (any status row for this order)
        user_id: User ID from X-User-ID header

    Returns:
        OrderHistoryResponse with timeline entries
    """
    _check_db_available()

    with UnitOfWork() as uow:
        order = uow.orders.get_by_id_for_user(order_id, user_id)
        if order is None:
            raise HTTPException(
                status_code=404,
                detail=f"Order not found: {order_id}",
            )

        rows = uow.orders.get_order_history(
            user_id=user_id,
            merchant_id=order.merchant.id,
            order_number=order.order_number,
        )
        timeline = [
            OrderTimelineEntry(
                id=row.id,
                status=row.status,
                source_type=row.source_type,
                source_id=row.source_id,
                confidence_score=row.confidence_score,
                notes=row.notes,
                created_at=row.created_at,
                updated_at=row.updated_at,
            )
            for row in rows
        ]
        return OrderHistoryResponse(
            order_number=order.order_number,
            merchant_name=order.merchant.name,
            user_id=user_id,
            timeline=timeline,
        )


@router.get("/orders/{order_id}/latest", response_model=Order)
async def get_order_latest(
    order_id: str,
    user_id: str = Depends(get_user_id),
) -> Order:
    """
    Get latest order details by ID.

    Args:
        order_id: Order UUID
        user_id: User ID from X-User-ID header

    Returns:
        Order details
    """
    _check_db_available()

    with UnitOfWork() as uow:
        order = uow.orders.get_by_id_for_user(order_id, user_id)

        if order is None:
            raise HTTPException(
                status_code=404,
                detail=f"Order not found: {order_id}",
            )

        return order


@router.patch("/orders/{order_id}", response_model=Order)
async def update_order(
    order_id: str,
    request: OrderUpdateRequest,
    user_id: str = Depends(get_user_id),
) -> Order:
    """
    Update order details.

    Allows updating:
    - status: Change order status
    - note: Append a note to the order
    - is_monitored: Enable/disable monitoring

    Args:
        order_id: Order UUID
        request: Fields to update
        user_id: User ID from X-User-ID header

    Returns:
        Updated order

    Raises:
        404: Order not found
        403: Order belongs to another user
    """
    _check_db_available()

    try:
        with UnitOfWork() as uow:
            # Get existing order (scoped to user)
            order = uow.orders.get_by_id_for_user(order_id, user_id)

            if order is None:
                raise HTTPException(
                    status_code=404,
                    detail=f"Order not found: {order_id}",
                )

            # Build update fields
            update_fields: dict = {"updated_at": datetime.now(timezone.utc)}

            if request.status is not None:
                update_fields["status"] = request.status.value

            if request.is_monitored is not None:
                update_fields["is_monitored"] = request.is_monitored

            # Update the order
            uow.orders.update_by_id(order_id, **update_fields)

            # Add note separately (uses special logic to append)
            if request.note is not None:
                uow.orders.add_note(order_id, request.note)

            uow.commit()

            # Fetch updated order
            updated_order = uow.orders.get_by_id(order_id)
            if updated_order is None:
                raise HTTPException(
                    status_code=500,
                    detail="Failed to retrieve updated order",
                )

            return updated_order

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to update order: {str(e)}",
        )


@router.delete("/orders/{order_id}")
async def delete_order(
    order_id: str,
    user_id: str = Depends(get_user_id),
) -> dict:
    """
    Delete an order.

    Args:
        order_id: Order UUID
        user_id: User ID from X-User-ID header

    Returns:
        Confirmation message

    Raises:
        404: Order not found
        403: Order belongs to another user
    """
    _check_db_available()

    try:
        with UnitOfWork() as uow:
            # Get existing order (scoped to user)
            order = uow.orders.get_by_id_for_user(order_id, user_id)

            if order is None:
                raise HTTPException(
                    status_code=404,
                    detail=f"Order not found: {order_id}",
                )

            # Delete the order
            deleted = uow.orders.delete_by_id(order_id)

            if not deleted:
                raise HTTPException(
                    status_code=500,
                    detail="Failed to delete order",
                )

            uow.commit()

            return {"message": f"Order {order_id} deleted successfully"}

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to delete order: {str(e)}",
        )

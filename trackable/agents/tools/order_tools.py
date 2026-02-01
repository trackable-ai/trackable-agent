"""Order query tools for the chatbot agent."""

from datetime import datetime, timezone

from trackable.db.unit_of_work import UnitOfWork
from trackable.models.order import OrderStatus


def get_user_orders(
    user_id: str,
    status: str | None = None,
    limit: int = 20,
) -> dict:
    """Retrieve orders for a user, optionally filtered by status.

    Use this tool to list a user's orders. You can filter by status
    (e.g., "delivered", "shipped", "confirmed") or get all orders.

    Args:
        user_id: The user's unique identifier.
        status: Optional order status filter. Valid values: detected, confirmed,
            shipped, in_transit, delivered, returned, refunded, cancelled.
        limit: Maximum number of orders to return (default 20).

    Returns:
        dict: A summary of the user's orders including count and order details.
    """
    # Validate status if provided
    order_status = None
    if status:
        try:
            order_status = OrderStatus(status.lower())
        except ValueError:
            valid = ", ".join(s.value for s in OrderStatus if s != OrderStatus.UNKNOWN)
            return {
                "status": "error",
                "message": f"Invalid status '{status}'. Valid values: {valid}",
            }

    with UnitOfWork() as uow:
        orders = uow.orders.get_by_user(
            user_id, status=order_status, limit=limit, offset=0
        )
        total = uow.orders.count_by_user(user_id, status=order_status)

    order_summaries = []
    for order in orders:
        item_names = [item.name for item in order.items]
        summary = {
            "order_id": order.id,
            "order_number": order.order_number,
            "merchant": order.merchant.name,
            "status": order.status.value,
            "total": str(order.total) if order.total else "unknown",
            "item_count": len(order.items),
            "items": item_names[:5],  # First 5 item names
            "order_date": (order.order_date.isoformat() if order.order_date else None),
            "return_window_end": (
                order.return_window_end.isoformat() if order.return_window_end else None
            ),
            "is_monitored": order.is_monitored,
        }
        order_summaries.append(summary)

    return {
        "status": "success",
        "total_count": total,
        "showing": len(order_summaries),
        "orders": order_summaries,
    }


def get_order_details(user_id: str, order_id: str) -> dict:
    """Get detailed information about a specific order including items and shipments.

    Use this tool when the user asks about a specific order. Returns full
    details including items, pricing, shipment tracking, and return window info.

    Args:
        user_id: The user's unique identifier.
        order_id: The order's unique identifier.

    Returns:
        dict: Full order details including items, shipments, and return windows.
    """
    with UnitOfWork() as uow:
        order = uow.orders.get_by_id_for_user(order_id, user_id)
        if order is None:
            return {
                "status": "not_found",
                "message": f"Order '{order_id}' not found.",
            }

        shipments = uow.shipments.get_by_order(order_id)

    items_detail = []
    for item in order.items:
        items_detail.append(
            {
                "name": item.name,
                "quantity": item.quantity,
                "price": str(item.price) if item.price else None,
                "size": item.size,
                "color": item.color,
                "is_returnable": item.is_returnable,
            }
        )

    shipment_detail = []
    for s in shipments:
        shipment_detail.append(
            {
                "tracking_number": s.tracking_number,
                "carrier": s.carrier.value,
                "status": s.status.value,
                "shipped_at": s.shipped_at.isoformat() if s.shipped_at else None,
                "estimated_delivery": (
                    s.estimated_delivery.isoformat() if s.estimated_delivery else None
                ),
                "delivered_at": s.delivered_at.isoformat() if s.delivered_at else None,
                "tracking_url": str(s.tracking_url) if s.tracking_url else None,
            }
        )

    return {
        "status": "success",
        "order": {
            "order_id": order.id,
            "order_number": order.order_number,
            "merchant": order.merchant.name,
            "merchant_domain": order.merchant.domain,
            "status": order.status.value,
            "order_date": order.order_date.isoformat() if order.order_date else None,
            "items": items_detail,
            "item_count": len(order.items),
            "subtotal": str(order.subtotal) if order.subtotal else None,
            "tax": str(order.tax) if order.tax else None,
            "shipping_cost": str(order.shipping_cost) if order.shipping_cost else None,
            "total": str(order.total) if order.total else None,
            "shipments": shipment_detail,
            "return_window_end": (
                order.return_window_end.isoformat() if order.return_window_end else None
            ),
            "return_window_days": order.return_window_days,
            "exchange_window_end": (
                order.exchange_window_end.isoformat()
                if order.exchange_window_end
                else None
            ),
            "is_monitored": order.is_monitored,
            "notes": order.notes,
            "needs_clarification": order.needs_clarification,
            "clarification_questions": order.clarification_questions,
        },
    }


def check_return_windows(user_id: str, days_ahead: int = 14) -> dict:
    """Check which orders have return windows expiring soon.

    Use this tool to find orders where the return window is about to close.
    This helps remind users to make return decisions before deadlines pass.

    Args:
        user_id: The user's unique identifier.
        days_ahead: Number of days to look ahead for expiring windows (default 14).

    Returns:
        dict: Orders with expiring return windows and days remaining.
    """
    now = datetime.now(timezone.utc)

    with UnitOfWork() as uow:
        orders = uow.orders.get_orders_with_expiring_return_window(
            days_until_expiry=days_ahead, user_id=user_id
        )

    expiring = []
    for order in orders:
        days_remaining = (order.return_window_end - now).days
        item_names = [item.name for item in order.items]
        expiring.append(
            {
                "order_id": order.id,
                "order_number": order.order_number,
                "merchant": order.merchant.name,
                "return_window_end": order.return_window_end.isoformat(),
                "days_remaining": days_remaining,
                "total": str(order.total) if order.total else "unknown",
                "items": item_names[:5],
            }
        )

    return {
        "status": "success",
        "days_checked": days_ahead,
        "expiring_orders": expiring,
    }


def search_order_by_number(user_id: str, order_number: str) -> dict:
    """Search for an order by its merchant order number.

    Use this tool when the user mentions a specific order number
    (e.g., "What's the status of order ORD-12345?").

    Args:
        user_id: The user's unique identifier.
        order_number: The merchant-assigned order number to search for.

    Returns:
        dict: The matching order's summary, or not_found if no match.
    """
    with UnitOfWork() as uow:
        order = uow.orders.get_by_order_number(user_id, order_number)

    if order is None:
        return {
            "status": "not_found",
            "message": f"No order found with number '{order_number}'.",
        }

    item_names = [item.name for item in order.items]
    return {
        "status": "success",
        "order": {
            "order_id": order.id,
            "order_number": order.order_number,
            "merchant": order.merchant.name,
            "status": order.status.value,
            "total": str(order.total) if order.total else "unknown",
            "item_count": len(order.items),
            "items": item_names[:5],
            "order_date": order.order_date.isoformat() if order.order_date else None,
            "return_window_end": (
                order.return_window_end.isoformat() if order.return_window_end else None
            ),
            "is_monitored": order.is_monitored,
        },
    }

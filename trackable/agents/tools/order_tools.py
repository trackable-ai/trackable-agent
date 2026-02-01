"""Order query tools for the chatbot agent."""

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

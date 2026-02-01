"""Tests for chatbot order query tools."""

from datetime import datetime, timezone
from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest

from trackable.models.order import (
    Item,
    Merchant,
    Money,
    Order,
    OrderStatus,
    SourceType,
)


def _make_order(
    order_number: str = "ORD-001",
    merchant_name: str = "Nike",
    status: OrderStatus = OrderStatus.DELIVERED,
    total_amount: str = "99.99",
    items: list[Item] | None = None,
    return_window_end: datetime | None = None,
) -> Order:
    """Helper to create test Order objects."""
    merchant_id = str(uuid4())
    order_id = str(uuid4())
    user_id = str(uuid4())
    now = datetime.now(timezone.utc)

    if items is None:
        items = [
            Item(
                id=str(uuid4()),
                order_id=order_id,
                name="Test Item",
                quantity=1,
                price=Money(amount=total_amount),
            )
        ]

    return Order(
        id=order_id,
        user_id=user_id,
        merchant=Merchant(
            id=merchant_id, name=merchant_name, domain=f"{merchant_name.lower()}.com"
        ),
        order_number=order_number,
        status=status,
        items=items,
        total=Money(amount=total_amount),
        source_type=SourceType.EMAIL,
        return_window_end=return_window_end,
        created_at=now,
        updated_at=now,
    )


class TestGetUserOrders:
    """Tests for the get_user_orders tool function."""

    @patch("trackable.agents.tools.order_tools.UnitOfWork")
    def test_returns_orders_summary(self, mock_uow_cls: MagicMock):
        from trackable.agents.tools.order_tools import get_user_orders

        orders = [
            _make_order("ORD-001", "Nike", OrderStatus.DELIVERED, "99.99"),
            _make_order("ORD-002", "Amazon", OrderStatus.SHIPPED, "45.00"),
        ]
        mock_uow = MagicMock()
        mock_uow.__enter__ = MagicMock(return_value=mock_uow)
        mock_uow.__exit__ = MagicMock(return_value=False)
        mock_uow.orders.get_by_user.return_value = orders
        mock_uow.orders.count_by_user.return_value = 2
        mock_uow_cls.return_value = mock_uow

        result = get_user_orders(user_id="user-123")

        assert result["status"] == "success"
        assert result["total_count"] == 2
        assert len(result["orders"]) == 2
        assert result["orders"][0]["order_number"] == "ORD-001"
        assert result["orders"][0]["merchant"] == "Nike"
        assert result["orders"][0]["status"] == "delivered"

    @patch("trackable.agents.tools.order_tools.UnitOfWork")
    def test_filters_by_status(self, mock_uow_cls: MagicMock):
        from trackable.agents.tools.order_tools import get_user_orders

        mock_uow = MagicMock()
        mock_uow.__enter__ = MagicMock(return_value=mock_uow)
        mock_uow.__exit__ = MagicMock(return_value=False)
        mock_uow.orders.get_by_user.return_value = []
        mock_uow.orders.count_by_user.return_value = 0
        mock_uow_cls.return_value = mock_uow

        result = get_user_orders(user_id="user-123", status="shipped")

        mock_uow.orders.get_by_user.assert_called_once_with(
            "user-123", status=OrderStatus.SHIPPED, limit=20, offset=0
        )
        assert result["status"] == "success"

    @patch("trackable.agents.tools.order_tools.UnitOfWork")
    def test_returns_empty_when_no_orders(self, mock_uow_cls: MagicMock):
        from trackable.agents.tools.order_tools import get_user_orders

        mock_uow = MagicMock()
        mock_uow.__enter__ = MagicMock(return_value=mock_uow)
        mock_uow.__exit__ = MagicMock(return_value=False)
        mock_uow.orders.get_by_user.return_value = []
        mock_uow.orders.count_by_user.return_value = 0
        mock_uow_cls.return_value = mock_uow

        result = get_user_orders(user_id="user-123")

        assert result["status"] == "success"
        assert result["total_count"] == 0
        assert result["orders"] == []

    @patch("trackable.agents.tools.order_tools.UnitOfWork")
    def test_handles_invalid_status(self, mock_uow_cls: MagicMock):
        from trackable.agents.tools.order_tools import get_user_orders

        result = get_user_orders(user_id="user-123", status="nonexistent")

        assert result["status"] == "error"
        assert "Invalid status" in result["message"]

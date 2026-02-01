"""Scenario tests for chatbot tools - realistic user interaction patterns."""

from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch
from uuid import uuid4

from trackable.models.order import (
    Carrier,
    Item,
    Merchant,
    Money,
    Order,
    OrderStatus,
    Shipment,
    ShipmentStatus,
    SourceType,
)


def _make_full_order(
    order_number: str,
    merchant_name: str,
    status: OrderStatus,
    total: str,
    items: list[dict],
    return_window_end: datetime | None = None,
    order_date: datetime | None = None,
) -> Order:
    """Create a realistic test order."""
    merchant_id = str(uuid4())
    order_id = str(uuid4())
    user_id = str(uuid4())
    now = datetime.now(timezone.utc)

    order_items = []
    for item_data in items:
        order_items.append(
            Item(
                id=str(uuid4()),
                order_id=order_id,
                name=item_data["name"],
                quantity=item_data.get("quantity", 1),
                price=(
                    Money(amount=item_data["price"]) if "price" in item_data else None
                ),
                size=item_data.get("size"),
                color=item_data.get("color"),
            )
        )

    return Order(
        id=order_id,
        user_id=user_id,
        merchant=Merchant(
            id=merchant_id,
            name=merchant_name,
            domain=f"{merchant_name.lower().replace(' ', '')}.com",
        ),
        order_number=order_number,
        order_date=order_date or now - timedelta(days=7),
        status=status,
        items=order_items,
        total=Money(amount=total),
        source_type=SourceType.EMAIL,
        return_window_end=return_window_end,
        is_monitored=True,
        created_at=now,
        updated_at=now,
    )


class TestOrderOverviewScenario:
    """Scenario: User asks 'Show me all my orders'."""

    @patch("trackable.agents.tools.order_tools.UnitOfWork")
    def test_multiple_orders_from_different_merchants(self, mock_uow_cls: MagicMock):
        from trackable.agents.tools.order_tools import get_user_orders

        orders = [
            _make_full_order(
                "NKE-001",
                "Nike",
                OrderStatus.DELIVERED,
                "129.99",
                [{"name": "Air Max 90", "price": "129.99", "size": "10"}],
            ),
            _make_full_order(
                "AMZ-002",
                "Amazon",
                OrderStatus.SHIPPED,
                "45.99",
                [
                    {"name": "USB-C Cable", "price": "12.99"},
                    {"name": "Phone Case", "price": "33.00"},
                ],
            ),
            _make_full_order(
                "TGT-003",
                "Target",
                OrderStatus.CONFIRMED,
                "78.50",
                [{"name": "Bedsheet Set", "price": "78.50"}],
            ),
        ]

        mock_uow = MagicMock()
        mock_uow.__enter__ = MagicMock(return_value=mock_uow)
        mock_uow.__exit__ = MagicMock(return_value=False)
        mock_uow.orders.get_by_user.return_value = orders
        mock_uow.orders.count_by_user.return_value = 3
        mock_uow_cls.return_value = mock_uow

        result = get_user_orders(user_id="user-123")

        assert result["total_count"] == 3
        assert result["orders"][0]["items"] == ["Air Max 90"]
        assert result["orders"][1]["item_count"] == 2
        assert result["orders"][2]["status"] == "confirmed"


class TestReturnDeadlineScenario:
    """Scenario: User asks 'Are any of my return windows closing soon?'."""

    @patch("trackable.agents.tools.order_tools.UnitOfWork")
    @patch("trackable.agents.tools.order_tools.datetime")
    def test_urgent_and_non_urgent_returns(
        self, mock_datetime: MagicMock, mock_uow_cls: MagicMock
    ):
        from trackable.agents.tools.order_tools import check_return_windows

        # Use a fixed timestamp so the tool's datetime.now() matches our test data
        now = datetime(2026, 2, 1, 12, 0, 0, tzinfo=timezone.utc)
        mock_datetime.now.return_value = now
        mock_datetime.side_effect = lambda *a, **kw: datetime(*a, **kw)

        orders = [
            _make_full_order(
                "NKE-001",
                "Nike",
                OrderStatus.DELIVERED,
                "129.99",
                [{"name": "Air Max 90"}],
                return_window_end=now + timedelta(days=2),
            ),
            _make_full_order(
                "AMZ-002",
                "Amazon",
                OrderStatus.DELIVERED,
                "45.99",
                [{"name": "USB-C Cable"}],
                return_window_end=now + timedelta(days=12),
            ),
        ]

        mock_uow = MagicMock()
        mock_uow.__enter__ = MagicMock(return_value=mock_uow)
        mock_uow.__exit__ = MagicMock(return_value=False)
        mock_uow.orders.get_orders_with_expiring_return_window.return_value = orders
        mock_uow_cls.return_value = mock_uow

        result = check_return_windows(user_id="user-123", days_ahead=14)

        assert len(result["expiring_orders"]) == 2
        assert result["expiring_orders"][0]["days_remaining"] == 2
        assert result["expiring_orders"][1]["days_remaining"] == 12


class TestOrderDetailWithShipmentsScenario:
    """Scenario: User asks 'Where is my Nike order?'."""

    @patch("trackable.agents.tools.order_tools.UnitOfWork")
    def test_shipped_order_with_tracking(self, mock_uow_cls: MagicMock):
        from trackable.agents.tools.order_tools import get_order_details

        order = _make_full_order(
            "NKE-001",
            "Nike",
            OrderStatus.SHIPPED,
            "129.99",
            [{"name": "Air Max 90", "price": "129.99", "size": "10", "color": "Black"}],
        )
        shipment = Shipment(
            id=str(uuid4()),
            order_id=order.id,
            tracking_number="1Z999AA10123456784",
            carrier=Carrier.UPS,
            status=ShipmentStatus.IN_TRANSIT,
            shipped_at=datetime.now(timezone.utc) - timedelta(days=2),
            estimated_delivery=datetime.now(timezone.utc) + timedelta(days=3),
        )

        mock_uow = MagicMock()
        mock_uow.__enter__ = MagicMock(return_value=mock_uow)
        mock_uow.__exit__ = MagicMock(return_value=False)
        mock_uow.orders.get_by_id_for_user.return_value = order
        mock_uow.shipments.get_by_order.return_value = [shipment]
        mock_uow_cls.return_value = mock_uow

        result = get_order_details(user_id="user-123", order_id=order.id)

        assert result["status"] == "success"
        assert result["order"]["status"] == "shipped"
        assert len(result["order"]["shipments"]) == 1
        ship = result["order"]["shipments"][0]
        assert ship["carrier"] == "ups"
        assert ship["tracking_number"] == "1Z999AA10123456784"
        assert ship["estimated_delivery"] is not None


class TestFuzzySearchScenario:
    """Scenario: User asks 'Where is my MacBook order?'."""

    @patch("trackable.agents.tools.order_tools.UnitOfWork")
    def test_search_finds_order_by_item_name(self, mock_uow_cls: MagicMock):
        from trackable.agents.tools.order_tools import search_orders

        orders = [
            _make_full_order(
                "APL-001",
                "Apple Store",
                OrderStatus.SHIPPED,
                "1299.00",
                [
                    {"name": "MacBook Air M3 13-inch", "price": "1299.00"},
                ],
            ),
        ]

        mock_uow = MagicMock()
        mock_uow.__enter__ = MagicMock(return_value=mock_uow)
        mock_uow.__exit__ = MagicMock(return_value=False)
        mock_uow.orders.search.return_value = orders
        mock_uow_cls.return_value = mock_uow

        result = search_orders(user_id="user-123", query="MacBook")

        assert result["status"] == "success"
        assert result["count"] == 1
        assert result["orders"][0]["items"] == ["MacBook Air M3 13-inch"]
        assert result["orders"][0]["merchant"] == "Apple Store"
        assert result["orders"][0]["status"] == "shipped"

    @patch("trackable.agents.tools.order_tools.UnitOfWork")
    def test_search_finds_orders_by_merchant(self, mock_uow_cls: MagicMock):
        from trackable.agents.tools.order_tools import search_orders

        orders = [
            _make_full_order(
                "AMZ-001",
                "Amazon",
                OrderStatus.DELIVERED,
                "45.99",
                [{"name": "USB-C Hub", "price": "45.99"}],
            ),
            _make_full_order(
                "AMZ-002",
                "Amazon",
                OrderStatus.SHIPPED,
                "29.99",
                [{"name": "Phone Case", "price": "29.99"}],
            ),
        ]

        mock_uow = MagicMock()
        mock_uow.__enter__ = MagicMock(return_value=mock_uow)
        mock_uow.__exit__ = MagicMock(return_value=False)
        mock_uow.orders.search.return_value = orders
        mock_uow_cls.return_value = mock_uow

        result = search_orders(user_id="user-123", query="Amazon")

        assert result["count"] == 2
        assert result["orders"][0]["merchant"] == "Amazon"
        assert result["orders"][1]["merchant"] == "Amazon"

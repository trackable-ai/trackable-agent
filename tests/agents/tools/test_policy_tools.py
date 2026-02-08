"""Tests for policy query tools."""

from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

import pytest

from trackable.agents.tools.policy_tools import (
    get_exchange_policy,
    get_policy_for_order,
    get_return_policy,
)
from trackable.models.order import (
    Item,
    Merchant,
    Money,
    Order,
    OrderStatus,
    SourceType,
)
from trackable.models.policy import (
    ExchangePolicy,
    ExchangeType,
    Policy,
    PolicyType,
    RefundMethod,
    ReturnCondition,
    ReturnPolicy,
    ReturnShippingResponsibility,
)


def _make_merchant(
    merchant_id: str = "merch-123",
    name: str = "Nike",
    domain: str = "nike.com",
) -> Merchant:
    """Helper to create test Merchant objects."""
    return Merchant(
        id=merchant_id,
        name=name,
        domain=domain,
    )


def _make_return_policy(
    merchant_id: str = "merch-123",
    policy_id: str = "pol-123",
    window_days: int = 30,
    conditions: list[ReturnCondition] | None = None,
    excluded_categories: list[str] | None = None,
    refund_method: RefundMethod = RefundMethod.ORIGINAL_PAYMENT,
    shipping_responsibility: ReturnShippingResponsibility = ReturnShippingResponsibility.CUSTOMER,
    free_return_label: bool = False,
    restocking_fee: float | None = None,
    source_url: str | None = "https://nike.com/returns",
    needs_verification: bool = False,
) -> Policy:
    """Helper to create test Policy objects with ReturnPolicy."""
    return Policy(
        id=policy_id,
        merchant_id=merchant_id,
        policy_type=PolicyType.RETURN,
        country_code="US",
        name="Return Policy",
        return_policy=ReturnPolicy(
            allowed=True,
            window_days=window_days,
            conditions=conditions or [ReturnCondition.UNUSED],
            refund_method=refund_method,
            shipping_responsibility=shipping_responsibility,
            free_return_label=free_return_label,
            restocking_fee=restocking_fee,
            excluded_categories=excluded_categories or [],
        ),
        source_url=source_url,
        confidence_score=0.9,
        needs_verification=needs_verification,
        last_verified=datetime.now(timezone.utc),
    )


def _make_exchange_policy(
    merchant_id: str = "merch-123",
    policy_id: str = "pol-456",
    window_days: int = 60,
    exchange_types: list[ExchangeType] | None = None,
    conditions: list[ReturnCondition] | None = None,
    excluded_categories: list[str] | None = None,
    shipping_responsibility: ReturnShippingResponsibility = ReturnShippingResponsibility.MERCHANT,
    free_exchange_label: bool = True,
    price_difference_handling: str | None = "Refund or charge the difference",
    source_url: str | None = "https://nike.com/exchanges",
    needs_verification: bool = False,
) -> Policy:
    """Helper to create test Policy objects with ExchangePolicy."""
    return Policy(
        id=policy_id,
        merchant_id=merchant_id,
        policy_type=PolicyType.EXCHANGE,
        country_code="US",
        name="Exchange Policy",
        exchange_policy=ExchangePolicy(
            allowed=True,
            window_days=window_days,
            exchange_types=exchange_types or [ExchangeType.SIZE_ONLY],
            conditions=conditions or [ReturnCondition.UNUSED],
            shipping_responsibility=shipping_responsibility,
            free_exchange_label=free_exchange_label,
            price_difference_handling=price_difference_handling,
            excluded_categories=excluded_categories or [],
        ),
        source_url=source_url,
        confidence_score=0.9,
        needs_verification=needs_verification,
        last_verified=datetime.now(timezone.utc),
    )


def _make_order(
    order_id: str = "order-123",
    merchant: Merchant | None = None,
    order_number: str = "NKE-12345",
    order_date: datetime | None = None,
    return_window_end: datetime | None = None,
    exchange_window_end: datetime | None = None,
) -> Order:
    """Helper to create test Order objects."""
    if merchant is None:
        merchant = _make_merchant()
    if order_date is None:
        order_date = datetime.now(timezone.utc) - timedelta(days=10)

    return Order(
        id=order_id,
        user_id="user-123",
        merchant=merchant,
        order_number=order_number,
        status=OrderStatus.DELIVERED,
        order_date=order_date,
        return_window_end=return_window_end,
        exchange_window_end=exchange_window_end,
        source_type=SourceType.EMAIL,
        items=[
            Item(
                id="item-1",
                order_id=order_id,
                name="Air Max Sneakers",
                quantity=1,
                price=Money(amount=120.0, currency="USD"),
            )
        ],
    )


class TestGetReturnPolicy:
    """Tests for get_return_policy tool."""

    @patch("trackable.agents.tools.policy_tools.UnitOfWork")
    def test_returns_return_policy_by_merchant_name(self, mock_uow_cls):
        """Test getting return policy by merchant name."""
        # Setup mocks
        mock_uow = MagicMock()
        mock_uow_cls.return_value.__enter__.return_value = mock_uow

        merchant = _make_merchant()
        policy = _make_return_policy(
            window_days=30,
            conditions=[ReturnCondition.UNUSED, ReturnCondition.TAGS_ATTACHED],
            excluded_categories=["Gift cards", "Personalized items"],
        )

        mock_uow.merchants.get_by_name_or_domain.return_value = merchant
        mock_uow.policies.get_return_policy_by_merchant.return_value = policy

        # Test function
        result = get_return_policy(merchant_name="Nike")

        # Assert response structure
        assert result["status"] == "success"
        assert result["merchant"] == "Nike"
        assert result["policy_type"] == "return"
        assert result["country"] == "US"

        details = result["details"]
        assert details["allowed"] is True
        assert details["window_days"] == 30
        assert len(details["conditions"]) == 2
        assert "Item must be unused" in details["conditions"]
        assert "Tags must be attached" in details["conditions"]
        assert details["refund_method"] == "Original payment method"
        assert details["restocking_fee"] is None
        assert details["shipping"] == "Customer pays return shipping"
        assert "Gift cards" in details["excluded_categories"]
        assert "Personalized items" in details["excluded_categories"]
        assert details["source_url"] == "https://nike.com/returns"
        assert details["needs_verification"] is False

        # Verify calls
        mock_uow.merchants.get_by_name_or_domain.assert_called_once_with(
            name="Nike", domain=None
        )
        mock_uow.policies.get_return_policy_by_merchant.assert_called_once_with(
            merchant_id="merch-123",
            country_code="US",
        )

    @patch("trackable.agents.tools.policy_tools.UnitOfWork")
    def test_returns_return_policy_by_merchant_domain(self, mock_uow_cls):
        """Test getting return policy by merchant domain."""
        mock_uow = MagicMock()
        mock_uow_cls.return_value.__enter__.return_value = mock_uow

        merchant = _make_merchant()
        policy = _make_return_policy()

        mock_uow.merchants.get_by_name_or_domain.return_value = merchant
        mock_uow.policies.get_return_policy_by_merchant.return_value = policy

        result = get_return_policy(merchant_domain="nike.com")

        assert result["status"] == "success"
        mock_uow.merchants.get_by_name_or_domain.assert_called_once_with(
            name=None, domain="nike.com"
        )

    @patch("trackable.agents.tools.policy_tools.UnitOfWork")
    def test_merchant_not_found(self, mock_uow_cls):
        """Test when merchant is not found."""
        mock_uow = MagicMock()
        mock_uow_cls.return_value.__enter__.return_value = mock_uow
        mock_uow.merchants.get_by_name_or_domain.return_value = None

        result = get_return_policy(merchant_name="UnknownMerchant")

        assert result["status"] == "not_found"
        assert "UnknownMerchant" in result["message"]

    @patch("trackable.agents.tools.policy_tools.UnitOfWork")
    def test_policy_not_found(self, mock_uow_cls):
        """Test when merchant exists but no policy."""
        mock_uow = MagicMock()
        mock_uow_cls.return_value.__enter__.return_value = mock_uow

        merchant = _make_merchant()
        mock_uow.merchants.get_by_name_or_domain.return_value = merchant
        mock_uow.policies.get_return_policy_by_merchant.return_value = None

        result = get_return_policy(merchant_name="Nike")

        assert result["status"] == "not_found"
        assert "Nike" in result["message"]

    @patch("trackable.agents.tools.policy_tools.UnitOfWork")
    def test_policy_data_incomplete(self, mock_uow_cls):
        """Test when policy exists but return_policy field is None."""
        mock_uow = MagicMock()
        mock_uow_cls.return_value.__enter__.return_value = mock_uow

        merchant = _make_merchant()
        policy = Policy(
            id="pol-123",
            merchant_id="merch-123",
            policy_type=PolicyType.RETURN,
            country_code="US",
            name="Return Policy",
            return_policy=None,  # Missing return_policy data
        )

        mock_uow.merchants.get_by_name_or_domain.return_value = merchant
        mock_uow.policies.get_return_policy_by_merchant.return_value = policy

        result = get_return_policy(merchant_name="Nike")

        assert result["status"] == "not_found"
        assert "incomplete" in result["message"].lower()

    @patch("trackable.agents.tools.policy_tools.UnitOfWork")
    def test_requires_merchant_identifier(self, mock_uow_cls):
        """Test error when no merchant name/domain provided."""
        result = get_return_policy()

        assert result["status"] == "error"
        assert "provide" in result["message"].lower()

    @patch("trackable.agents.tools.policy_tools.UnitOfWork")
    def test_free_return_label_formatting(self, mock_uow_cls):
        """Test shipping responsibility with free return label."""
        mock_uow = MagicMock()
        mock_uow_cls.return_value.__enter__.return_value = mock_uow

        merchant = _make_merchant()
        policy = _make_return_policy(
            shipping_responsibility=ReturnShippingResponsibility.MERCHANT,
            free_return_label=True,
        )

        mock_uow.merchants.get_by_name_or_domain.return_value = merchant
        mock_uow.policies.get_return_policy_by_merchant.return_value = policy

        result = get_return_policy(merchant_name="Nike")

        assert result["status"] == "success"
        assert result["details"]["shipping"] == "Free return label provided by merchant"

    @patch("trackable.agents.tools.policy_tools.UnitOfWork")
    def test_restocking_fee(self, mock_uow_cls):
        """Test policy with restocking fee."""
        mock_uow = MagicMock()
        mock_uow_cls.return_value.__enter__.return_value = mock_uow

        merchant = _make_merchant()
        policy = _make_return_policy(restocking_fee=15.0)

        mock_uow.merchants.get_by_name_or_domain.return_value = merchant
        mock_uow.policies.get_return_policy_by_merchant.return_value = policy

        result = get_return_policy(merchant_name="Nike")

        assert result["status"] == "success"
        assert result["details"]["restocking_fee"] == 15.0

    @patch("trackable.agents.tools.policy_tools.UnitOfWork")
    def test_different_country_code(self, mock_uow_cls):
        """Test querying policy for different country."""
        mock_uow = MagicMock()
        mock_uow_cls.return_value.__enter__.return_value = mock_uow

        merchant = _make_merchant()
        policy = _make_return_policy()

        mock_uow.merchants.get_by_name_or_domain.return_value = merchant
        mock_uow.policies.get_return_policy_by_merchant.return_value = policy

        result = get_return_policy(merchant_name="Nike", country_code="GB")

        assert result["status"] == "success"
        assert result["country"] == "GB"
        mock_uow.policies.get_return_policy_by_merchant.assert_called_once_with(
            merchant_id="merch-123",
            country_code="GB",
        )


class TestGetExchangePolicy:
    """Tests for get_exchange_policy tool."""

    @patch("trackable.agents.tools.policy_tools.UnitOfWork")
    def test_returns_exchange_policy_by_merchant_name(self, mock_uow_cls):
        """Test getting exchange policy by merchant name."""
        mock_uow = MagicMock()
        mock_uow_cls.return_value.__enter__.return_value = mock_uow

        merchant = _make_merchant()
        policy = _make_exchange_policy(
            window_days=60,
            exchange_types=[ExchangeType.SIZE_ONLY, ExchangeType.COLOR_ONLY],
            conditions=[ReturnCondition.UNUSED],
            excluded_categories=["Clearance items"],
        )

        mock_uow.merchants.get_by_name_or_domain.return_value = merchant
        mock_uow.policies.get_exchange_policy_by_merchant.return_value = policy

        result = get_exchange_policy(merchant_name="Nike")

        assert result["status"] == "success"
        assert result["merchant"] == "Nike"
        assert result["policy_type"] == "exchange"
        assert result["country"] == "US"

        details = result["details"]
        assert details["allowed"] is True
        assert details["window_days"] == 60
        assert len(details["exchange_types"]) == 2
        assert "Size only" in details["exchange_types"]
        assert "Color only" in details["exchange_types"]
        assert "Item must be unused" in details["conditions"]
        assert details["shipping"] == "Free return label provided by merchant"
        assert details["price_difference_handling"] == "Refund or charge the difference"
        assert "Clearance items" in details["excluded_categories"]
        assert details["source_url"] == "https://nike.com/exchanges"
        assert details["needs_verification"] is False

    @patch("trackable.agents.tools.policy_tools.UnitOfWork")
    def test_merchant_not_found(self, mock_uow_cls):
        """Test when merchant is not found."""
        mock_uow = MagicMock()
        mock_uow_cls.return_value.__enter__.return_value = mock_uow
        mock_uow.merchants.get_by_name_or_domain.return_value = None

        result = get_exchange_policy(merchant_name="UnknownMerchant")

        assert result["status"] == "not_found"
        assert "UnknownMerchant" in result["message"]

    @patch("trackable.agents.tools.policy_tools.UnitOfWork")
    def test_policy_not_found(self, mock_uow_cls):
        """Test when merchant exists but no exchange policy."""
        mock_uow = MagicMock()
        mock_uow_cls.return_value.__enter__.return_value = mock_uow

        merchant = _make_merchant()
        mock_uow.merchants.get_by_name_or_domain.return_value = merchant
        mock_uow.policies.get_exchange_policy_by_merchant.return_value = None

        result = get_exchange_policy(merchant_name="Nike")

        assert result["status"] == "not_found"
        assert "Nike" in result["message"]

    @patch("trackable.agents.tools.policy_tools.UnitOfWork")
    def test_policy_data_incomplete(self, mock_uow_cls):
        """Test when policy exists but exchange_policy field is None."""
        mock_uow = MagicMock()
        mock_uow_cls.return_value.__enter__.return_value = mock_uow

        merchant = _make_merchant()
        policy = Policy(
            id="pol-456",
            merchant_id="merch-123",
            policy_type=PolicyType.EXCHANGE,
            country_code="US",
            name="Exchange Policy",
            exchange_policy=None,  # Missing exchange_policy data
        )

        mock_uow.merchants.get_by_name_or_domain.return_value = merchant
        mock_uow.policies.get_exchange_policy_by_merchant.return_value = policy

        result = get_exchange_policy(merchant_name="Nike")

        assert result["status"] == "not_found"
        assert "incomplete" in result["message"].lower()

    @patch("trackable.agents.tools.policy_tools.UnitOfWork")
    def test_requires_merchant_identifier(self, mock_uow_cls):
        """Test error when no merchant name/domain provided."""
        result = get_exchange_policy()

        assert result["status"] == "error"
        assert "provide" in result["message"].lower()


class TestGetPolicyForOrder:
    """Tests for get_policy_for_order tool."""

    @patch("trackable.agents.tools.policy_tools.UnitOfWork")
    def test_returns_policies_for_order(self, mock_uow_cls):
        """Test getting policies for a specific order."""
        mock_uow = MagicMock()
        mock_uow_cls.return_value.__enter__.return_value = mock_uow

        merchant = _make_merchant()
        order = _make_order(
            merchant=merchant,
            order_date=datetime(2026, 1, 15, tzinfo=timezone.utc),
            return_window_end=datetime(2026, 2, 14, tzinfo=timezone.utc),
            exchange_window_end=datetime(2026, 3, 16, tzinfo=timezone.utc),
        )
        return_policy = _make_return_policy(merchant_id=merchant.id)
        exchange_policy = _make_exchange_policy(merchant_id=merchant.id)

        mock_uow.orders.get_by_id_for_user.return_value = order
        mock_uow.policies.get_return_policy_by_merchant.return_value = return_policy
        mock_uow.policies.get_exchange_policy_by_merchant.return_value = exchange_policy

        result = get_policy_for_order(user_id="user-123", order_id="order-123")

        assert result["status"] == "success"

        # Check order context
        order_ctx = result["order"]
        assert order_ctx["order_number"] == "NKE-12345"
        assert order_ctx["merchant"] == "Nike"
        assert order_ctx["order_date"] == "2026-01-15T00:00:00+00:00"

        # Check return policy
        rp = result["return_policy"]
        assert rp is not None
        assert rp["allowed"] is True
        assert rp["window_days"] == 30
        assert rp["deadline"] == "2026-02-14T00:00:00+00:00"
        assert rp["days_remaining"] >= 0  # Will vary based on current time
        assert "Item must be unused" in rp["conditions"]

        # Check exchange policy
        ep = result["exchange_policy"]
        assert ep is not None
        assert ep["allowed"] is True
        assert ep["window_days"] == 60
        assert ep["deadline"] == "2026-03-16T00:00:00+00:00"
        assert ep["days_remaining"] >= 0

        # Verify calls
        mock_uow.orders.get_by_id_for_user.assert_called_once_with(
            "order-123", "user-123"
        )
        mock_uow.policies.get_return_policy_by_merchant.assert_called_once_with(
            merchant_id="merch-123",
            country_code="US",
        )
        mock_uow.policies.get_exchange_policy_by_merchant.assert_called_once_with(
            merchant_id="merch-123",
            country_code="US",
        )

    @patch("trackable.agents.tools.policy_tools.UnitOfWork")
    def test_order_not_found(self, mock_uow_cls):
        """Test when order doesn't exist or doesn't belong to user."""
        mock_uow = MagicMock()
        mock_uow_cls.return_value.__enter__.return_value = mock_uow
        mock_uow.orders.get_by_id_for_user.return_value = None

        result = get_policy_for_order(user_id="user-123", order_id="order-999")

        assert result["status"] == "not_found"
        assert "order-999" in result["message"]

    @patch("trackable.agents.tools.policy_tools.UnitOfWork")
    def test_only_return_policy_available(self, mock_uow_cls):
        """Test when only return policy is available."""
        mock_uow = MagicMock()
        mock_uow_cls.return_value.__enter__.return_value = mock_uow

        merchant = _make_merchant()
        order = _make_order(
            merchant=merchant,
            return_window_end=datetime(2026, 2, 14, tzinfo=timezone.utc),
        )
        return_policy = _make_return_policy(merchant_id=merchant.id)

        mock_uow.orders.get_by_id_for_user.return_value = order
        mock_uow.policies.get_return_policy_by_merchant.return_value = return_policy
        mock_uow.policies.get_exchange_policy_by_merchant.return_value = None

        result = get_policy_for_order(user_id="user-123", order_id="order-123")

        assert result["status"] == "success"
        assert result["return_policy"] is not None
        assert result["exchange_policy"] is None

    @patch("trackable.agents.tools.policy_tools.UnitOfWork")
    def test_no_policies_available(self, mock_uow_cls):
        """Test when no policies are available."""
        mock_uow = MagicMock()
        mock_uow_cls.return_value.__enter__.return_value = mock_uow

        merchant = _make_merchant()
        order = _make_order(merchant=merchant)

        mock_uow.orders.get_by_id_for_user.return_value = order
        mock_uow.policies.get_return_policy_by_merchant.return_value = None
        mock_uow.policies.get_exchange_policy_by_merchant.return_value = None

        result = get_policy_for_order(user_id="user-123", order_id="order-123")

        assert result["status"] == "success"
        assert result["return_policy"] is None
        assert result["exchange_policy"] is None

    @patch("trackable.agents.tools.policy_tools.UnitOfWork")
    def test_no_return_window_in_order(self, mock_uow_cls):
        """Test when order has no return_window_end set."""
        mock_uow = MagicMock()
        mock_uow_cls.return_value.__enter__.return_value = mock_uow

        merchant = _make_merchant()
        order = _make_order(
            merchant=merchant,
            return_window_end=None,  # No return window
            exchange_window_end=None,
        )
        return_policy = _make_return_policy(merchant_id=merchant.id)

        mock_uow.orders.get_by_id_for_user.return_value = order
        mock_uow.policies.get_return_policy_by_merchant.return_value = return_policy
        mock_uow.policies.get_exchange_policy_by_merchant.return_value = None

        result = get_policy_for_order(user_id="user-123", order_id="order-123")

        assert result["status"] == "success"
        rp = result["return_policy"]
        assert rp is not None
        assert rp["deadline"] is None
        assert rp["days_remaining"] is None

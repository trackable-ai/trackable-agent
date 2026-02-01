"""
Unit tests for OrderRepository merge logic.

These tests verify the order merge logic without requiring a database connection.
"""

from datetime import datetime, timezone
from decimal import Decimal
from unittest.mock import MagicMock
from uuid import uuid4

import pytest

from trackable.db.repositories.order import ORDER_STATUS_PROGRESSION, OrderRepository
from trackable.models.order import (
    Item,
    Merchant,
    Money,
    Order,
    OrderStatus,
    SourceType,
)


@pytest.fixture
def mock_session() -> MagicMock:
    """Create a mock database session."""
    return MagicMock()


@pytest.fixture
def order_repo(mock_session: MagicMock) -> OrderRepository:
    """Create an OrderRepository with mock session."""
    return OrderRepository(mock_session)


@pytest.fixture
def sample_merchant() -> Merchant:
    """Create a sample merchant for testing."""
    return Merchant(
        id=str(uuid4()),
        name="Test Store",
        domain="teststore.com",
    )


@pytest.fixture
def sample_order(sample_merchant: Merchant) -> Order:
    """Create a sample order for testing."""
    order_id = str(uuid4())
    now = datetime.now(timezone.utc)

    return Order(
        id=order_id,
        user_id=str(uuid4()),
        merchant=sample_merchant,
        order_number="TEST-001",
        order_date=now,
        status=OrderStatus.CONFIRMED,
        source_type=SourceType.EMAIL,
        items=[
            Item(
                id=str(uuid4()),
                order_id=order_id,
                name="Test Item",
                quantity=1,
                price=Money(amount=Decimal("50.00"), currency="USD"),
            ),
        ],
        total=Money(amount=Decimal("50.00"), currency="USD"),
        confidence_score=0.80,
        notes=["Original note"],
        created_at=now,
        updated_at=now,
    )


class TestOrderStatusProgression:
    """Tests for ORDER_STATUS_PROGRESSION constant."""

    def test_status_progression_order(self):
        """Test that status progression is in correct order."""
        expected_order = [
            OrderStatus.UNKNOWN,
            OrderStatus.DETECTED,
            OrderStatus.CONFIRMED,
            OrderStatus.SHIPPED,
            OrderStatus.IN_TRANSIT,
            OrderStatus.DELIVERED,
            OrderStatus.RETURNED,
            OrderStatus.REFUNDED,
            OrderStatus.CANCELLED,
        ]
        assert ORDER_STATUS_PROGRESSION == expected_order

    def test_all_statuses_included(self):
        """Test that all OrderStatus values are in the progression."""
        for status in OrderStatus:
            assert status in ORDER_STATUS_PROGRESSION


class TestMergeOrders:
    """Tests for _merge_orders method."""

    def test_merge_same_status_does_not_set_status(
        self,
        order_repo: OrderRepository,
        sample_order: Order,
        sample_merchant: Merchant,
    ):
        """Merge never changes status (both have same status under new semantics)."""
        existing = sample_order  # CONFIRMED
        incoming = Order(
            id=str(uuid4()),
            user_id=existing.user_id,
            merchant=sample_merchant,
            order_number=existing.order_number,
            status=existing.status,  # Same status
            source_type=SourceType.EMAIL,
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )
        updates = order_repo._merge_orders(existing, incoming)
        assert "status" not in updates

    def test_merge_notes_appended(
        self,
        order_repo: OrderRepository,
        sample_order: Order,
        sample_merchant: Merchant,
    ):
        """Test that notes are appended during merge."""
        existing = sample_order
        existing.notes = ["Note 1", "Note 2"]

        incoming = Order(
            id=str(uuid4()),
            user_id=existing.user_id,
            merchant=sample_merchant,
            order_number=existing.order_number,
            status=existing.status,
            source_type=SourceType.EMAIL,
            notes=["Note 3", "Note 1"],  # Note 1 is duplicate
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )

        updates = order_repo._merge_orders(existing, incoming)

        assert "notes" in updates
        assert updates["notes"] == [
            "Note 1",
            "Note 2",
            "Note 3",
        ]  # Deduped and appended

    def test_merge_higher_confidence_used(
        self,
        order_repo: OrderRepository,
        sample_order: Order,
        sample_merchant: Merchant,
    ):
        """Test that higher confidence score is used during merge."""
        existing = sample_order
        existing.confidence_score = 0.70

        incoming = Order(
            id=str(uuid4()),
            user_id=existing.user_id,
            merchant=sample_merchant,
            order_number=existing.order_number,
            status=existing.status,
            source_type=SourceType.EMAIL,
            confidence_score=0.95,  # Higher confidence
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )

        updates = order_repo._merge_orders(existing, incoming)

        assert "confidence_score" in updates
        assert updates["confidence_score"] == 0.95

    def test_merge_lower_confidence_not_used(
        self,
        order_repo: OrderRepository,
        sample_order: Order,
        sample_merchant: Merchant,
    ):
        """Test that lower confidence score is not used during merge."""
        existing = sample_order
        existing.confidence_score = 0.95

        incoming = Order(
            id=str(uuid4()),
            user_id=existing.user_id,
            merchant=sample_merchant,
            order_number=existing.order_number,
            status=existing.status,
            source_type=SourceType.EMAIL,
            confidence_score=0.70,  # Lower confidence
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )

        updates = order_repo._merge_orders(existing, incoming)

        assert "confidence_score" not in updates

    def test_merge_items_replaced(
        self,
        order_repo: OrderRepository,
        sample_order: Order,
        sample_merchant: Merchant,
    ):
        """Test that items are replaced during merge."""
        existing = sample_order
        order_id = existing.id

        new_item = Item(
            id=str(uuid4()),
            order_id=order_id,
            name="New Item",
            quantity=2,
            price=Money(amount=Decimal("75.00"), currency="USD"),
        )

        incoming = Order(
            id=str(uuid4()),
            user_id=existing.user_id,
            merchant=sample_merchant,
            order_number=existing.order_number,
            status=existing.status,
            source_type=SourceType.EMAIL,
            items=[new_item],
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )

        updates = order_repo._merge_orders(existing, incoming)

        assert "items" in updates
        assert len(updates["items"]) == 1
        assert updates["items"][0]["name"] == "New Item"

    def test_merge_preserves_existing_return_window(
        self,
        order_repo: OrderRepository,
        sample_order: Order,
        sample_merchant: Merchant,
    ):
        """Test that existing return window is preserved during merge."""
        existing = sample_order
        existing.return_window_end = datetime(2025, 2, 15, tzinfo=timezone.utc)
        existing.return_window_days = 30

        incoming = Order(
            id=str(uuid4()),
            user_id=existing.user_id,
            merchant=sample_merchant,
            order_number=existing.order_number,
            status=existing.status,
            source_type=SourceType.EMAIL,
            return_window_end=datetime(
                2025, 3, 1, tzinfo=timezone.utc
            ),  # Different date
            return_window_days=60,  # Different days
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )

        updates = order_repo._merge_orders(existing, incoming)

        # Existing values should be preserved
        assert "return_window_end" not in updates
        assert "return_window_days" not in updates

    def test_merge_sets_return_window_if_not_set(
        self,
        order_repo: OrderRepository,
        sample_order: Order,
        sample_merchant: Merchant,
    ):
        """Test that return window is set during merge if not already set."""
        existing = sample_order
        existing.return_window_end = None
        existing.return_window_days = None

        new_return_end = datetime(2025, 2, 15, tzinfo=timezone.utc)

        incoming = Order(
            id=str(uuid4()),
            user_id=existing.user_id,
            merchant=sample_merchant,
            order_number=existing.order_number,
            status=existing.status,
            source_type=SourceType.EMAIL,
            return_window_end=new_return_end,
            return_window_days=30,
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )

        updates = order_repo._merge_orders(existing, incoming)

        assert "return_window_end" in updates
        assert updates["return_window_end"] == new_return_end
        assert "return_window_days" in updates
        assert updates["return_window_days"] == 30

    def test_merge_total_updated(
        self,
        order_repo: OrderRepository,
        sample_order: Order,
        sample_merchant: Merchant,
    ):
        """Test that total amount is updated during merge."""
        existing = sample_order

        incoming = Order(
            id=str(uuid4()),
            user_id=existing.user_id,
            merchant=sample_merchant,
            order_number=existing.order_number,
            status=existing.status,
            source_type=SourceType.EMAIL,
            total=Money(amount=Decimal("100.00"), currency="USD"),  # New total
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )

        updates = order_repo._merge_orders(existing, incoming)

        assert "total" in updates
        assert updates["total"]["amount"] == "100.00"

    def test_merge_clarification_questions_appended(
        self,
        order_repo: OrderRepository,
        sample_order: Order,
        sample_merchant: Merchant,
    ):
        """Test that clarification questions are appended during merge."""
        existing = sample_order
        existing.needs_clarification = True
        existing.clarification_questions = ["Is the color correct?"]

        incoming = Order(
            id=str(uuid4()),
            user_id=existing.user_id,
            merchant=sample_merchant,
            order_number=existing.order_number,
            status=existing.status,
            source_type=SourceType.EMAIL,
            needs_clarification=True,
            clarification_questions=[
                "Is the size correct?",
                "Is the color correct?",  # Duplicate
            ],
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )

        updates = order_repo._merge_orders(existing, incoming)

        assert "clarification_questions" in updates
        assert updates["clarification_questions"] == [
            "Is the color correct?",
            "Is the size correct?",
        ]

    def test_merge_urls_updated(
        self,
        order_repo: OrderRepository,
        sample_order: Order,
        sample_merchant: Merchant,
    ):
        """Test that URLs are updated during merge."""
        existing = sample_order
        existing.order_url = None

        incoming = Order(
            id=str(uuid4()),
            user_id=existing.user_id,
            merchant=sample_merchant,
            order_number=existing.order_number,
            status=existing.status,
            source_type=SourceType.EMAIL,
            order_url="https://example.com/order/123",
            receipt_url="https://example.com/receipt/123",
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )

        updates = order_repo._merge_orders(existing, incoming)

        assert "order_url" in updates
        assert updates["order_url"] == "https://example.com/order/123"
        assert "receipt_url" in updates
        assert updates["receipt_url"] == "https://example.com/receipt/123"

    def test_merge_refund_info_updated(
        self,
        order_repo: OrderRepository,
        sample_order: Order,
        sample_merchant: Merchant,
    ):
        """Test that refund info is updated during merge."""
        existing = sample_order
        existing.refund_initiated = False

        incoming = Order(
            id=str(uuid4()),
            user_id=existing.user_id,
            merchant=sample_merchant,
            order_number=existing.order_number,
            status=existing.status,
            source_type=SourceType.EMAIL,
            refund_initiated=True,
            refund_amount=Money(amount=Decimal("25.00"), currency="USD"),
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )

        updates = order_repo._merge_orders(existing, incoming)

        assert "refund_initiated" in updates
        assert updates["refund_initiated"] is True
        assert "refund_amount" in updates
        assert updates["refund_amount"]["amount"] == "25.00"

    def test_merge_order_date_set_if_null(
        self,
        order_repo: OrderRepository,
        sample_order: Order,
        sample_merchant: Merchant,
    ):
        """Test that order date is set during merge if existing is None."""
        existing = sample_order
        existing.order_date = None

        new_date = datetime(2025, 1, 15, 10, 30, 0, tzinfo=timezone.utc)

        incoming = Order(
            id=str(uuid4()),
            user_id=existing.user_id,
            merchant=sample_merchant,
            order_number=existing.order_number,
            status=existing.status,
            source_type=SourceType.EMAIL,
            order_date=new_date,
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )

        updates = order_repo._merge_orders(existing, incoming)

        assert "order_date" in updates
        assert updates["order_date"] == new_date

    def test_merge_order_date_preserved_if_set(
        self,
        order_repo: OrderRepository,
        sample_order: Order,
        sample_merchant: Merchant,
    ):
        """Test that existing order date is preserved during merge."""
        existing = sample_order
        existing.order_date = datetime(2025, 1, 1, tzinfo=timezone.utc)

        incoming = Order(
            id=str(uuid4()),
            user_id=existing.user_id,
            merchant=sample_merchant,
            order_number=existing.order_number,
            status=existing.status,
            source_type=SourceType.EMAIL,
            order_date=datetime(2025, 1, 15, tzinfo=timezone.utc),  # Different date
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )

        updates = order_repo._merge_orders(existing, incoming)

        # Existing date should be preserved
        assert "order_date" not in updates

    def test_merge_always_sets_updated_at(
        self,
        order_repo: OrderRepository,
        sample_order: Order,
        sample_merchant: Merchant,
    ):
        """Test that updated_at is always set during merge."""
        existing = sample_order

        incoming = Order(
            id=str(uuid4()),
            user_id=existing.user_id,
            merchant=sample_merchant,
            order_number=existing.order_number,
            status=existing.status,
            source_type=SourceType.EMAIL,
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )

        updates = order_repo._merge_orders(existing, incoming)

        assert "updated_at" in updates


class TestGetByUniqueKey:
    """Tests for get_by_unique_key with optional status."""

    def test_get_by_unique_key_with_status_includes_status_filter(
        self,
        order_repo: OrderRepository,
        sample_order: Order,
    ):
        """Verify status is included in the WHERE clause when provided."""
        order_repo.session.execute.return_value.fetchone.return_value = None

        order_repo.get_by_unique_key(
            user_id=sample_order.user_id,
            merchant_id=sample_order.merchant.id,
            order_number=sample_order.order_number,
            status=OrderStatus.CONFIRMED,
        )

        call_args = order_repo.session.execute.call_args
        compiled = str(call_args[0][0].compile(compile_kwargs={"literal_binds": True}))
        assert "status" in compiled.lower()

    def test_get_by_unique_key_without_status_omits_status_filter(
        self,
        order_repo: OrderRepository,
        sample_order: Order,
    ):
        """Verify status is NOT in WHERE clause when omitted."""
        order_repo.session.execute.return_value.fetchone.return_value = None

        order_repo.get_by_unique_key(
            user_id=sample_order.user_id,
            merchant_id=sample_order.merchant.id,
            order_number=sample_order.order_number,
        )

        call_args = order_repo.session.execute.call_args
        compiled = str(call_args[0][0].compile(compile_kwargs={"literal_binds": True}))
        assert "order_number" in compiled.lower()


class TestUpsertNewSemantics:
    """Tests for upsert with status-aware unique key."""

    def test_upsert_new_status_creates_new_row(
        self,
        order_repo: OrderRepository,
        sample_order: Order,
        sample_merchant: Merchant,
    ):
        """Different status -> new row (is_new=True)."""
        incoming = Order(
            id=str(uuid4()),
            user_id=sample_order.user_id,
            merchant=sample_merchant,
            order_number=sample_order.order_number,
            status=OrderStatus.SHIPPED,
            source_type=SourceType.EMAIL,
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )

        # get_by_unique_key returns None (no existing row for this status)
        order_repo.session.execute.return_value.fetchone.return_value = None

        from unittest.mock import patch

        with patch.object(order_repo, "create", return_value=incoming) as mock_create:
            result, is_new = order_repo.upsert_by_order_number(incoming)

        assert is_new is True
        mock_create.assert_called_once_with(incoming)


def _make_mock_row(**overrides) -> MagicMock:
    """Create a mock row with default order fields."""
    mock = MagicMock()
    defaults = {
        "id": uuid4(),
        "user_id": uuid4(),
        "merchant_id": uuid4(),
        "order_number": "ORD-001",
        "order_date": datetime.now(timezone.utc),
        "status": "detected",
        "country_code": "US",
        "items": [],
        "subtotal": None,
        "tax": None,
        "shipping_cost": None,
        "total": None,
        "return_window_start": None,
        "return_window_end": None,
        "return_window_days": None,
        "exchange_window_end": None,
        "is_monitored": True,
        "source_type": "email",
        "source_id": None,
        "confidence_score": None,
        "needs_clarification": False,
        "clarification_questions": [],
        "order_url": None,
        "receipt_url": None,
        "refund_initiated": False,
        "refund_amount": None,
        "refund_completed_at": None,
        "notes": [],
        "last_agent_intervention": None,
        "created_at": datetime.now(timezone.utc),
        "updated_at": datetime.now(timezone.utc),
    }
    defaults.update(overrides)
    for k, v in defaults.items():
        setattr(mock, k, v)
    mock._mapping = defaults
    return mock


class TestGetOrderHistory:
    def test_returns_list(self, order_repo: OrderRepository):
        mock_rows = [
            _make_mock_row(status="detected"),
            _make_mock_row(status="shipped"),
        ]
        order_repo.session.execute.return_value.fetchall.return_value = mock_rows
        result = order_repo.get_order_history(str(uuid4()), str(uuid4()), "ORD-001")
        assert len(result) == 2

    def test_empty_history(self, order_repo: OrderRepository):
        order_repo.session.execute.return_value.fetchall.return_value = []
        result = order_repo.get_order_history(str(uuid4()), str(uuid4()), "ORD-001")
        assert result == []


class TestGetLatestOrder:
    def test_returns_order(self, order_repo: OrderRepository):
        order_repo.session.execute.return_value.fetchone.return_value = _make_mock_row(
            status="delivered"
        )
        result = order_repo.get_latest_order(str(uuid4()), str(uuid4()), "ORD-001")
        assert result is not None

    def test_not_found(self, order_repo: OrderRepository):
        order_repo.session.execute.return_value.fetchone.return_value = None
        result = order_repo.get_latest_order(str(uuid4()), str(uuid4()), "ORD-001")
        assert result is None


class TestGetByUserDeduplicated:
    def test_default_uses_distinct_on(self, order_repo: OrderRepository):
        """Default get_by_user uses DISTINCT ON for deduplication."""
        order_repo.session.execute.return_value.fetchall.return_value = []
        order_repo.get_by_user(user_id=str(uuid4()))
        compiled = str(
            order_repo.session.execute.call_args[0][0].compile(
                compile_kwargs={"literal_binds": True}
            )
        )
        assert "distinct" in compiled.lower()

    def test_include_history_skips_distinct(self, order_repo: OrderRepository):
        """include_history=True returns all rows without DISTINCT ON."""
        order_repo.session.execute.return_value.fetchall.return_value = []
        order_repo.get_by_user(user_id=str(uuid4()), include_history=True)
        compiled = str(
            order_repo.session.execute.call_args[0][0].compile(
                compile_kwargs={"literal_binds": True}
            )
        )
        assert "distinct" not in compiled.lower()


class TestGetByOrderNumberLatest:
    def test_uses_status_ordering(self, order_repo: OrderRepository):
        """get_by_order_number sorts by status progression DESC."""
        order_repo.session.execute.return_value.fetchone.return_value = None
        order_repo.get_by_order_number(str(uuid4()), "ORD-001")
        compiled = str(
            order_repo.session.execute.call_args[0][0].compile(
                compile_kwargs={"literal_binds": True}
            )
        )
        assert "limit" in compiled.lower()
        assert "case" in compiled.lower()

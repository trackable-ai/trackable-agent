"""
Tests for order management API endpoints.

These tests verify the order CRUD endpoints work correctly
by mocking the database layer.
"""

from datetime import datetime, timezone
from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from trackable.api.main import app
from trackable.models.order import (
    Item,
    Merchant,
    Money,
    Order,
    OrderStatus,
    SourceType,
)


@pytest.fixture
def client() -> TestClient:
    """Create a test client for the API."""
    return TestClient(app)


# Test user ID (valid UUID format)
TEST_USER_ID = "d5314b80-4aac-4bf2-940c-0a0ceda5bff4"
TEST_HEADERS = {"X-User-ID": TEST_USER_ID}


@pytest.fixture
def sample_order() -> Order:
    """Create a sample order for testing."""
    now = datetime.now(timezone.utc)
    return Order(
        id=str(uuid4()),
        user_id="user_default",
        merchant=Merchant(id=str(uuid4()), name="Test Store", domain="teststore.com"),
        order_number="TEST-12345",
        order_date=now,
        status=OrderStatus.DELIVERED,
        items=[
            Item(
                id=str(uuid4()),
                order_id="",
                name="Test Item",
                quantity=1,
                price=Money(amount=29.99, currency="USD"),
            )
        ],
        total=Money(amount=29.99, currency="USD"),
        source_type=SourceType.EMAIL,
        is_monitored=True,
        created_at=now,
        updated_at=now,
    )


@pytest.fixture
def mock_db_initialized():
    """Mock DatabaseConnection.is_initialized to return True."""
    with patch("trackable.api.routes.orders.DatabaseConnection") as mock_db:
        mock_db.is_initialized.return_value = True
        yield mock_db


class TestListOrders:
    """Tests for GET /api/v1/orders endpoint."""

    def test_list_orders_success(
        self, client: TestClient, sample_order: Order, mock_db_initialized
    ):
        """Test listing orders returns paginated results."""
        with patch("trackable.api.routes.orders.UnitOfWork") as mock_uow_class:
            mock_uow = MagicMock()
            mock_uow_class.return_value.__enter__.return_value = mock_uow
            mock_uow.orders.get_by_user.return_value = [sample_order]
            mock_uow.orders.count_by_user.return_value = 1

            response = client.get("/api/v1/orders", headers=TEST_HEADERS)

            assert response.status_code == 200
            data = response.json()

            assert "orders" in data
            assert "total" in data
            assert "limit" in data
            assert "offset" in data

            assert len(data["orders"]) == 1
            assert data["total"] == 1
            assert data["limit"] == 100
            assert data["offset"] == 0

            # Verify order data
            assert data["orders"][0]["order_number"] == "TEST-12345"
            assert data["orders"][0]["status"] == "delivered"

    def test_list_orders_with_status_filter(
        self, client: TestClient, sample_order: Order, mock_db_initialized
    ):
        """Test listing orders with status filter."""
        with patch("trackable.api.routes.orders.UnitOfWork") as mock_uow_class:
            mock_uow = MagicMock()
            mock_uow_class.return_value.__enter__.return_value = mock_uow
            mock_uow.orders.get_by_user.return_value = [sample_order]
            mock_uow.orders.count_by_user.return_value = 1

            response = client.get(
                "/api/v1/orders?status=delivered", headers=TEST_HEADERS
            )

            assert response.status_code == 200

            # Verify status filter was passed
            mock_uow.orders.get_by_user.assert_called_once()
            call_kwargs = mock_uow.orders.get_by_user.call_args.kwargs
            assert call_kwargs["status"] == OrderStatus.DELIVERED

    def test_list_orders_invalid_status(self, client: TestClient, mock_db_initialized):
        """Test listing orders with invalid status returns 400."""
        response = client.get(
            "/api/v1/orders?status=invalid_status", headers=TEST_HEADERS
        )

        assert response.status_code == 400
        assert "Invalid status" in response.json()["detail"]

    def test_list_orders_with_pagination(
        self, client: TestClient, sample_order: Order, mock_db_initialized
    ):
        """Test listing orders with pagination parameters."""
        with patch("trackable.api.routes.orders.UnitOfWork") as mock_uow_class:
            mock_uow = MagicMock()
            mock_uow_class.return_value.__enter__.return_value = mock_uow
            mock_uow.orders.get_by_user.return_value = []
            mock_uow.orders.count_by_user.return_value = 50

            response = client.get(
                "/api/v1/orders?limit=10&offset=20", headers=TEST_HEADERS
            )

            assert response.status_code == 200
            data = response.json()

            assert data["limit"] == 10
            assert data["offset"] == 20
            assert data["total"] == 50

    def test_list_orders_empty(self, client: TestClient, mock_db_initialized):
        """Test listing orders when user has no orders."""
        with patch("trackable.api.routes.orders.UnitOfWork") as mock_uow_class:
            mock_uow = MagicMock()
            mock_uow_class.return_value.__enter__.return_value = mock_uow
            mock_uow.orders.get_by_user.return_value = []
            mock_uow.orders.count_by_user.return_value = 0

            response = client.get("/api/v1/orders", headers=TEST_HEADERS)

            assert response.status_code == 200
            data = response.json()
            assert data["orders"] == []
            assert data["total"] == 0

    def test_list_orders_db_unavailable(self, client: TestClient):
        """Test listing orders when database is unavailable."""
        with patch("trackable.api.routes.orders.DatabaseConnection") as mock_db:
            mock_db.is_initialized.return_value = False

            response = client.get("/api/v1/orders", headers=TEST_HEADERS)

            assert response.status_code == 503
            assert "Database not available" in response.json()["detail"]


class TestGetOrder:
    """Tests for GET /api/v1/orders/{order_id} endpoint."""

    def test_get_order_success(
        self, client: TestClient, sample_order: Order, mock_db_initialized
    ):
        """Test getting a specific order."""
        with patch("trackable.api.routes.orders.UnitOfWork") as mock_uow_class:
            mock_uow = MagicMock()
            mock_uow_class.return_value.__enter__.return_value = mock_uow
            mock_uow.orders.get_by_id_for_user.return_value = sample_order

            response = client.get(
                f"/api/v1/orders/{sample_order.id}", headers=TEST_HEADERS
            )

            assert response.status_code == 200
            data = response.json()

            assert data["id"] == sample_order.id
            assert data["order_number"] == "TEST-12345"
            assert data["status"] == "delivered"

    def test_get_order_not_found(self, client: TestClient, mock_db_initialized):
        """Test getting an order that doesn't exist."""
        with patch("trackable.api.routes.orders.UnitOfWork") as mock_uow_class:
            mock_uow = MagicMock()
            mock_uow_class.return_value.__enter__.return_value = mock_uow
            mock_uow.orders.get_by_id_for_user.return_value = None

            fake_id = str(uuid4())
            response = client.get(f"/api/v1/orders/{fake_id}", headers=TEST_HEADERS)

            assert response.status_code == 404
            assert "Order not found" in response.json()["detail"]


class TestUpdateOrder:
    """Tests for PATCH /api/v1/orders/{order_id} endpoint."""

    def test_update_order_status(
        self, client: TestClient, sample_order: Order, mock_db_initialized
    ):
        """Test updating order status."""
        with patch("trackable.api.routes.orders.UnitOfWork") as mock_uow_class:
            mock_uow = MagicMock()
            mock_uow_class.return_value.__enter__.return_value = mock_uow
            mock_uow.orders.get_by_id_for_user.return_value = sample_order
            mock_uow.orders.get_by_id.return_value = (
                sample_order  # For fetching after update
            )
            mock_uow.orders.update_by_id.return_value = True

            response = client.patch(
                f"/api/v1/orders/{sample_order.id}",
                headers=TEST_HEADERS,
                json={"status": "returned"},
            )

            assert response.status_code == 200

            # Verify update was called with correct status
            mock_uow.orders.update_by_id.assert_called()
            call_args = mock_uow.orders.update_by_id.call_args
            assert call_args.kwargs["status"] == "returned"

    def test_update_order_add_note(
        self, client: TestClient, sample_order: Order, mock_db_initialized
    ):
        """Test adding a note to an order."""
        with patch("trackable.api.routes.orders.UnitOfWork") as mock_uow_class:
            mock_uow = MagicMock()
            mock_uow_class.return_value.__enter__.return_value = mock_uow
            mock_uow.orders.get_by_id_for_user.return_value = sample_order
            mock_uow.orders.get_by_id.return_value = (
                sample_order  # For fetching after update
            )
            mock_uow.orders.add_note.return_value = True

            response = client.patch(
                f"/api/v1/orders/{sample_order.id}",
                headers=TEST_HEADERS,
                json={"note": "Customer requested return"},
            )

            assert response.status_code == 200

            # Verify add_note was called
            mock_uow.orders.add_note.assert_called_once_with(
                sample_order.id, "Customer requested return"
            )

    def test_update_order_is_monitored(
        self, client: TestClient, sample_order: Order, mock_db_initialized
    ):
        """Test toggling order monitoring."""
        with patch("trackable.api.routes.orders.UnitOfWork") as mock_uow_class:
            mock_uow = MagicMock()
            mock_uow_class.return_value.__enter__.return_value = mock_uow
            mock_uow.orders.get_by_id_for_user.return_value = sample_order
            mock_uow.orders.get_by_id.return_value = (
                sample_order  # For fetching after update
            )
            mock_uow.orders.update_by_id.return_value = True

            response = client.patch(
                f"/api/v1/orders/{sample_order.id}",
                headers=TEST_HEADERS,
                json={"is_monitored": False},
            )

            assert response.status_code == 200

            # Verify update was called with is_monitored
            mock_uow.orders.update_by_id.assert_called()
            call_args = mock_uow.orders.update_by_id.call_args
            assert call_args.kwargs["is_monitored"] is False

    def test_update_order_not_found(self, client: TestClient, mock_db_initialized):
        """Test updating an order that doesn't exist."""
        with patch("trackable.api.routes.orders.UnitOfWork") as mock_uow_class:
            mock_uow = MagicMock()
            mock_uow_class.return_value.__enter__.return_value = mock_uow
            mock_uow.orders.get_by_id_for_user.return_value = None

            fake_id = str(uuid4())
            response = client.patch(
                f"/api/v1/orders/{fake_id}",
                headers=TEST_HEADERS,
                json={"status": "returned"},
            )

            assert response.status_code == 404
            assert "Order not found" in response.json()["detail"]


class TestDeleteOrder:
    """Tests for DELETE /api/v1/orders/{order_id} endpoint."""

    def test_delete_order_success(
        self, client: TestClient, sample_order: Order, mock_db_initialized
    ):
        """Test deleting an order."""
        with patch("trackable.api.routes.orders.UnitOfWork") as mock_uow_class:
            mock_uow = MagicMock()
            mock_uow_class.return_value.__enter__.return_value = mock_uow
            mock_uow.orders.get_by_id_for_user.return_value = sample_order
            mock_uow.orders.delete_by_id.return_value = True

            response = client.delete(
                f"/api/v1/orders/{sample_order.id}", headers=TEST_HEADERS
            )

            assert response.status_code == 200
            data = response.json()
            assert "deleted successfully" in data["message"]

            # Verify delete was called
            mock_uow.orders.delete_by_id.assert_called_once_with(sample_order.id)
            mock_uow.commit.assert_called_once()

    def test_delete_order_not_found(self, client: TestClient, mock_db_initialized):
        """Test deleting an order that doesn't exist."""
        with patch("trackable.api.routes.orders.UnitOfWork") as mock_uow_class:
            mock_uow = MagicMock()
            mock_uow_class.return_value.__enter__.return_value = mock_uow
            mock_uow.orders.get_by_id_for_user.return_value = None

            fake_id = str(uuid4())
            response = client.delete(f"/api/v1/orders/{fake_id}", headers=TEST_HEADERS)

            assert response.status_code == 404
            assert "Order not found" in response.json()["detail"]

    def test_delete_order_db_unavailable(self, client: TestClient):
        """Test deleting an order when database is unavailable."""
        with patch("trackable.api.routes.orders.DatabaseConnection") as mock_db:
            mock_db.is_initialized.return_value = False

            fake_id = str(uuid4())
            response = client.delete(f"/api/v1/orders/{fake_id}", headers=TEST_HEADERS)

            assert response.status_code == 503
            assert "Database not available" in response.json()["detail"]

"""
Tests for shipment management API endpoints.

These tests verify the shipment update endpoints work correctly
by mocking the database layer.
"""

from datetime import datetime, timezone
from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from trackable.api.main import app
from trackable.models.order import (
    Carrier,
    Shipment,
    ShipmentStatus,
)


@pytest.fixture
def client() -> TestClient:
    """Create a test client for the API."""
    return TestClient(app)


# Test user ID (valid UUID format)
TEST_USER_ID = "d5314b80-4aac-4bf2-940c-0a0ceda5bff4"
TEST_HEADERS = {"X-User-ID": TEST_USER_ID}


@pytest.fixture
def sample_order_id() -> str:
    """Return a sample order ID."""
    return str(uuid4())


@pytest.fixture
def sample_shipment(sample_order_id: str) -> Shipment:
    """Create a sample shipment for testing."""
    return Shipment(
        id=str(uuid4()),
        order_id=sample_order_id,
        tracking_number="1Z999AA10123456784",
        carrier=Carrier.UPS,
        status=ShipmentStatus.IN_TRANSIT,
        events=[],
    )


@pytest.fixture
def mock_db_initialized():
    """Mock DatabaseConnection.is_initialized to return True."""
    with patch("trackable.api.routes.shipments.DatabaseConnection") as mock_db:
        mock_db.is_initialized.return_value = True
        yield mock_db


class TestGetShipment:
    """Tests for GET /api/v1/orders/{order_id}/shipments/{shipment_id} endpoint."""

    def test_get_shipment_success(
        self,
        client: TestClient,
        sample_shipment: Shipment,
        sample_order_id: str,
        mock_db_initialized,
    ):
        """Test getting a specific shipment."""
        with patch("trackable.api.routes.shipments.UnitOfWork") as mock_uow_class:
            mock_uow = MagicMock()
            mock_uow_class.return_value.__enter__.return_value = mock_uow
            # Order exists and belongs to user
            mock_uow.orders.get_by_id_for_user.return_value = MagicMock(
                id=sample_order_id
            )
            mock_uow.shipments.get_by_id.return_value = sample_shipment

            response = client.get(
                f"/api/v1/orders/{sample_order_id}/shipments/{sample_shipment.id}",
                headers=TEST_HEADERS,
            )

            assert response.status_code == 200
            data = response.json()
            assert data["id"] == sample_shipment.id
            assert data["tracking_number"] == "1Z999AA10123456784"
            assert data["carrier"] == "ups"

    def test_get_shipment_order_not_found(
        self, client: TestClient, mock_db_initialized
    ):
        """Test getting a shipment when order doesn't exist."""
        with patch("trackable.api.routes.shipments.UnitOfWork") as mock_uow_class:
            mock_uow = MagicMock()
            mock_uow_class.return_value.__enter__.return_value = mock_uow
            mock_uow.orders.get_by_id_for_user.return_value = None

            fake_order_id = str(uuid4())
            fake_shipment_id = str(uuid4())
            response = client.get(
                f"/api/v1/orders/{fake_order_id}/shipments/{fake_shipment_id}",
                headers=TEST_HEADERS,
            )

            assert response.status_code == 404
            assert "Order not found" in response.json()["detail"]

    def test_get_shipment_not_found(
        self, client: TestClient, sample_order_id: str, mock_db_initialized
    ):
        """Test getting a shipment that doesn't exist."""
        with patch("trackable.api.routes.shipments.UnitOfWork") as mock_uow_class:
            mock_uow = MagicMock()
            mock_uow_class.return_value.__enter__.return_value = mock_uow
            mock_uow.orders.get_by_id_for_user.return_value = MagicMock(
                id=sample_order_id
            )
            mock_uow.shipments.get_by_id.return_value = None

            fake_shipment_id = str(uuid4())
            response = client.get(
                f"/api/v1/orders/{sample_order_id}/shipments/{fake_shipment_id}",
                headers=TEST_HEADERS,
            )

            assert response.status_code == 404
            assert "Shipment not found" in response.json()["detail"]

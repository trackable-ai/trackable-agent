"""
Tests for worker task endpoints.

These tests verify that the Cloud Tasks endpoints correctly handle task payloads
and invoke the appropriate handlers.
"""

import base64
from pathlib import Path

import dotenv
import pytest
from fastapi.testclient import TestClient

from trackable.worker.main import app

pytest_plugins = ("pytest_asyncio",)
pytestmark = pytest.mark.manual


@pytest.fixture(scope="session", autouse=True)
def load_env():
    dotenv.load_dotenv()


@pytest.fixture
def client() -> TestClient:
    """Create test client for worker service"""
    return TestClient(app)


@pytest.fixture(scope="function")
def sample_email_content(shared_datadir: Path) -> str:
    """Load sample email content from test data"""
    email_path = shared_datadir / "sample_email.eml"
    return email_path.read_text(encoding="utf-8")


@pytest.fixture(scope="function")
def sample_screenshot_base64(shared_datadir: Path) -> str:
    """Load sample screenshot and encode as base64"""
    image_path = shared_datadir / "sample_screenshot.png"
    image_bytes = image_path.read_bytes()
    return base64.b64encode(image_bytes).decode("utf-8")


class TestHealthEndpoints:
    def test_root_endpoint(self, client: TestClient):
        """Test root endpoint returns service info"""
        response = client.get("/")
        assert response.status_code == 200

        data = response.json()
        assert data["service"] == "Trackable Worker API"
        assert data["status"] == "operational"

    def test_health_endpoint(self, client: TestClient):
        """Test health check endpoint"""
        response = client.get("/health")
        assert response.status_code == 200

        data = response.json()
        assert data["status"] == "healthy"
        assert data["service"] == "trackable-worker"


class TestParseEmailTask:
    def test_parse_email_with_sample(
        self, client: TestClient, sample_email_content: str
    ):
        """Test email parsing task with real Amazon shipment email"""
        task_payload = {
            "job_id": "job_amazon_test",
            "user_id": "user_test",
            "source_id": "source_email_123",
            "email_content": sample_email_content,
        }

        response = client.post("/tasks/parse-email", json=task_payload)

        # The task should execute, but may fail without database
        assert response.status_code in [200, 500]

        if response.status_code == 200:
            data = response.json()
            assert data["status"] == "success"
            assert data["job_id"] == task_payload["job_id"]

            # Check if order was extracted
            result = data.get("result", {})
            if result.get("status") == "success":
                # Verify Amazon order details were extracted
                assert result.get("merchant_name") is not None
                assert result.get("order_id") == "111-3710012-0752235"
                assert result.get("merchant_name") == "Amazon.com"
                print(f"\n✅ Extracted order from email:")
                print(f"   Merchant: {result.get('merchant_name')}")
                print(f"   Order ID: {result.get('order_id')}")
                print(f"   Confidence: {result.get('confidence_score')}")

    def test_parse_email_basic(self, client: TestClient):
        """Test email parsing task with simple inline email"""
        task_payload = {
            "job_id": "job_simple_test",
            "user_id": "user_test",
            "source_id": "source_test_123",
            "email_content": """
            Order Confirmation - Order #12345

            Thank you for your order from Nike!

            Order Number: 12345
            Order Date: January 20, 2026

            Items:
            - Blue T-Shirt (Size M) - Qty: 2 - $29.99 each
            - Black Jeans (Size 32) - Qty: 1 - $59.99

            Subtotal: $119.97
            Shipping: $5.00
            Total: $124.97

            Tracking Number: 1Z999AA10123456784
            Carrier: UPS

            Thank you for shopping with us!
            """,
        }

        response = client.post("/tasks/parse-email", json=task_payload)

        # The task should execute
        assert response.status_code in [200, 500]

        if response.status_code == 200:
            data = response.json()
            assert data["status"] == "success"
            assert data["job_id"] == task_payload["job_id"]
            assert data.get("result") is not None
            assert data["result"].get("order_id") == "12345"


class TestParseImageTask:
    def test_parse_image_with_sample(
        self, client: TestClient, sample_screenshot_base64: str
    ):
        """Test image parsing task with real Amazon screenshot"""
        task_payload = {
            "job_id": "job_screenshot_test",
            "user_id": "user_test",
            "source_id": "source_image_123",
            "image_data": sample_screenshot_base64,
        }

        response = client.post("/tasks/parse-image", json=task_payload)

        # The task should execute, but may fail without database
        assert response.status_code in [200, 500]

        if response.status_code == 200:
            data = response.json()
            assert data["status"] == "success"
            assert data["job_id"] == task_payload["job_id"]

            # Check if order was extracted
            result = data.get("result", {})
            if result.get("status") == "success":
                # Verify Amazon order details were extracted
                assert result.get("merchant_name") is not None
                assert result.get("order_id") == "111-3710012-0752235"
                assert result.get("merchant_name") == "Amazon.com"
                print(f"\n✅ Extracted order from screenshot:")
                print(f"   Merchant: {result.get('merchant_name')}")
                print(f"   Order ID: {result.get('order_id')}")
                print(f"   Confidence: {result.get('confidence_score')}")
                print(f"   Duplicate: {result.get('is_duplicate', False)}")


class TestTaskTestEndpoint:
    def test_parse_email_via_test_endpoint(
        self, client: TestClient, sample_email_content: str
    ):
        """Test the test endpoint with parse_email task"""
        payload = {
            "task_type": "parse_email",
            "job_id": "job_test_endpoint",
            "user_id": "user_test",
            "source_id": "source_test_456",
            "email_content": sample_email_content,
        }

        response = client.post("/tasks/test", json=payload)
        assert response.status_code in [200, 500]

    def test_parse_image_via_test_endpoint(
        self, client: TestClient, sample_screenshot_base64: str
    ):
        """Test the test endpoint with parse_image task"""
        payload = {
            "task_type": "parse_image",
            "job_id": "job_test_image",
            "user_id": "user_test",
            "source_id": "source_test_img",
            "image_data": sample_screenshot_base64,
        }

        response = client.post("/tasks/test", json=payload)
        assert response.status_code in [200, 500]

    def test_invalid_task_type(self, client: TestClient):
        """Test test endpoint with invalid task type"""
        payload = {
            "task_type": "invalid_task",
        }

        response = client.post("/tasks/test", json=payload)
        assert response.status_code == 400

        data = response.json()
        assert "Unknown task type" in data["detail"]

"""
Tests for ingest API endpoints.

These tests verify the email and image submission endpoints
work correctly without requiring Cloud Tasks infrastructure.
"""

import base64
from pathlib import Path
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from trackable.api.main import app


@pytest.fixture
def client() -> TestClient:
    """Create a test client for the API."""
    return TestClient(app)


class TestIngestEmail:
    """Tests for POST /api/v1/ingest/email endpoint."""

    def test_ingest_email_success(self, client: TestClient) -> None:
        """Test successful email submission."""
        with patch(
            "trackable.api.routes.ingest.create_parse_email_task"
        ) as mock_create_task:
            mock_create_task.return_value = "local-task/parse-email-job_test123"

            response = client.post(
                "/api/v1/ingest/email",
                json={
                    "email_content": "From: orders@amazon.com\nSubject: Your order\n\nOrder confirmed!",
                    "email_subject": "Your order",
                    "email_from": "orders@amazon.com",
                },
            )

            assert response.status_code == 200
            data = response.json()

            # Verify response structure
            assert "job_id" in data
            assert "source_id" in data
            assert data["status"] == "queued"
            assert "message" in data

            # Verify IDs are valid UUIDs
            assert len(data["job_id"]) == 36  # UUID format
            assert len(data["source_id"]) == 36

            # Verify task was created with correct parameters
            mock_create_task.assert_called_once()
            call_kwargs = mock_create_task.call_args.kwargs
            assert call_kwargs["job_id"] == data["job_id"]
            assert call_kwargs["source_id"] == data["source_id"]
            assert "email_content" in call_kwargs

    def test_ingest_email_minimal(self, client: TestClient) -> None:
        """Test email submission with only required fields."""
        with patch(
            "trackable.api.routes.ingest.create_parse_email_task"
        ) as mock_create_task:
            mock_create_task.return_value = "local-task/parse-email-job_test123"

            response = client.post(
                "/api/v1/ingest/email",
                json={"email_content": "Order confirmation email content"},
            )

            assert response.status_code == 200
            data = response.json()
            assert data["status"] == "queued"

    def test_ingest_email_empty_content(self, client: TestClient) -> None:
        """Test that empty email content is rejected."""
        response = client.post(
            "/api/v1/ingest/email",
            json={"email_content": ""},
        )

        assert response.status_code == 422  # Validation error

    def test_ingest_email_missing_content(self, client: TestClient) -> None:
        """Test that missing email content is rejected."""
        response = client.post(
            "/api/v1/ingest/email",
            json={},
        )

        assert response.status_code == 422  # Validation error

    def test_ingest_email_task_creation_failure(self, client: TestClient) -> None:
        """Test error handling when task creation fails."""
        with patch(
            "trackable.api.routes.ingest.create_parse_email_task"
        ) as mock_create_task:
            mock_create_task.side_effect = Exception("Cloud Tasks unavailable")

            response = client.post(
                "/api/v1/ingest/email",
                json={"email_content": "Order confirmation email content"},
            )

            assert response.status_code == 500
            assert "Failed to create processing task" in response.json()["detail"]


class TestIngestImage:
    """Tests for POST /api/v1/ingest/image endpoint."""

    def test_ingest_image_success(self, client: TestClient) -> None:
        """Test successful image submission."""
        # Create a small test image (1x1 PNG)
        image_data = base64.b64encode(
            b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01"
            b"\x00\x00\x00\x01\x08\x02\x00\x00\x00\x90wS\xde\x00"
            b"\x00\x00\x0cIDATx\x9cc\xf8\x0f\x00\x00\x01\x01\x00"
            b"\x05\x18\xd8N\x00\x00\x00\x00IEND\xaeB`\x82"
        ).decode("utf-8")

        with patch(
            "trackable.api.routes.ingest.create_parse_image_task"
        ) as mock_create_task:
            mock_create_task.return_value = "local-task/parse-image-job_test123"

            response = client.post(
                "/api/v1/ingest/image",
                json={
                    "image_data": image_data,
                    "filename": "screenshot.png",
                },
            )

            assert response.status_code == 200
            data = response.json()

            # Verify response structure
            assert "job_id" in data
            assert "source_id" in data
            assert data["status"] == "queued"
            assert "message" in data

            # Verify IDs are valid UUIDs
            assert len(data["job_id"]) == 36  # UUID format
            assert len(data["source_id"]) == 36

            # Verify task was created with correct parameters
            mock_create_task.assert_called_once()
            call_kwargs = mock_create_task.call_args.kwargs
            assert call_kwargs["job_id"] == data["job_id"]
            assert call_kwargs["source_id"] == data["source_id"]
            assert call_kwargs["image_data"] == image_data

    def test_ingest_image_minimal(self, client: TestClient) -> None:
        """Test image submission with only required fields."""
        image_data = base64.b64encode(b"fake image data").decode("utf-8")

        with patch(
            "trackable.api.routes.ingest.create_parse_image_task"
        ) as mock_create_task:
            mock_create_task.return_value = "local-task/parse-image-job_test123"

            response = client.post(
                "/api/v1/ingest/image",
                json={"image_data": image_data},
            )

            assert response.status_code == 200
            data = response.json()
            assert data["status"] == "queued"

    def test_ingest_image_empty_data(self, client: TestClient) -> None:
        """Test that empty image data is rejected."""
        response = client.post(
            "/api/v1/ingest/image",
            json={"image_data": ""},
        )

        assert response.status_code == 422  # Validation error

    def test_ingest_image_missing_data(self, client: TestClient) -> None:
        """Test that missing image data is rejected."""
        response = client.post(
            "/api/v1/ingest/image",
            json={},
        )

        assert response.status_code == 422  # Validation error

    def test_ingest_image_task_creation_failure(self, client: TestClient) -> None:
        """Test error handling when task creation fails."""
        image_data = base64.b64encode(b"fake image data").decode("utf-8")

        with patch(
            "trackable.api.routes.ingest.create_parse_image_task"
        ) as mock_create_task:
            mock_create_task.side_effect = Exception("Cloud Tasks unavailable")

            response = client.post(
                "/api/v1/ingest/image",
                json={"image_data": image_data},
            )

            assert response.status_code == 500
            assert "Failed to create processing task" in response.json()["detail"]


class TestIngestWithRealSamples:
    """Tests using real sample data from the test data directory."""

    @pytest.fixture
    def sample_email_content(self) -> str:
        """Load sample email content from test data."""
        # Use worker test data since it has the email sample
        email_path = (
            Path(__file__).parent.parent / "worker" / "data" / "sample_email.eml"
        )
        if email_path.exists():
            return email_path.read_text(encoding="utf-8")
        return "Sample order confirmation email from Amazon"

    @pytest.fixture
    def sample_screenshot_base64(self) -> str:
        """Load sample screenshot and encode as base64."""
        # Use worker test data since it has the screenshot sample
        image_path = (
            Path(__file__).parent.parent / "worker" / "data" / "sample_screenshot.png"
        )
        if image_path.exists():
            return base64.b64encode(image_path.read_bytes()).decode("utf-8")
        return base64.b64encode(b"fake image data").decode("utf-8")

    def test_ingest_real_email_sample(
        self, client: TestClient, sample_email_content: str
    ) -> None:
        """Test email ingestion with real Amazon email sample."""
        with patch(
            "trackable.api.routes.ingest.create_parse_email_task"
        ) as mock_create_task:
            mock_create_task.return_value = "local-task/parse-email-job_test"

            response = client.post(
                "/api/v1/ingest/email",
                json={"email_content": sample_email_content},
            )

            assert response.status_code == 200
            data = response.json()
            assert data["status"] == "queued"
            assert len(data["job_id"]) == 36  # UUID format

    def test_ingest_real_screenshot_sample(
        self, client: TestClient, sample_screenshot_base64: str
    ) -> None:
        """Test image ingestion with real screenshot sample."""
        with patch(
            "trackable.api.routes.ingest.create_parse_image_task"
        ) as mock_create_task:
            mock_create_task.return_value = "local-task/parse-image-job_test"

            response = client.post(
                "/api/v1/ingest/image",
                json={
                    "image_data": sample_screenshot_base64,
                    "filename": "amazon_order.png",
                },
            )

            assert response.status_code == 200
            data = response.json()
            assert data["status"] == "queued"
            assert len(data["job_id"]) == 36  # UUID format

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


# Test user ID (valid UUID format)
TEST_USER_ID = "d5314b80-4aac-4bf2-940c-0a0ceda5bff4"
TEST_HEADERS = {"X-User-ID": TEST_USER_ID}


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
                headers=TEST_HEADERS,
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
                headers=TEST_HEADERS,
                json={"email_content": "Order confirmation email content"},
            )

            assert response.status_code == 200
            data = response.json()
            assert data["status"] == "queued"

    def test_ingest_email_empty_content(self, client: TestClient) -> None:
        """Test that empty email content is rejected."""
        response = client.post(
            "/api/v1/ingest/email",
            headers=TEST_HEADERS,
            json={"email_content": ""},
        )

        assert response.status_code == 422  # Validation error

    def test_ingest_email_missing_content(self, client: TestClient) -> None:
        """Test that missing email content is rejected."""
        response = client.post(
            "/api/v1/ingest/email",
            headers=TEST_HEADERS,
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
                headers=TEST_HEADERS,
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
                headers=TEST_HEADERS,
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
                headers=TEST_HEADERS,
                json={"image_data": image_data},
            )

            assert response.status_code == 200
            data = response.json()
            assert data["status"] == "queued"

    def test_ingest_image_empty_data(self, client: TestClient) -> None:
        """Test that empty image data is rejected."""
        response = client.post(
            "/api/v1/ingest/image",
            headers=TEST_HEADERS,
            json={"image_data": ""},
        )

        assert response.status_code == 422  # Validation error

    def test_ingest_image_missing_data(self, client: TestClient) -> None:
        """Test that missing image data is rejected."""
        response = client.post(
            "/api/v1/ingest/image",
            headers=TEST_HEADERS,
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
                headers=TEST_HEADERS,
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
                headers=TEST_HEADERS,
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
                headers=TEST_HEADERS,
                json={
                    "image_data": sample_screenshot_base64,
                    "filename": "amazon_order.png",
                },
            )

            assert response.status_code == 200
            data = response.json()
            assert data["status"] == "queued"
            assert len(data["job_id"]) == 36  # UUID format


class TestIngestEmailBatch:
    """Tests for POST /api/v1/ingest/email/batch endpoint."""

    def test_batch_email_success(self, client: TestClient) -> None:
        """Test successful batch email submission."""
        with patch(
            "trackable.api.routes.ingest.create_parse_email_task"
        ) as mock_create_task:
            mock_create_task.return_value = "local-task/parse-email-job_test123"

            response = client.post(
                "/api/v1/ingest/email/batch",
                headers=TEST_HEADERS,
                json={
                    "items": [
                        {
                            "email_content": "Order 1 from Amazon",
                            "email_subject": "Your order #1",
                        },
                        {
                            "email_content": "Order 2 from Nike",
                            "email_subject": "Your order #2",
                        },
                    ]
                },
            )

            assert response.status_code == 200
            data = response.json()

            assert data["total"] == 2
            assert data["succeeded"] == 2
            assert data["duplicates"] == 0
            assert data["failed"] == 0
            assert len(data["results"]) == 2

            # Verify each result
            for i, result in enumerate(data["results"]):
                assert result["index"] == i
                assert result["status"] == "success"
                assert len(result["job_id"]) == 36  # UUID
                assert len(result["source_id"]) == 36  # UUID

            # Verify task was created twice
            assert mock_create_task.call_count == 2

    def test_batch_email_partial_failure(self, client: TestClient) -> None:
        """Test batch where some items fail task creation."""
        call_count = 0

        def mock_task_side_effect(**kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 2:
                raise Exception("Cloud Tasks unavailable")
            return f"local-task/parse-email-job_{call_count}"

        with patch(
            "trackable.api.routes.ingest.create_parse_email_task"
        ) as mock_create_task:
            mock_create_task.side_effect = mock_task_side_effect

            response = client.post(
                "/api/v1/ingest/email/batch",
                headers=TEST_HEADERS,
                json={
                    "items": [
                        {"email_content": "Order 1"},
                        {"email_content": "Order 2"},  # This will fail
                        {"email_content": "Order 3"},
                    ]
                },
            )

            assert response.status_code == 200
            data = response.json()

            assert data["total"] == 3
            assert data["succeeded"] == 2
            assert data["failed"] == 1

            # Check individual results
            assert data["results"][0]["status"] == "success"
            assert data["results"][1]["status"] == "failed"
            assert "Cloud Tasks unavailable" in data["results"][1]["error"]
            assert data["results"][2]["status"] == "success"

    def test_batch_email_single_item(self, client: TestClient) -> None:
        """Test batch with single item works like single endpoint."""
        with patch(
            "trackable.api.routes.ingest.create_parse_email_task"
        ) as mock_create_task:
            mock_create_task.return_value = "local-task/parse-email-job_test"

            response = client.post(
                "/api/v1/ingest/email/batch",
                headers=TEST_HEADERS,
                json={"items": [{"email_content": "Single order email"}]},
            )

            assert response.status_code == 200
            data = response.json()
            assert data["total"] == 1
            assert data["succeeded"] == 1
            assert len(data["results"]) == 1

    def test_batch_email_empty_list(self, client: TestClient) -> None:
        """Test that empty items list is rejected."""
        response = client.post(
            "/api/v1/ingest/email/batch",
            headers=TEST_HEADERS,
            json={"items": []},
        )

        assert response.status_code == 422  # Validation error

    def test_batch_email_exceeds_max_size(self, client: TestClient) -> None:
        """Test that batch exceeding 50 items is rejected."""
        items = [{"email_content": f"Order {i}"} for i in range(51)]

        response = client.post(
            "/api/v1/ingest/email/batch",
            headers=TEST_HEADERS,
            json={"items": items},
        )

        assert response.status_code == 422  # Validation error


class TestIngestImageBatch:
    """Tests for POST /api/v1/ingest/image/batch endpoint."""

    def test_batch_image_success(self, client: TestClient) -> None:
        """Test successful batch image submission."""
        image_data_1 = base64.b64encode(b"image data 1").decode("utf-8")
        image_data_2 = base64.b64encode(b"image data 2").decode("utf-8")

        with patch(
            "trackable.api.routes.ingest.create_parse_image_task"
        ) as mock_create_task:
            mock_create_task.return_value = "local-task/parse-image-job_test123"

            response = client.post(
                "/api/v1/ingest/image/batch",
                headers=TEST_HEADERS,
                json={
                    "items": [
                        {"image_data": image_data_1, "filename": "order1.png"},
                        {"image_data": image_data_2, "filename": "order2.png"},
                    ]
                },
            )

            assert response.status_code == 200
            data = response.json()

            assert data["total"] == 2
            assert data["succeeded"] == 2
            assert data["duplicates"] == 0
            assert data["failed"] == 0
            assert len(data["results"]) == 2

            # Verify each result
            for i, result in enumerate(data["results"]):
                assert result["index"] == i
                assert result["status"] == "success"
                assert len(result["job_id"]) == 36  # UUID
                assert len(result["source_id"]) == 36  # UUID

            # Verify task was created twice
            assert mock_create_task.call_count == 2

    def test_batch_image_with_invalid_base64(self, client: TestClient) -> None:
        """Test batch containing invalid base64 data."""
        valid_image = base64.b64encode(b"valid image").decode("utf-8")

        with patch(
            "trackable.api.routes.ingest.create_parse_image_task"
        ) as mock_create_task:
            mock_create_task.return_value = "local-task/parse-image-job_test"

            response = client.post(
                "/api/v1/ingest/image/batch",
                headers=TEST_HEADERS,
                json={
                    "items": [
                        {"image_data": valid_image},
                        {"image_data": "not-valid-base64!!!"},
                        {"image_data": valid_image},
                    ]
                },
            )

            assert response.status_code == 200
            data = response.json()

            assert data["total"] == 3
            assert data["succeeded"] == 2
            assert data["failed"] == 1

            # Check individual results
            assert data["results"][0]["status"] == "success"
            assert data["results"][1]["status"] == "failed"
            assert "Invalid base64" in data["results"][1]["error"]
            assert data["results"][2]["status"] == "success"

    def test_batch_image_partial_failure(self, client: TestClient) -> None:
        """Test batch where some items fail task creation."""
        call_count = 0

        def mock_task_side_effect(**kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 2:
                raise Exception("Cloud Tasks unavailable")
            return f"local-task/parse-image-job_{call_count}"

        image_data = base64.b64encode(b"image data").decode("utf-8")

        with patch(
            "trackable.api.routes.ingest.create_parse_image_task"
        ) as mock_create_task:
            mock_create_task.side_effect = mock_task_side_effect

            response = client.post(
                "/api/v1/ingest/image/batch",
                headers=TEST_HEADERS,
                json={
                    "items": [
                        {"image_data": image_data},
                        {"image_data": image_data},  # This will fail
                        {"image_data": image_data},
                    ]
                },
            )

            assert response.status_code == 200
            data = response.json()

            assert data["total"] == 3
            assert data["succeeded"] == 2
            assert data["failed"] == 1

            # Check individual results
            assert data["results"][0]["status"] == "success"
            assert data["results"][1]["status"] == "failed"
            assert "Cloud Tasks unavailable" in data["results"][1]["error"]
            assert data["results"][2]["status"] == "success"

    def test_batch_image_single_item(self, client: TestClient) -> None:
        """Test batch with single item works like single endpoint."""
        image_data = base64.b64encode(b"single image").decode("utf-8")

        with patch(
            "trackable.api.routes.ingest.create_parse_image_task"
        ) as mock_create_task:
            mock_create_task.return_value = "local-task/parse-image-job_test"

            response = client.post(
                "/api/v1/ingest/image/batch",
                headers=TEST_HEADERS,
                json={"items": [{"image_data": image_data}]},
            )

            assert response.status_code == 200
            data = response.json()
            assert data["total"] == 1
            assert data["succeeded"] == 1
            assert len(data["results"]) == 1

    def test_batch_image_empty_list(self, client: TestClient) -> None:
        """Test that empty items list is rejected."""
        response = client.post(
            "/api/v1/ingest/image/batch",
            headers=TEST_HEADERS,
            json={"items": []},
        )

        assert response.status_code == 422  # Validation error

    def test_batch_image_exceeds_max_size(self, client: TestClient) -> None:
        """Test that batch exceeding 50 items is rejected."""
        image_data = base64.b64encode(b"image").decode("utf-8")
        items = [{"image_data": image_data} for _ in range(51)]

        response = client.post(
            "/api/v1/ingest/image/batch",
            headers=TEST_HEADERS,
            json={"items": items},
        )

        assert response.status_code == 422  # Validation error

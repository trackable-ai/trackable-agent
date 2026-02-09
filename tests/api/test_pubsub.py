"""
Tests for Pub/Sub handler endpoints.

These tests verify the Gmail notification and policy refresh handlers
work correctly without requiring actual Pub/Sub or Cloud Tasks infrastructure.
"""

import base64
import json
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from trackable.api.main import app
from trackable.models.oauth import OAuthToken
from trackable.models.order import Merchant


@pytest.fixture
def client() -> TestClient:
    """Create a test client for the API."""
    return TestClient(app)


def _create_pubsub_message(data: dict) -> dict:
    """Helper to create a Pub/Sub push message envelope."""
    encoded_data = base64.b64encode(json.dumps(data).encode()).decode()
    return {
        "message": {
            "data": encoded_data,
            "messageId": "test-message-id",
            "publishTime": "2026-01-26T12:00:00Z",
            "attributes": {},
        },
        "subscription": "projects/test-project/subscriptions/test-subscription",
    }


class TestGmailNotificationHandler:
    """Tests for POST /pubsub/gmail endpoint."""

    def test_gmail_notification_success(self, client: TestClient) -> None:
        """Test successful Gmail notification handling."""
        mock_oauth_token = OAuthToken(
            id="tok_123",
            user_id="usr_456",
            provider="gmail",
            provider_email="user@gmail.com",
            access_token="ya29.xxx",
        )

        with (
            patch(
                "trackable.api.routes.pubsub.DatabaseConnection.is_initialized",
                return_value=True,
            ),
            patch("trackable.api.routes.pubsub.UnitOfWork") as mock_uow_class,
            patch(
                "trackable.api.routes.pubsub.create_gmail_sync_task"
            ) as mock_create_task,
        ):
            # Set up mock UnitOfWork
            mock_uow = MagicMock()
            mock_uow.__enter__ = MagicMock(return_value=mock_uow)
            mock_uow.__exit__ = MagicMock(return_value=False)
            mock_uow.oauth_tokens.get_by_provider_email.return_value = mock_oauth_token
            mock_uow_class.return_value = mock_uow

            mock_create_task.return_value = "local-task/gmail-sync-abc123"

            message = _create_pubsub_message(
                {"emailAddress": "user@gmail.com", "historyId": "12345"}
            )
            response = client.post("/pubsub/gmail", json=message)

            assert response.status_code == 200
            data = response.json()
            assert data["status"] == "queued"
            assert data["tasks_created"] == 1
            assert data["details"]["email"] == "user@gmail.com"
            assert data["details"]["history_id"] == "12345"
            assert "job_id" in data["details"]  # Verify job_id is returned
            assert len(data["details"]["job_id"]) == 36  # UUID format

            # Verify job was created
            mock_uow.jobs.create.assert_called_once()
            created_job = mock_uow.jobs.create.call_args[0][0]
            assert created_job.user_id == "usr_456"
            assert created_job.job_type.value == "gmail_sync"

            # Verify task was created with correct parameters
            mock_create_task.assert_called_once_with(
                user_id="usr_456",
                user_email="user@gmail.com",
                history_id="12345",
            )

    def test_gmail_notification_user_not_found(self, client: TestClient) -> None:
        """Test Gmail notification for unknown user."""
        with (
            patch(
                "trackable.api.routes.pubsub.DatabaseConnection.is_initialized",
                return_value=True,
            ),
            patch("trackable.api.routes.pubsub.UnitOfWork") as mock_uow_class,
        ):
            mock_uow = MagicMock()
            mock_uow.__enter__ = MagicMock(return_value=mock_uow)
            mock_uow.__exit__ = MagicMock(return_value=False)
            mock_uow.oauth_tokens.get_by_provider_email.return_value = None
            mock_uow_class.return_value = mock_uow

            message = _create_pubsub_message(
                {"emailAddress": "unknown@gmail.com", "historyId": "12345"}
            )
            response = client.post("/pubsub/gmail", json=message)

            assert response.status_code == 200
            data = response.json()
            assert data["status"] == "ignored"
            assert data["tasks_created"] == 0
            assert "not found" in data["message"].lower()

    def test_gmail_notification_database_not_initialized(
        self, client: TestClient
    ) -> None:
        """Test Gmail notification when database is not configured."""
        with patch(
            "trackable.api.routes.pubsub.DatabaseConnection.is_initialized",
            return_value=False,
        ):
            message = _create_pubsub_message(
                {"emailAddress": "user@gmail.com", "historyId": "12345"}
            )
            response = client.post("/pubsub/gmail", json=message)

            assert response.status_code == 200
            data = response.json()
            assert data["status"] == "skipped"
            assert data["tasks_created"] == 0

    def test_gmail_notification_invalid_payload(self, client: TestClient) -> None:
        """Test Gmail notification with invalid payload."""
        # Invalid base64 data
        response = client.post(
            "/pubsub/gmail",
            json={
                "message": {
                    "data": "not-valid-base64!!!",
                    "messageId": "test-id",
                    "attributes": {},
                },
                "subscription": "projects/test/subscriptions/test",
            },
        )

        assert response.status_code == 400
        assert "Invalid Gmail notification payload" in response.json()["detail"]

    def test_gmail_notification_missing_fields(self, client: TestClient) -> None:
        """Test Gmail notification with missing required fields."""
        # Missing emailAddress field
        message = _create_pubsub_message({"historyId": "12345"})
        response = client.post("/pubsub/gmail", json=message)

        assert response.status_code == 400

    def test_gmail_notification_task_creation_failure(self, client: TestClient) -> None:
        """Test error handling when task creation fails."""
        mock_oauth_token = OAuthToken(
            id="tok_123",
            user_id="usr_456",
            provider="gmail",
            provider_email="user@gmail.com",
            access_token="ya29.xxx",
        )

        with (
            patch(
                "trackable.api.routes.pubsub.DatabaseConnection.is_initialized",
                return_value=True,
            ),
            patch("trackable.api.routes.pubsub.UnitOfWork") as mock_uow_class,
            patch(
                "trackable.api.routes.pubsub.create_gmail_sync_task"
            ) as mock_create_task,
        ):
            mock_uow = MagicMock()
            mock_uow.__enter__ = MagicMock(return_value=mock_uow)
            mock_uow.__exit__ = MagicMock(return_value=False)
            mock_uow.oauth_tokens.get_by_provider_email.return_value = mock_oauth_token
            mock_uow_class.return_value = mock_uow

            mock_create_task.side_effect = Exception("Cloud Tasks unavailable")

            message = _create_pubsub_message(
                {"emailAddress": "user@gmail.com", "historyId": "12345"}
            )
            response = client.post("/pubsub/gmail", json=message)

            assert response.status_code == 500
            assert "Failed to create Gmail sync task" in response.json()["detail"]


class TestPolicyRefreshHandler:
    """Tests for POST /pubsub/policy endpoint."""

    def test_policy_refresh_all_merchants(self, client: TestClient) -> None:
        """Test policy refresh for all merchants."""
        mock_merchants = [
            Merchant(id="m1", name="Amazon", domain="amazon.com"),
            Merchant(id="m2", name="Nike", domain="nike.com"),
        ]

        with (
            patch(
                "trackable.api.routes.pubsub.DatabaseConnection.is_initialized",
                return_value=True,
            ),
            patch("trackable.api.routes.pubsub.UnitOfWork") as mock_uow_class,
            patch(
                "trackable.api.routes.pubsub.create_policy_refresh_task"
            ) as mock_create_task,
        ):
            mock_uow = MagicMock()
            mock_uow.__enter__ = MagicMock(return_value=mock_uow)
            mock_uow.__exit__ = MagicMock(return_value=False)
            mock_uow.merchants.list_all.return_value = mock_merchants
            mock_uow_class.return_value = mock_uow

            mock_create_task.return_value = "local-task/policy-refresh-xxx"

            # Default payload refreshes all merchants
            message = _create_pubsub_message({"refresh_all": True})
            response = client.post("/pubsub/policy", json=message)

            assert response.status_code == 200
            data = response.json()
            assert data["status"] == "queued"
            assert data["tasks_created"] == 2
            assert data["details"]["merchants_found"] == 2
            assert "job_ids" in data["details"]  # Verify job_ids are returned
            assert len(data["details"]["job_ids"]) == 2

            # Verify jobs were created for each merchant
            assert mock_uow.jobs.create.call_count == 2

            # Verify tasks were created for each merchant
            assert mock_create_task.call_count == 2

            # Verify job_id was passed to create_policy_refresh_task
            for call in mock_create_task.call_args_list:
                assert "job_id" in call.kwargs

    def test_policy_refresh_specific_merchants(self, client: TestClient) -> None:
        """Test policy refresh for specific merchants."""
        mock_merchant = Merchant(id="m1", name="Amazon", domain="amazon.com")

        with (
            patch(
                "trackable.api.routes.pubsub.DatabaseConnection.is_initialized",
                return_value=True,
            ),
            patch("trackable.api.routes.pubsub.UnitOfWork") as mock_uow_class,
            patch(
                "trackable.api.routes.pubsub.create_policy_refresh_task"
            ) as mock_create_task,
        ):
            mock_uow = MagicMock()
            mock_uow.__enter__ = MagicMock(return_value=mock_uow)
            mock_uow.__exit__ = MagicMock(return_value=False)
            mock_uow.merchants.get_by_id.return_value = mock_merchant
            mock_uow_class.return_value = mock_uow

            mock_create_task.return_value = "local-task/policy-refresh-xxx"

            message = _create_pubsub_message(
                {"refresh_all": False, "merchant_ids": ["m1"]}
            )
            response = client.post("/pubsub/policy", json=message)

            assert response.status_code == 200
            data = response.json()
            assert data["status"] == "queued"
            assert data["tasks_created"] == 1

            # Verify job_id was passed to create_policy_refresh_task
            call_kwargs = mock_create_task.call_args.kwargs
            assert "job_id" in call_kwargs

    def test_policy_refresh_no_merchants(self, client: TestClient) -> None:
        """Test policy refresh when no merchants exist."""
        with (
            patch(
                "trackable.api.routes.pubsub.DatabaseConnection.is_initialized",
                return_value=True,
            ),
            patch("trackable.api.routes.pubsub.UnitOfWork") as mock_uow_class,
        ):
            mock_uow = MagicMock()
            mock_uow.__enter__ = MagicMock(return_value=mock_uow)
            mock_uow.__exit__ = MagicMock(return_value=False)
            mock_uow.merchants.list_all.return_value = []
            mock_uow_class.return_value = mock_uow

            message = _create_pubsub_message({"refresh_all": True})
            response = client.post("/pubsub/policy", json=message)

            assert response.status_code == 200
            data = response.json()
            assert data["status"] == "completed"
            assert data["tasks_created"] == 0
            assert "No merchants" in data["message"]

    def test_policy_refresh_database_not_initialized(self, client: TestClient) -> None:
        """Test policy refresh when database is not configured."""
        with patch(
            "trackable.api.routes.pubsub.DatabaseConnection.is_initialized",
            return_value=False,
        ):
            message = _create_pubsub_message({"refresh_all": True})
            response = client.post("/pubsub/policy", json=message)

            assert response.status_code == 200
            data = response.json()
            assert data["status"] == "skipped"
            assert data["tasks_created"] == 0

    def test_policy_refresh_empty_payload(self, client: TestClient) -> None:
        """Test policy refresh with empty/default payload."""
        mock_merchants = [Merchant(id="m1", name="Amazon", domain="amazon.com")]

        with (
            patch(
                "trackable.api.routes.pubsub.DatabaseConnection.is_initialized",
                return_value=True,
            ),
            patch("trackable.api.routes.pubsub.UnitOfWork") as mock_uow_class,
            patch(
                "trackable.api.routes.pubsub.create_policy_refresh_task"
            ) as mock_create_task,
        ):
            mock_uow = MagicMock()
            mock_uow.__enter__ = MagicMock(return_value=mock_uow)
            mock_uow.__exit__ = MagicMock(return_value=False)
            mock_uow.merchants.list_all.return_value = mock_merchants
            mock_uow_class.return_value = mock_uow

            mock_create_task.return_value = "local-task/policy-refresh-xxx"

            # Empty data should default to refresh_all=True
            response = client.post(
                "/pubsub/policy",
                json={
                    "message": {
                        "data": base64.b64encode(b"{}").decode(),
                        "messageId": "test-id",
                        "attributes": {},
                    },
                    "subscription": "projects/test/subscriptions/test",
                },
            )

            assert response.status_code == 200
            data = response.json()
            assert data["status"] == "queued"
            assert data["tasks_created"] == 1

    def test_policy_refresh_partial_task_failures(self, client: TestClient) -> None:
        """Test policy refresh when some task creations fail."""
        mock_merchants = [
            Merchant(id="m1", name="Amazon", domain="amazon.com"),
            Merchant(id="m2", name="Nike", domain="nike.com"),
        ]

        with (
            patch(
                "trackable.api.routes.pubsub.DatabaseConnection.is_initialized",
                return_value=True,
            ),
            patch("trackable.api.routes.pubsub.UnitOfWork") as mock_uow_class,
            patch(
                "trackable.api.routes.pubsub.create_policy_refresh_task"
            ) as mock_create_task,
        ):
            mock_uow = MagicMock()
            mock_uow.__enter__ = MagicMock(return_value=mock_uow)
            mock_uow.__exit__ = MagicMock(return_value=False)
            mock_uow.merchants.list_all.return_value = mock_merchants
            mock_uow_class.return_value = mock_uow

            # First call succeeds, second fails
            mock_create_task.side_effect = [
                "local-task/policy-refresh-xxx",
                Exception("Task creation failed"),
            ]

            message = _create_pubsub_message({"refresh_all": True})
            response = client.post("/pubsub/policy", json=message)

            assert response.status_code == 200
            data = response.json()
            assert data["status"] == "queued"  # Still queued because some succeeded
            assert data["tasks_created"] == 1
            assert len(data["details"]["errors"]) == 1
            assert data["details"]["errors"][0]["merchant"] == "nike.com"


class TestPubSubMessageFormat:
    """Tests for Pub/Sub message format validation."""

    def test_missing_message_field(self, client: TestClient) -> None:
        """Test request with missing message field."""
        response = client.post(
            "/pubsub/gmail",
            json={"subscription": "projects/test/subscriptions/test"},
        )
        assert response.status_code == 422

    def test_missing_subscription_field(self, client: TestClient) -> None:
        """Test request with missing subscription field."""
        response = client.post(
            "/pubsub/gmail",
            json={
                "message": {
                    "data": base64.b64encode(b"{}").decode(),
                    "messageId": "test-id",
                    "attributes": {},
                }
            },
        )
        assert response.status_code == 422

    def test_missing_data_field(self, client: TestClient) -> None:
        """Test request with missing data field in message."""
        response = client.post(
            "/pubsub/gmail",
            json={
                "message": {"messageId": "test-id", "attributes": {}},
                "subscription": "projects/test/subscriptions/test",
            },
        )
        assert response.status_code == 422

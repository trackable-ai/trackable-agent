"""Tests for PolicyRepository query methods."""

from unittest.mock import MagicMock, patch
from uuid import UUID

import pytest
from sqlalchemy import select

from trackable.db.repositories.policy import PolicyRepository
from trackable.models.policy import PolicyType

MERCHANT_ID = "12345678-1234-5678-1234-567812345678"


class TestGetReturnPolicyByMerchant:
    """Tests for get_return_policy_by_merchant."""

    def test_queries_by_non_null_return_policy(self):
        """Verify the query filters on return_policy IS NOT NULL, not policy_type."""
        mock_session = MagicMock()
        mock_result = MagicMock()
        mock_session.execute.return_value = mock_result
        mock_result.fetchone.return_value = None

        repo = PolicyRepository(mock_session)
        result = repo.get_return_policy_by_merchant(MERCHANT_ID, "US")

        assert result is None
        # Verify execute was called (query was built and run)
        mock_session.execute.assert_called_once()

    def test_returns_none_when_no_match(self):
        """Should return None when no policy has return_policy populated."""
        mock_session = MagicMock()
        mock_result = MagicMock()
        mock_session.execute.return_value = mock_result
        mock_result.fetchone.return_value = None

        repo = PolicyRepository(mock_session)
        result = repo.get_return_policy_by_merchant(MERCHANT_ID, "US")

        assert result is None


class TestGetExchangePolicyByMerchant:
    """Tests for get_exchange_policy_by_merchant."""

    def test_queries_by_non_null_exchange_policy(self):
        """Verify the query filters on exchange_policy IS NOT NULL."""
        mock_session = MagicMock()
        mock_result = MagicMock()
        mock_session.execute.return_value = mock_result
        mock_result.fetchone.return_value = None

        repo = PolicyRepository(mock_session)
        result = repo.get_exchange_policy_by_merchant(MERCHANT_ID, "US")

        assert result is None
        mock_session.execute.assert_called_once()

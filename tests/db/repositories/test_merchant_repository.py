"""Tests for MerchantRepository policy_urls support."""

from unittest.mock import MagicMock

from trackable.db.repositories.merchant import MerchantRepository
from trackable.models.order import Merchant


class TestPolicyUrlsField:
    """Tests for Merchant.policy_urls field."""

    def test_merchant_model_accepts_policy_urls(self):
        """Verify Merchant model has policy_urls field."""
        merchant = Merchant(
            id="merch-123",
            name="Nike",
            domain="nike.com",
            policy_urls=["https://nike.com/returns", "https://nike.com/exchanges"],
        )
        assert merchant.policy_urls == [
            "https://nike.com/returns",
            "https://nike.com/exchanges",
        ]

    def test_merchant_model_defaults_to_empty_list(self):
        """Verify policy_urls defaults to empty list."""
        merchant = Merchant(
            id="merch-123",
            name="Nike",
            domain="nike.com",
        )
        assert merchant.policy_urls == []

    def test_row_to_model_maps_policy_urls(self):
        """Verify _row_to_model includes policy_urls."""
        mock_session = MagicMock()
        repo = MerchantRepository(mock_session)

        mock_row = MagicMock()
        mock_row.id = "12345678-1234-5678-1234-567812345678"
        mock_row.name = "Nike"
        mock_row.domain = "nike.com"
        mock_row.aliases = []
        mock_row.support_email = None
        mock_row.support_url = None
        mock_row.return_portal_url = None
        mock_row.policy_urls = ["https://nike.com/returns"]

        merchant = repo._row_to_model(mock_row)

        assert merchant.policy_urls == ["https://nike.com/returns"]

    def test_row_to_model_handles_null_policy_urls(self):
        """Verify _row_to_model handles None policy_urls."""
        mock_session = MagicMock()
        repo = MerchantRepository(mock_session)

        mock_row = MagicMock()
        mock_row.id = "12345678-1234-5678-1234-567812345678"
        mock_row.name = "Nike"
        mock_row.domain = "nike.com"
        mock_row.aliases = []
        mock_row.support_email = None
        mock_row.support_url = None
        mock_row.return_portal_url = None
        mock_row.policy_urls = None

        merchant = repo._row_to_model(mock_row)

        assert merchant.policy_urls == []

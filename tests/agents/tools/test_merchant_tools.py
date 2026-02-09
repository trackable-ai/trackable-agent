"""Tests for chatbot merchant query tools."""

from unittest.mock import MagicMock, patch
from uuid import uuid4

from trackable.models.order import Merchant


def _make_merchant(
    name: str = "Nike",
    domain: str = "nike.com",
) -> Merchant:
    return Merchant(
        id=str(uuid4()),
        name=name,
        domain=domain,
        aliases=["nike"],
        support_email="support@nike.com",
        support_url="https://nike.com/help",
        return_portal_url="https://nike.com/returns",
    )


class TestGetMerchantInfo:
    """Tests for the get_merchant_info tool function."""

    @patch("trackable.agents.tools.merchant_tools.UnitOfWork")
    def test_finds_merchant_by_name(self, mock_uow_cls: MagicMock):
        from trackable.agents.tools.merchant_tools import get_merchant_info

        merchant = _make_merchant()
        mock_uow = MagicMock()
        mock_uow.__enter__ = MagicMock(return_value=mock_uow)
        mock_uow.__exit__ = MagicMock(return_value=False)
        mock_uow.merchants.get_by_name_or_domain.return_value = merchant
        mock_uow_cls.return_value = mock_uow

        result = get_merchant_info(merchant_name="Nike")

        assert result["status"] == "success"
        assert result["merchant"]["name"] == "Nike"
        assert result["merchant"]["domain"] == "nike.com"
        assert result["merchant"]["support_email"] == "support@nike.com"
        assert result["merchant"]["policy_urls"] == []

    @patch("trackable.agents.tools.merchant_tools.UnitOfWork")
    def test_finds_merchant_by_domain(self, mock_uow_cls: MagicMock):
        from trackable.agents.tools.merchant_tools import get_merchant_info

        merchant = _make_merchant()
        mock_uow = MagicMock()
        mock_uow.__enter__ = MagicMock(return_value=mock_uow)
        mock_uow.__exit__ = MagicMock(return_value=False)
        mock_uow.merchants.get_by_name_or_domain.return_value = merchant
        mock_uow_cls.return_value = mock_uow

        result = get_merchant_info(merchant_domain="nike.com")

        assert result["status"] == "success"
        assert result["merchant"]["policy_urls"] == []

    @patch("trackable.agents.tools.merchant_tools.UnitOfWork")
    def test_returns_not_found(self, mock_uow_cls: MagicMock):
        from trackable.agents.tools.merchant_tools import get_merchant_info

        mock_uow = MagicMock()
        mock_uow.__enter__ = MagicMock(return_value=mock_uow)
        mock_uow.__exit__ = MagicMock(return_value=False)
        mock_uow.merchants.get_by_name_or_domain.return_value = None
        mock_uow_cls.return_value = mock_uow

        result = get_merchant_info(merchant_name="UnknownStore")

        assert result["status"] == "not_found"

    @patch("trackable.agents.tools.merchant_tools.UnitOfWork")
    def test_requires_name_or_domain(self, mock_uow_cls: MagicMock):
        from trackable.agents.tools.merchant_tools import get_merchant_info

        result = get_merchant_info()

        assert result["status"] == "error"
        assert "name or domain" in result["message"].lower()

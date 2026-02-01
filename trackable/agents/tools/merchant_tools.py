"""Merchant query tools for the chatbot agent."""

from trackable.db.unit_of_work import UnitOfWork


def get_merchant_info(
    merchant_name: str | None = None,
    merchant_domain: str | None = None,
) -> dict:
    """Look up merchant information by name or domain.

    Use this tool to find details about a merchant/retailer including their
    support contact info and return portal URL.

    Args:
        merchant_name: The merchant's name (e.g., "Nike", "Amazon").
        merchant_domain: The merchant's website domain (e.g., "nike.com").

    Returns:
        dict: Merchant details including support info and return portal URL.
    """
    if not merchant_name and not merchant_domain:
        return {
            "status": "error",
            "message": "Please provide a merchant name or domain to look up.",
        }

    with UnitOfWork() as uow:
        merchant = uow.merchants.get_by_name_or_domain(
            name=merchant_name, domain=merchant_domain
        )

    if merchant is None:
        query = merchant_name or merchant_domain
        return {
            "status": "not_found",
            "message": f"Merchant '{query}' not found in our database.",
        }

    return {
        "status": "success",
        "merchant": {
            "name": merchant.name,
            "domain": merchant.domain,
            "support_email": merchant.support_email,
            "support_url": str(merchant.support_url) if merchant.support_url else None,
            "return_portal_url": (
                str(merchant.return_portal_url) if merchant.return_portal_url else None
            ),
        },
    }

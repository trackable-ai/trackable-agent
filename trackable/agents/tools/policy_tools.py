"""Policy query tools for the chatbot agent."""

from datetime import datetime, timezone

from trackable.db.unit_of_work import UnitOfWork
from trackable.models.policy import (
    ExchangeType,
    RefundMethod,
    ReturnCondition,
    ReturnShippingResponsibility,
)


def _format_return_condition(condition: ReturnCondition) -> str:
    """Convert ReturnCondition enum to human-readable string."""
    mapping = {
        ReturnCondition.UNUSED: "Item must be unused",
        ReturnCondition.ORIGINAL_PACKAGING: "Original packaging required",
        ReturnCondition.TAGS_ATTACHED: "Tags must be attached",
        ReturnCondition.RECEIPT_REQUIRED: "Receipt required",
        ReturnCondition.ANY_CONDITION: "Any condition accepted",
        ReturnCondition.CUSTOM: "Custom conditions apply",
    }
    return mapping.get(condition, str(condition))


def _format_refund_method(method: RefundMethod) -> str:
    """Convert RefundMethod enum to human-readable string."""
    mapping = {
        RefundMethod.ORIGINAL_PAYMENT: "Original payment method",
        RefundMethod.STORE_CREDIT: "Store credit only",
        RefundMethod.GIFT_CARD: "Gift card",
        RefundMethod.EITHER: "Customer choice (original payment or store credit)",
        RefundMethod.UNKNOWN: "Unknown",
    }
    return mapping.get(method, str(method))


def _format_shipping_responsibility(
    responsibility: ReturnShippingResponsibility,
    free_label: bool,
) -> str:
    """Convert shipping responsibility to human-readable string."""
    if free_label:
        return "Free return label provided by merchant"

    mapping = {
        ReturnShippingResponsibility.CUSTOMER: "Customer pays return shipping",
        ReturnShippingResponsibility.MERCHANT: "Merchant pays return shipping",
        ReturnShippingResponsibility.MERCHANT_IF_DEFECTIVE: "Merchant pays if item is defective, otherwise customer pays",
        ReturnShippingResponsibility.UNKNOWN: "Unknown",
    }
    return mapping.get(responsibility, str(responsibility))


def _format_exchange_types(exchange_types: list[ExchangeType]) -> list[str]:
    """Convert ExchangeType enums to human-readable strings."""
    mapping = {
        ExchangeType.SIZE_ONLY: "Size only",
        ExchangeType.COLOR_ONLY: "Color only",
        ExchangeType.SIZE_OR_COLOR: "Size or color",
        ExchangeType.SAME_ITEM: "Same item variants only",
        ExchangeType.ANY_ITEM: "Any item",
        ExchangeType.UNKNOWN: "Unknown",
    }
    return [mapping.get(et, str(et)) for et in exchange_types]


def get_return_policy(
    merchant_name: str | None = None,
    merchant_domain: str | None = None,
    country_code: str = "US",
) -> dict:
    """
    Get return policy details for a merchant.

    Use this to answer questions about return policies, return windows,
    conditions, refund methods, shipping costs, and excluded categories.

    Args:
        merchant_name: The merchant's name (e.g., "Nike", "Amazon").
        merchant_domain: The merchant's website domain (e.g., "nike.com").
        country_code: Country code (default "US").

    Returns:
        dict: Return policy details or error/not_found status.
    """
    if not merchant_name and not merchant_domain:
        return {
            "status": "error",
            "message": "Please provide a merchant name or domain to look up the policy.",
        }

    with UnitOfWork() as uow:
        # Look up merchant
        merchant = uow.merchants.get_by_name_or_domain(
            name=merchant_name, domain=merchant_domain
        )
        if merchant is None:
            query = merchant_name or merchant_domain
            return {
                "status": "not_found",
                "message": f"Merchant '{query}' not found in our database.",
            }

        # Look up return policy
        policy = uow.policies.get_return_policy_by_merchant(
            merchant_id=merchant.id,
            country_code=country_code,
        )

    if policy is None:
        return {
            "status": "not_found",
            "message": f"No return policy data available for {merchant.name}.",
        }

    # Extract return policy details
    if policy.return_policy is None:
        return {
            "status": "not_found",
            "message": f"Return policy data is incomplete for {merchant.name}.",
        }

    rp = policy.return_policy

    return {
        "status": "success",
        "merchant": merchant.name,
        "policy_type": "return",
        "country": country_code,
        "details": {
            "allowed": rp.allowed,
            "window_days": rp.window_days,
            "conditions": [_format_return_condition(c) for c in rp.conditions],
            "refund_method": _format_refund_method(rp.refund_method),
            "restocking_fee": rp.restocking_fee,
            "shipping": _format_shipping_responsibility(
                rp.shipping_responsibility, rp.free_return_label
            ),
            "excluded_categories": rp.excluded_categories,
            "source_url": str(policy.source_url) if policy.source_url else None,
            "last_verified": (
                policy.last_verified.isoformat() if policy.last_verified else None
            ),
            "needs_verification": policy.needs_verification,
        },
    }


def get_exchange_policy(
    merchant_name: str | None = None,
    merchant_domain: str | None = None,
    country_code: str = "US",
) -> dict:
    """
    Get exchange policy details for a merchant.

    Use this to answer questions about item exchanges, exchange windows,
    allowed exchange types, and conditions.

    Args:
        merchant_name: The merchant's name (e.g., "Nike", "Amazon").
        merchant_domain: The merchant's website domain (e.g., "nike.com").
        country_code: Country code (default "US").

    Returns:
        dict: Exchange policy details or error/not_found status.
    """
    if not merchant_name and not merchant_domain:
        return {
            "status": "error",
            "message": "Please provide a merchant name or domain to look up the policy.",
        }

    with UnitOfWork() as uow:
        # Look up merchant
        merchant = uow.merchants.get_by_name_or_domain(
            name=merchant_name, domain=merchant_domain
        )
        if merchant is None:
            query = merchant_name or merchant_domain
            return {
                "status": "not_found",
                "message": f"Merchant '{query}' not found in our database.",
            }

        # Look up exchange policy
        policy = uow.policies.get_exchange_policy_by_merchant(
            merchant_id=merchant.id,
            country_code=country_code,
        )

    if policy is None:
        return {
            "status": "not_found",
            "message": f"No exchange policy data available for {merchant.name}.",
        }

    # Extract exchange policy details
    if policy.exchange_policy is None:
        return {
            "status": "not_found",
            "message": f"Exchange policy data is incomplete for {merchant.name}.",
        }

    ep = policy.exchange_policy

    return {
        "status": "success",
        "merchant": merchant.name,
        "policy_type": "exchange",
        "country": country_code,
        "details": {
            "allowed": ep.allowed,
            "window_days": ep.window_days,
            "exchange_types": _format_exchange_types(ep.exchange_types),
            "conditions": [_format_return_condition(c) for c in ep.conditions],
            "shipping": _format_shipping_responsibility(
                ep.shipping_responsibility, ep.free_exchange_label
            ),
            "price_difference_handling": ep.price_difference_handling,
            "excluded_categories": ep.excluded_categories,
            "source_url": str(policy.source_url) if policy.source_url else None,
            "last_verified": (
                policy.last_verified.isoformat() if policy.last_verified else None
            ),
            "needs_verification": policy.needs_verification,
        },
    }


def get_policy_for_order(
    user_id: str,
    order_id: str,
) -> dict:
    """
    Get applicable return and exchange policies for a specific order.

    Use this when the user asks about policy for a specific order they placed.
    Automatically looks up the merchant and country for the order.

    Args:
        user_id: The user's unique identifier.
        order_id: The order's unique identifier.

    Returns:
        dict: Order context with applicable return and exchange policies.
    """
    with UnitOfWork() as uow:
        # Look up order
        order = uow.orders.get_by_id_for_user(order_id, user_id)
        if order is None:
            return {
                "status": "not_found",
                "message": f"Order '{order_id}' not found.",
            }

        # Get country code from order (default to US if not set)
        country_code = "US"  # TODO: Add country_code field to Order model

        # Look up both policies
        return_policy = uow.policies.get_return_policy_by_merchant(
            merchant_id=order.merchant.id,
            country_code=country_code,
        )
        exchange_policy = uow.policies.get_exchange_policy_by_merchant(
            merchant_id=order.merchant.id,
            country_code=country_code,
        )

    # Build order context
    order_context = {
        "order_number": order.order_number,
        "merchant": order.merchant.name,
        "order_date": order.order_date.isoformat() if order.order_date else None,
        "delivered_date": None,  # TODO: Extract from shipments
    }

    # Build return policy details with deadline calculation
    return_policy_details = None
    if return_policy and return_policy.return_policy:
        rp = return_policy.return_policy

        # Calculate deadline and days remaining
        deadline = None
        days_remaining = None
        if order.return_window_end:
            deadline = order.return_window_end.isoformat()
            now = datetime.now(timezone.utc)
            days_remaining = (order.return_window_end - now).days

        return_policy_details = {
            "allowed": rp.allowed,
            "window_days": rp.window_days,
            "deadline": deadline,
            "days_remaining": days_remaining,
            "conditions": [_format_return_condition(c) for c in rp.conditions],
            "refund_method": _format_refund_method(rp.refund_method),
            "restocking_fee": rp.restocking_fee,
            "shipping": _format_shipping_responsibility(
                rp.shipping_responsibility, rp.free_return_label
            ),
            "excluded_categories": rp.excluded_categories,
            "source_url": (
                str(return_policy.source_url) if return_policy.source_url else None
            ),
            "needs_verification": return_policy.needs_verification,
        }

    # Build exchange policy details with deadline calculation
    exchange_policy_details = None
    if exchange_policy and exchange_policy.exchange_policy:
        ep = exchange_policy.exchange_policy

        # Calculate deadline and days remaining
        deadline = None
        days_remaining = None
        if order.exchange_window_end:
            deadline = order.exchange_window_end.isoformat()
            now = datetime.now(timezone.utc)
            days_remaining = (order.exchange_window_end - now).days

        exchange_policy_details = {
            "allowed": ep.allowed,
            "window_days": ep.window_days,
            "deadline": deadline,
            "days_remaining": days_remaining,
            "exchange_types": _format_exchange_types(ep.exchange_types),
            "conditions": [_format_return_condition(c) for c in ep.conditions],
            "shipping": _format_shipping_responsibility(
                ep.shipping_responsibility, ep.free_exchange_label
            ),
            "price_difference_handling": ep.price_difference_handling,
            "excluded_categories": ep.excluded_categories,
            "source_url": (
                str(exchange_policy.source_url) if exchange_policy.source_url else None
            ),
            "needs_verification": exchange_policy.needs_verification,
        }

    return {
        "status": "success",
        "order": order_context,
        "return_policy": return_policy_details,
        "exchange_policy": exchange_policy_details,
    }

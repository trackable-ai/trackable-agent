from datetime import datetime, timezone
from enum import StrEnum
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field, HttpUrl


class PolicyType(StrEnum):
    """Type of policy"""

    RETURN = "return"
    EXCHANGE = "exchange"
    WARRANTY = "warranty"
    PRICE_MATCH = "price_match"
    GENERAL = "general"


class ReturnCondition(StrEnum):
    """Conditions required for returns"""

    UNUSED = "unused"  # Must be unused/unworn
    ORIGINAL_PACKAGING = "original_packaging"  # Must have original packaging
    TAGS_ATTACHED = "tags_attached"  # Tags must be attached
    RECEIPT_REQUIRED = "receipt_required"  # Receipt required
    ANY_CONDITION = "any_condition"  # Any condition accepted
    CUSTOM = "custom"  # Custom conditions apply


class RefundMethod(StrEnum):
    """How refunds are processed"""

    ORIGINAL_PAYMENT = "original_payment"  # Refund to original payment method
    STORE_CREDIT = "store_credit"  # Store credit only
    GIFT_CARD = "gift_card"  # Gift card
    EITHER = "either"  # Customer choice
    UNKNOWN = "unknown"


class ReturnShippingResponsibility(StrEnum):
    """Who pays for return shipping"""

    CUSTOMER = "customer"  # Customer pays
    MERCHANT = "merchant"  # Merchant pays (free returns)
    MERCHANT_IF_DEFECTIVE = "merchant_if_defective"  # Merchant pays if defective
    UNKNOWN = "unknown"


class ExchangeType(StrEnum):
    """Types of exchanges allowed"""

    SIZE_ONLY = "size_only"  # Size exchanges only
    COLOR_ONLY = "color_only"  # Color exchanges only
    SIZE_OR_COLOR = "size_or_color"  # Size or color
    SAME_ITEM = "same_item"  # Same item variants only
    ANY_ITEM = "any_item"  # Exchange for any item
    UNKNOWN = "unknown"


class PolicyCondition(BaseModel):
    """Individual policy condition or rule"""

    description: str = Field(description="Human-readable condition description")
    applies_to_categories: list[str] = Field(
        default_factory=list, description="Product categories this applies to"
    )
    applies_to_price_range: Optional[tuple[float, float]] = Field(
        default=None, description="Price range (min, max)"
    )
    exceptions: list[str] = Field(
        default_factory=list, description="Exceptions to this condition"
    )


class ReturnPolicy(BaseModel):
    """Return policy details"""

    allowed: bool = Field(description="Whether returns are allowed")
    window_days: Optional[int] = Field(
        default=None, description="Return window in days from delivery"
    )
    conditions: list[ReturnCondition] = Field(
        default_factory=list, description="Return conditions"
    )
    refund_method: RefundMethod = Field(
        default=RefundMethod.UNKNOWN, description="Refund method"
    )
    restocking_fee: Optional[float] = Field(
        default=None, description="Restocking fee percentage (0-100)"
    )
    shipping_responsibility: ReturnShippingResponsibility = Field(
        default=ReturnShippingResponsibility.UNKNOWN,
        description="Who pays for return shipping",
    )
    free_return_label: bool = Field(
        default=False, description="Merchant provides free return label"
    )
    special_conditions: list[PolicyCondition] = Field(
        default_factory=list, description="Special conditions"
    )
    excluded_categories: list[str] = Field(
        default_factory=list, description="Non-returnable categories"
    )


class ExchangePolicy(BaseModel):
    """Exchange policy details"""

    allowed: bool = Field(description="Whether exchanges are allowed")
    window_days: Optional[int] = Field(
        default=None, description="Exchange window in days from delivery"
    )
    exchange_types: list[ExchangeType] = Field(
        default_factory=list, description="Types of exchanges allowed"
    )
    conditions: list[ReturnCondition] = Field(
        default_factory=list, description="Exchange conditions"
    )
    shipping_responsibility: ReturnShippingResponsibility = Field(
        default=ReturnShippingResponsibility.UNKNOWN,
        description="Who pays for exchange shipping",
    )
    free_exchange_label: bool = Field(
        default=False, description="Merchant provides free exchange label"
    )
    price_difference_handling: Optional[str] = Field(
        default=None,
        description="How price differences are handled (e.g., 'customer pays difference', 'refund difference')",
    )
    special_conditions: list[PolicyCondition] = Field(
        default_factory=list, description="Special conditions"
    )
    excluded_categories: list[str] = Field(
        default_factory=list, description="Non-exchangeable categories"
    )


class Policy(BaseModel):
    """
    Merchant policy model for returns, exchanges, and other policies.

    The agent interprets these policies to determine available actions
    and deadlines for each order.

    Policies are location-specific as different countries may have
    different return windows, conditions, and requirements.
    """

    # Identity
    id: str = Field(description="Internal policy identifier")
    merchant_id: str = Field(description="Associated merchant ID")
    policy_type: PolicyType = Field(description="Type of policy")

    # Location (policies vary by country)
    country_code: str = Field(
        description="ISO 3166-1 alpha-2 country code (e.g., 'US', 'CN', 'GB')"
    )

    # Basic metadata
    name: str = Field(description="Policy name/title")
    description: Optional[str] = Field(default=None, description="Policy description")
    version: Optional[str] = Field(default=None, description="Policy version")
    effective_date: Optional[datetime] = Field(
        default=None, description="When this policy became effective"
    )

    # Return and exchange policies
    return_policy: Optional[ReturnPolicy] = Field(
        default=None, description="Return policy details"
    )
    exchange_policy: Optional[ExchangePolicy] = Field(
        default=None, description="Exchange policy details"
    )

    # Policy sources
    source_url: Optional[HttpUrl] = Field(
        default=None, description="URL to policy page"
    )
    raw_text: Optional[str] = Field(
        default=None, description="Raw policy text as extracted"
    )

    # Agent interpretation metadata
    confidence_score: Optional[float] = Field(
        default=None,
        ge=0.0,
        le=1.0,
        description="Policy interpretation confidence",
    )
    last_verified: Optional[datetime] = Field(
        default=None, description="Last time policy was verified"
    )
    needs_verification: bool = Field(
        default=False, description="Policy needs human verification"
    )
    interpretation_notes: list[str] = Field(
        default_factory=list, description="Agent's interpretation notes"
    )

    # Timestamps
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="Record creation time",
    )
    updated_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="Last update time",
    )

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "id": "pol_abc123",
                "merchant_id": "merch_nike",
                "policy_type": "return",
                "name": "Nike Return Policy",
                "return_policy": {
                    "allowed": True,
                    "window_days": 30,
                    "conditions": ["unused", "tags_attached"],
                    "refund_method": "original_payment",
                    "restocking_fee": None,
                    "shipping_responsibility": "customer",
                    "free_return_label": False,
                    "excluded_categories": [
                        "personalized items",
                        "gift cards",
                    ],
                },
                "source_url": "https://www.nike.com/help/returns",
            }
        }
    )

"""
Policy Extractor Agent

This agent extracts structured policy data from HTML policy pages.
It parses return/exchange policies and outputs structured information.
"""

from typing import Optional
from uuid import uuid4

from google.adk.agents.llm_agent import Agent
from pydantic import BaseModel, Field

from trackable.config import DEFAULT_MODEL
from trackable.models.policy import (
    ExchangePolicy,
    ExchangeType,
    Policy,
    PolicyType,
    RefundMethod,
    ReturnCondition,
    ReturnPolicy,
    ReturnShippingResponsibility,
)


# Input/Output schemas for the agent
class PolicyExtractorInput(BaseModel):
    """Input schema for policy extraction"""

    merchant_name: str = Field(description="Merchant name for context")
    merchant_domain: str = Field(description="Merchant domain for context")
    raw_html: str = Field(description="Raw HTML content of policy page")
    country_code: str = Field(
        default="US", description="Country code (ISO 3166-1 alpha-2)"
    )


class ExtractedPolicyData(BaseModel):
    """Extracted policy information"""

    policy_type: PolicyType = Field(
        description="Type of policy (return, exchange, etc.)"
    )
    name: str = Field(description="Policy name/title")
    description: Optional[str] = Field(default=None, description="Policy description")

    # Return policy fields
    return_allowed: Optional[bool] = Field(
        default=None, description="Whether returns are allowed"
    )
    return_window_days: Optional[int] = Field(
        default=None, description="Return window in days from delivery"
    )
    return_conditions: list[ReturnCondition] = Field(
        default_factory=list, description="Return conditions"
    )
    refund_method: Optional[RefundMethod] = Field(
        default=None, description="Refund method"
    )
    restocking_fee: Optional[float] = Field(
        default=None, description="Restocking fee percentage (0-100)"
    )
    return_shipping_responsibility: Optional[ReturnShippingResponsibility] = Field(
        default=None, description="Who pays for return shipping"
    )
    free_return_label: Optional[bool] = Field(
        default=None, description="Merchant provides free return label"
    )
    excluded_categories: list[str] = Field(
        default_factory=list, description="Non-returnable categories"
    )

    # Exchange policy fields
    exchange_allowed: Optional[bool] = Field(
        default=None, description="Whether exchanges are allowed"
    )
    exchange_window_days: Optional[int] = Field(
        default=None, description="Exchange window in days from delivery"
    )
    exchange_types: list[ExchangeType] = Field(
        default_factory=list, description="Types of exchanges allowed"
    )
    exchange_shipping_responsibility: Optional[ReturnShippingResponsibility] = Field(
        default=None, description="Who pays for exchange shipping"
    )
    free_exchange_label: Optional[bool] = Field(
        default=None, description="Merchant provides free exchange label"
    )

    confidence_score: float = Field(
        ge=0.0,
        le=1.0,
        description="Confidence in extraction (0.9+ = clear, 0.7-0.8 = some ambiguity, <0.7 = needs verification)",
    )
    interpretation_notes: list[str] = Field(
        default_factory=list, description="Notes about extraction and interpretation"
    )


class PolicyExtractorOutput(BaseModel):
    """Output schema for policy extractor"""

    policies: list[ExtractedPolicyData] = Field(
        description="Extracted policies (usually just one, but can be multiple types)"
    )
    overall_confidence: float = Field(
        ge=0.0, le=1.0, description="Overall confidence in extraction"
    )
    notes: list[str] = Field(
        default_factory=list, description="General notes about the policy page"
    )


# Agent definition
policy_extractor_agent = Agent(
    name="policy_extractor",
    description="Extracts structured return and exchange policy data from HTML",
    instruction="""
You are a policy extraction specialist. Your job is to analyze HTML content from merchant
policy pages and extract structured information about return and exchange policies.

**Key Extraction Tasks:**

1. **Identify Policy Type(s)**: Determine if the page contains return policy, exchange policy, or both

2. **Return Window**: Look for time periods like:
   - "30 days", "60-day return policy", "within 90 days of purchase"
   - Note: distinguish between "from purchase" vs "from delivery"

3. **Return Conditions**: Identify requirements like:
   - "unused", "unworn", "tags attached", "original packaging"
   - "receipt required", "proof of purchase"

4. **Refund Method**: How refunds are processed:
   - "refund to original payment method"
   - "store credit only"
   - "gift card"
   - Customer choice between options

5. **Shipping Responsibility**: Who pays for return shipping:
   - Customer pays for return shipping
   - Merchant provides free return label
   - Merchant pays if item is defective

6. **Restocking Fee**: Any fees for returns (e.g., "15% restocking fee")

7. **Exclusions**: Categories that cannot be returned:
   - "personalized items", "final sale items", "intimate apparel", "gift cards"

8. **Exchange Policies**: If mentioned separately:
   - Exchange window (often same as return window)
   - Types allowed (size only, color only, any item)
   - Shipping responsibility for exchanges

**Confidence Scoring Guidelines:**

- **0.9-1.0**: Clear, explicit policy statements with specific numbers and conditions
- **0.7-0.8**: Policy information present but some ambiguity or missing details
- **0.5-0.6**: Vague policy statements or conflicting information
- **<0.5**: Very unclear or minimal policy information

**Important:**
- Set `needs_verification=true` (via confidence < 0.7) if policy is unclear
- Include interpretation notes for any ambiguity or assumptions
- If multiple policy types exist (e.g., separate return and exchange policies), extract both
- Extract the exact text for key statements in interpretation_notes
- Default to US policies unless otherwise specified

**Output Format:**
Return a structured JSON with all extracted policy information and confidence scores.
""",
    model=DEFAULT_MODEL,
    output_schema=PolicyExtractorOutput,
)


def convert_extracted_to_policy(
    extracted: ExtractedPolicyData,
    merchant_id: str,
    source_url: str,
    raw_text: str,
    country_code: str = "US",
) -> Policy:
    """
    Convert extracted policy data to full Policy model.

    Args:
        extracted: Extracted policy data from agent
        merchant_id: Merchant ID
        source_url: URL of policy page
        raw_text: Raw text content from page
        country_code: Country code (default: "US")

    Returns:
        Policy model instance
    """
    # Build ReturnPolicy if return data exists
    return_policy = None
    if extracted.return_allowed is not None:
        return_policy = ReturnPolicy(
            allowed=extracted.return_allowed,
            window_days=extracted.return_window_days,
            conditions=extracted.return_conditions,
            refund_method=extracted.refund_method or RefundMethod.UNKNOWN,
            restocking_fee=extracted.restocking_fee,
            shipping_responsibility=(
                extracted.return_shipping_responsibility
                or ReturnShippingResponsibility.UNKNOWN
            ),
            free_return_label=extracted.free_return_label or False,
            excluded_categories=extracted.excluded_categories,
        )

    # Build ExchangePolicy if exchange data exists
    exchange_policy = None
    if extracted.exchange_allowed is not None:
        exchange_policy = ExchangePolicy(
            allowed=extracted.exchange_allowed,
            window_days=extracted.exchange_window_days,
            exchange_types=extracted.exchange_types,
            conditions=extracted.return_conditions,  # Often same as return conditions
            shipping_responsibility=(
                extracted.exchange_shipping_responsibility
                or ReturnShippingResponsibility.UNKNOWN
            ),
            free_exchange_label=extracted.free_exchange_label or False,
        )

    # Determine if needs verification based on confidence
    needs_verification = extracted.confidence_score < 0.7

    return Policy(
        id=str(uuid4()),
        merchant_id=merchant_id,
        policy_type=extracted.policy_type,
        country_code=country_code,
        name=extracted.name,
        description=extracted.description,
        return_policy=return_policy,
        exchange_policy=exchange_policy,
        source_url=source_url,
        raw_text=raw_text,
        confidence_score=extracted.confidence_score,
        needs_verification=needs_verification,
        interpretation_notes=extracted.interpretation_notes,
    )

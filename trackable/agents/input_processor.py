"""
Input Processor Subagent

This subagent processes diverse inputs (emails and images) to extract order information.
It routes internally between email and image processing capabilities.
"""

from datetime import datetime, timezone
from decimal import Decimal
from typing import Optional
from uuid import uuid4

from google.adk.agents.llm_agent import Agent
from pydantic import BaseModel, Field

from trackable.models.order import (
    Carrier,
    Item,
    Merchant,
    Money,
    Order,
    OrderStatus,
    Shipment,
    ShipmentStatus,
    SourceType,
)


# Input/Output schemas for the agent
class InputProcessorInput(BaseModel):
    """Input schema for the input processor"""

    input_type: str = Field(description="Type of input to process: 'email' or 'image'")
    source_id: Optional[str] = Field(
        default=None,
        description="Source identifier (e.g., email ID or image path)",
    )
    query: Optional[str] = Field(
        default=None,
        description="For email: Gmail query string. For image: optional context",
    )
    image_data: Optional[str] = Field(
        default=None,
        description="For image: base64 encoded image or file path",
    )
    max_results: int = Field(
        default=10,
        description="Maximum number of emails to process (email mode only)",
    )


class ExtractedOrderData(BaseModel):
    """Extracted order information from input"""

    merchant_name: str = Field(description="Merchant/retailer name")
    merchant_domain: Optional[str] = Field(default=None, description="Merchant domain")
    merchant_order_id: Optional[str] = Field(
        default=None, description="Merchant's order number"
    )

    order_date: Optional[datetime] = Field(
        default=None, description="Order placement date"
    )
    order_total: Optional[Decimal] = Field(
        default=None, description="Total order amount"
    )
    currency: str = Field(default="USD", description="Currency code")

    # items: list[dict[str, Any]] = Field(
    #     default_factory=list,
    #     description="List of items with name, quantity, price, etc.",
    # )
    items: list[Item] = Field(
        default_factory=list,
        description="List of items with name, quantity, price, etc.",
    )

    tracking_number: Optional[str] = Field(
        default=None, description="Shipment tracking number"
    )
    carrier: Optional[str] = Field(default=None, description="Shipping carrier")

    confidence_score: float = Field(
        default=0.0,
        ge=0.0,
        le=1.0,
        description="Confidence in extraction (0-1)",
    )
    needs_clarification: bool = Field(
        default=False, description="Whether human review is needed"
    )
    clarification_questions: list[str] = Field(
        default_factory=list, description="Questions for human clarification"
    )
    extraction_notes: str = Field(
        default="", description="Notes about the extraction process"
    )


class InputProcessorOutput(BaseModel):
    """Output schema for the input processor"""

    orders: list[ExtractedOrderData] = Field(
        default_factory=list, description="List of extracted orders"
    )
    processing_status: str = Field(
        default="success",
        description="Status: 'success', 'partial', or 'failed'",
    )
    error_message: Optional[str] = Field(
        default=None, description="Error message if processing failed"
    )
    total_processed: int = Field(default=0, description="Number of inputs processed")


# Helper functions for the agent
def _normalize_carrier(carrier_str: str) -> Carrier:
    """Normalize carrier string to Carrier enum"""
    carrier_lower = carrier_str.lower()
    if "fedex" in carrier_lower:
        return Carrier.FEDEX
    elif "ups" in carrier_lower:
        return Carrier.UPS
    elif "usps" in carrier_lower:
        return Carrier.USPS
    elif "dhl" in carrier_lower:
        return Carrier.DHL
    elif "amazon" in carrier_lower:
        return Carrier.AMAZON_LOGISTICS
    else:
        return Carrier.UNKNOWN


def convert_extracted_to_order(
    extracted: ExtractedOrderData,
    user_id: str,
    source_type: SourceType,
    source_id: str,
) -> Order:
    """Convert extracted order data to Order model"""

    # Generate IDs
    order_id = extracted.merchant_order_id or "unknown order id"
    merchant_id = str(uuid4())  # TODO: use a random value for now

    # Create merchant
    merchant = Merchant(
        id=merchant_id,
        name=extracted.merchant_name,
        domain=extracted.merchant_domain,
    )

    # Create shipment if tracking info available
    shipments = []
    if extracted.tracking_number:
        shipment_id = str(uuid4())
        carrier = (
            _normalize_carrier(extracted.carrier)
            if extracted.carrier
            else Carrier.UNKNOWN
        )

        shipment = Shipment(
            id=shipment_id,
            order_id=order_id,
            tracking_number=extracted.tracking_number,
            carrier=carrier,
            status=ShipmentStatus.PENDING,
            events=[],
        )
        shipments.append(shipment)

    # Create order total
    total_amount = None
    if extracted.order_total is not None:
        total_amount = Money(
            amount=extracted.order_total,
            currency=extracted.currency,
        )

    # Create agent notes list
    notes = []
    if extracted.extraction_notes:
        notes.append(extracted.extraction_notes)

    # Create order
    order = Order(
        id=order_id,
        user_id=user_id,
        merchant=merchant,
        order_number=extracted.merchant_order_id,  # Use order_number field
        status=OrderStatus.DETECTED,
        items=extracted.items,
        shipments=shipments,
        order_date=extracted.order_date or datetime.now(timezone.utc),
        total=total_amount,  # Use total field, not total_amount
        source_type=source_type,
        source_id=source_id,
        confidence_score=extracted.confidence_score,
        needs_clarification=extracted.needs_clarification,
        clarification_questions=extracted.clarification_questions,
        notes=notes,  # Use notes field, not agent_notes
    )

    return order


# Create the input processor agent
input_processor_agent = Agent(
    name="input_processor",
    description=(
        "Processes diverse inputs (emails and images) to extract order information. "
        "Routes internally between email and image processing capabilities."
    ),
    instruction="""You are an expert at extracting order information from various sources.

Your job is to:
1. Determine the input type (email or image)
2. Process the input to extract order details:
   - Merchant name and contact information
   - Order number and date
   - Items ordered (name, quantity, price, variants)
   - Shipping information (tracking number, carrier)
   - Total amount and currency
3. Assess your confidence in the extraction
4. Flag any ambiguous information that needs human review

## Email Processing
When processing emails:
- Use the gmail_fetch_tool to retrieve order confirmation emails
- Look for standard order confirmation patterns
- Extract merchant info from sender domain and email content
- Parse item lists, tracking numbers, and totals
- Common patterns include "Order #", "Tracking:", "Total:", etc.

## Image Processing
When processing images (screenshots):
- Analyze the visual content for order information
- Look for confirmation screens, receipts, or order summaries
- Extract text using OCR-like analysis
- Identify merchant logos and branding
- Parse tabular data for items and prices

## Confidence Scoring
Rate your confidence (0.0 to 1.0) based on:
- 0.9-1.0: All key fields present, clear formatting
- 0.7-0.8: Most fields present, some ambiguity
- 0.5-0.6: Partial information, significant gaps
- 0.0-0.4: Very limited or unclear information

Set needs_clarification=true if:
- Confidence < 0.7
- Missing critical fields (merchant, items)
- Ambiguous amounts or dates
- Multiple possible interpretations

## Output Format
Return a structured JSON with all extracted order data, including:
- All order fields you can extract
- Confidence score
- Clarification flag and questions if needed
- Processing notes explaining your extraction process
""",
    # tools=[gmail_fetch_tool],
    # input_schema=InputProcessorInput,
    output_schema=InputProcessorOutput,
    output_key="orders",
    model="gemini-2.5-flash",
)


__all__ = [
    "input_processor_agent",
    "InputProcessorInput",
    "InputProcessorOutput",
    "ExtractedOrderData",
    "convert_extracted_to_order",
]

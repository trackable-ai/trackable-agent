from datetime import datetime, timezone
from decimal import Decimal
from enum import StrEnum
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field, HttpUrl


class OrderStatus(StrEnum):
    """Order lifecycle status"""

    DETECTED = "detected"  # Order discovered from email/image
    CONFIRMED = "confirmed"  # Order confirmation received
    SHIPPED = "shipped"  # Shipment initiated
    IN_TRANSIT = "in_transit"  # Package in transit
    DELIVERED = "delivered"  # Package delivered
    RETURNED = "returned"  # Return initiated
    REFUNDED = "refunded"  # Refund processed
    CANCELLED = "cancelled"  # Order cancelled
    UNKNOWN = "unknown"  # Status unclear


class ShipmentStatus(StrEnum):
    """Shipment tracking status"""

    PENDING = "pending"  # Awaiting shipment
    LABEL_CREATED = "label_created"  # Shipping label created
    IN_TRANSIT = "in_transit"  # Package in transit
    OUT_FOR_DELIVERY = "out_for_delivery"  # Out for delivery
    DELIVERED = "delivered"  # Package delivered
    DELIVERY_ATTEMPTED = "delivery_attempted"  # Delivery attempted
    EXCEPTION = "exception"  # Shipping exception
    RETURNED_TO_SENDER = "returned_to_sender"  # Returned to sender
    UNKNOWN = "unknown"  # Status unclear


class Carrier(StrEnum):
    """Supported shipping carriers"""

    USPS = "usps"
    UPS = "ups"
    FEDEX = "fedex"
    DHL = "dhl"
    AMAZON_LOGISTICS = "amazon_logistics"
    OTHER = "other"
    UNKNOWN = "unknown"


class ItemCondition(StrEnum):
    """Item condition for returns"""

    NEW = "new"
    OPENED = "opened"
    USED = "used"
    DAMAGED = "damaged"
    UNKNOWN = "unknown"


class Money(BaseModel):
    """Money amount with currency"""

    amount: Decimal = Field(description="Amount in the currency's smallest unit")
    currency: str = Field(default="USD", description="ISO 4217 currency code")

    def __str__(self) -> str:
        return f"{self.currency} {self.amount:.2f}"


class Merchant(BaseModel):
    """Merchant/retailer information"""

    id: str = Field(description="Internal merchant identifier")
    name: str = Field(description="Merchant display name")
    domain: Optional[str] = Field(default=None, description="Merchant domain")
    support_email: Optional[str] = Field(default=None, description="Support email")
    support_url: Optional[HttpUrl] = Field(default=None, description="Support URL")
    return_portal_url: Optional[HttpUrl] = Field(
        default=None, description="Return portal URL"
    )


class Item(BaseModel):
    """Individual item in an order"""

    id: str = Field(description="Internal item identifier")
    order_id: str = Field(description="Parent order ID")
    name: str = Field(description="Item name/title")
    description: Optional[str] = Field(default=None, description="Item description")
    quantity: int = Field(default=1, description="Quantity ordered")
    price: Optional[Money] = Field(default=None, description="Item price")
    sku: Optional[str] = Field(default=None, description="Stock keeping unit")
    size: Optional[str] = Field(default=None, description="Size variant")
    color: Optional[str] = Field(default=None, description="Color variant")
    condition: ItemCondition = Field(
        default=ItemCondition.NEW, description="Item condition"
    )
    image_url: Optional[HttpUrl] = Field(default=None, description="Product image URL")

    # Return/exchange tracking
    is_returnable: Optional[bool] = Field(
        default=None, description="Whether item can be returned"
    )
    is_exchangeable: Optional[bool] = Field(
        default=None, description="Whether item can be exchanged"
    )
    return_requested: bool = Field(
        default=False, description="Return has been requested"
    )
    exchange_requested: bool = Field(
        default=False, description="Exchange has been requested"
    )


class TrackingEvent(BaseModel):
    """Individual tracking event"""

    timestamp: datetime = Field(description="Event timestamp")
    status: ShipmentStatus = Field(description="Shipment status")
    location: Optional[str] = Field(default=None, description="Event location")
    description: Optional[str] = Field(default=None, description="Event description")


class Shipment(BaseModel):
    """Shipment tracking information"""

    id: str = Field(description="Internal shipment identifier")
    order_id: str = Field(description="Parent order ID")
    tracking_number: Optional[str] = Field(
        default=None, description="Carrier tracking number"
    )
    carrier: Carrier = Field(default=Carrier.UNKNOWN, description="Shipping carrier")
    status: ShipmentStatus = Field(
        default=ShipmentStatus.PENDING, description="Current status"
    )

    # Addresses
    shipping_address: Optional[str] = Field(
        default=None, description="Shipping address"
    )
    return_address: Optional[str] = Field(default=None, description="Return address")

    # Timing
    shipped_at: Optional[datetime] = Field(default=None, description="Ship date")
    estimated_delivery: Optional[datetime] = Field(
        default=None, description="Estimated delivery date"
    )
    delivered_at: Optional[datetime] = Field(
        default=None, description="Actual delivery date"
    )

    # Tracking
    tracking_url: Optional[HttpUrl] = Field(
        default=None, description="Carrier tracking URL"
    )
    events: list[TrackingEvent] = Field(
        default_factory=list, description="Tracking events"
    )
    last_updated: Optional[datetime] = Field(
        default=None, description="Last tracking update"
    )


class SourceType(StrEnum):
    """Source of order information"""

    EMAIL = "email"  # Gmail order confirmation
    SCREENSHOT = "screenshot"  # User-shared screenshot
    PHOTO = "photo"  # User-shared photo
    MANUAL = "manual"  # Manually entered
    API = "api"  # Merchant API


class Order(BaseModel):
    """
    Core order model representing a purchase and its lifecycle.

    This model maintains the agent's awareness of user purchases,
    tracking everything from detection through delivery, returns, and refunds.
    """

    # Identity
    id: str = Field(description="Internal order identifier (UUID)")
    user_id: str = Field(description="User who owns this order")
    merchant: Merchant = Field(description="Merchant information")

    # Order details
    order_number: Optional[str] = Field(
        default=None, description="Merchant order number"
    )
    order_date: Optional[datetime] = Field(
        default=None, description="Order placement date"
    )
    status: OrderStatus = Field(
        default=OrderStatus.DETECTED, description="Order status"
    )
    country_code: Optional[str] = Field(
        default=None,
        description="ISO 3166-1 alpha-2 country code for order location (e.g., 'US', 'CN')",
    )

    # Items and pricing
    items: list[Item] = Field(default_factory=list, description="Order items")
    subtotal: Optional[Money] = Field(default=None, description="Subtotal amount")
    tax: Optional[Money] = Field(default=None, description="Tax amount")
    shipping_cost: Optional[Money] = Field(default=None, description="Shipping cost")
    total: Optional[Money] = Field(default=None, description="Total amount")

    # Shipment tracking
    shipments: list[Shipment] = Field(
        default_factory=list, description="Shipment information"
    )

    # Return/exchange window tracking
    return_window_start: Optional[datetime] = Field(
        default=None, description="Return window start (usually delivery date)"
    )
    return_window_end: Optional[datetime] = Field(
        default=None, description="Return window end date"
    )
    return_window_days: Optional[int] = Field(
        default=None, description="Return window duration in days"
    )
    exchange_window_end: Optional[datetime] = Field(
        default=None, description="Exchange window end date"
    )
    is_monitored: bool = Field(
        default=True, description="Whether user is actively monitoring this order"
    )

    # Agent awareness metadata
    source_type: SourceType = Field(description="How this order was discovered")
    source_id: Optional[str] = Field(
        default=None,
        description="Source identifier (email ID, file path, etc.)",
    )
    confidence_score: Optional[float] = Field(
        default=None, ge=0.0, le=1.0, description="Extraction confidence"
    )
    needs_clarification: bool = Field(
        default=False, description="Agent needs user clarification"
    )
    clarification_questions: list[str] = Field(
        default_factory=list, description="Questions for user"
    )

    # URLs
    order_url: Optional[HttpUrl] = Field(default=None, description="Order details URL")
    receipt_url: Optional[HttpUrl] = Field(default=None, description="Receipt URL")

    # Refund tracking
    refund_initiated: bool = Field(
        default=False, description="Refund has been initiated"
    )
    refund_amount: Optional[Money] = Field(default=None, description="Refund amount")
    refund_completed_at: Optional[datetime] = Field(
        default=None, description="Refund completion date"
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

    # Notes and agent reasoning
    notes: list[str] = Field(
        default_factory=list, description="Agent observations and notes"
    )
    last_agent_intervention: Optional[datetime] = Field(
        default=None, description="Last time agent intervened"
    )

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "id": "ord_abc123",
                "user_id": "usr_xyz789",
                "merchant": {
                    "id": "merch_nike",
                    "name": "Nike",
                    "domain": "nike.com",
                    "support_email": "support@nike.com",
                },
                "order_number": "NKE-2024-001234",
                "order_date": "2024-01-15T10:30:00Z",
                "status": "delivered",
                "items": [
                    {
                        "id": "item_1",
                        "order_id": "ord_abc123",
                        "name": "Air Max 90",
                        "quantity": 1,
                        "price": {"amount": "120.00", "currency": "USD"},
                        "size": "10",
                        "color": "Black",
                    }
                ],
                "total": {"amount": "132.50", "currency": "USD"},
                "return_window_end": "2024-02-12T23:59:59Z",
                "source_type": "email",
            }
        }
    )


# API Request/Response Models


class OrderListResponse(BaseModel):
    """Response for listing orders with pagination."""

    orders: list[Order] = Field(description="List of orders")
    total: int = Field(description="Total number of orders matching the query")
    limit: int = Field(description="Maximum number of orders returned")
    offset: int = Field(description="Number of orders skipped")


class OrderUpdateRequest(BaseModel):
    """Request body for updating an order."""

    status: Optional[OrderStatus] = Field(default=None, description="New order status")
    note: Optional[str] = Field(default=None, description="Note to append to the order")
    is_monitored: Optional[bool] = Field(
        default=None, description="Whether to monitor this order"
    )

"""
Trackable data models.

This package contains all Pydantic models for the Trackable Personal Shopping Agent.
"""

# Intervention models
from trackable.models.intervention import (
    ActionType,
    Intervention,
    InterventionPriority,
    InterventionStatus,
    InterventionType,
    RecommendedAction,
)

# Order models
from trackable.models.order import (
    Carrier,
    Item,
    ItemCondition,
    Merchant,
    Money,
    Order,
    OrderStatus,
    Shipment,
    ShipmentStatus,
    SourceType,
    TrackingEvent,
)

# Policy models
from trackable.models.policy import (
    ExchangePolicy,
    ExchangeType,
    Policy,
    PolicyCondition,
    PolicyType,
    RefundMethod,
    ReturnCondition,
    ReturnPolicy,
    ReturnShippingResponsibility,
)

# User models
from trackable.models.user import (
    GmailConnection,
    NotificationPreference,
    ReminderSensitivity,
    User,
    UserPreferences,
    UserStatus,
)

__all__ = [
    # Order models
    "Carrier",
    "Item",
    "ItemCondition",
    "Merchant",
    "Money",
    "Order",
    "OrderStatus",
    "Shipment",
    "ShipmentStatus",
    "SourceType",
    "TrackingEvent",
    # Policy models
    "ExchangePolicy",
    "ExchangeType",
    "Policy",
    "PolicyCondition",
    "PolicyType",
    "RefundMethod",
    "ReturnCondition",
    "ReturnPolicy",
    "ReturnShippingResponsibility",
    # User models
    "GmailConnection",
    "NotificationPreference",
    "ReminderSensitivity",
    "User",
    "UserPreferences",
    "UserStatus",
    # Intervention models
    "ActionType",
    "Intervention",
    "InterventionPriority",
    "InterventionStatus",
    "InterventionType",
    "RecommendedAction",
]

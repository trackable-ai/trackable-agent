"""
Email filtering utilities for ingress service.
"""

import logging
import re
from typing import NamedTuple

logger = logging.getLogger(__name__)

# List of known merchant domains (whitelist)
# In production, this would likely be a database table or external config
KNOWN_MERCHANTS = {
    "amazon.com",
    "amazon.co.uk",
    "amazon.de",
    "amazon.fr",
    "amazon.it",
    "amazon.es",
    "amazon.ca",
    "amazon.co.jp",
    "nike.com",
    "apple.com",
    "walmart.com",
    "target.com",
    "bestbuy.com",
    "ebay.com",
    "shopify.com",
    "stripe.com",
    "paypal.com",
    "fedex.com",
    "ups.com",
    "usps.com",
    "dhl.com",
}

# Regex patterns for order-related subject lines
ORDER_SUBJECT_PATTERNS = [
    r"order\s*#?[:\s]*\d+",
    r"order\s*confirmation",
    r"receipt",
    r"invoice",
    r"shipping\s*confirmation",
    r"shipment",
    r"package\s*track",
    r"delivery",
    r"delivered",
    r"tracking",
    r"return",
    r"refund",
    r"exchange",
    r"purchase",
    r"thank\s*you\s*for\s*your\s*order",
    r"your\s*order\s*is",
]

# Regex patterns to exclude (marketing, newsletters)
EXCLUDE_SUBJECT_PATTERNS = [
    r"newsletter",
    r"subscribe",
    r"unsubscribe",
    r"sale",
    r"discount",
    r"% off",
    r"deals?",
    r"promotion",
    r"recommendation",
    r"review",
    r"survey",
    r"feedback",
    r"cart",
    r"waiting",
    r"miss\s*you",
]


class FilterResult(NamedTuple):
    """Result of email filtering check."""
    should_process: bool
    reason: str


def should_process_email(
    subject: str | None,
    sender: str | None,
    content: str | None = None,
) -> FilterResult:
    """
    Determine if an email should be processed based on metadata.

    Args:
        subject: Email subject line
        sender: Sender email address or name
        content: Email body content (optional, for future deep inspection)

    Returns:
        FilterResult: (should_process, reason)
    """
    if not subject:
        return FilterResult(False, "Missing subject")

    subject_lower = subject.lower()
    
    # 1. Check exclusion patterns first (fast fail)
    for pattern in EXCLUDE_SUBJECT_PATTERNS:
        if re.search(pattern, subject_lower):
            return FilterResult(False, f"Subject matches exclusion pattern: {pattern}")

    # 2. Check for order-related keywords in subject
    has_order_keyword = False
    for pattern in ORDER_SUBJECT_PATTERNS:
        if re.search(pattern, subject_lower):
            has_order_keyword = True
            break
            
    if not has_order_keyword:
        # If subject is generic, maybe check sender?
        # For now, strict subject matching
        return FilterResult(False, "Subject does not match order patterns")

    # 3. Check sender domain (optional whitelist)
    # This is looser - we often want to discover new merchants.
    # But if provided, we can log it or use it for scoring.
    # For now, we don't strictly block unknown senders, but we could.
    
    return FilterResult(True, "Matched order criteria")

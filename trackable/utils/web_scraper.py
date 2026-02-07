"""
Web scraping utilities for policy page fetching.

Simple HTTP fetching with BeautifulSoup for policy page extraction.
"""

import requests
from bs4 import BeautifulSoup


def fetch_policy_page(url: str, timeout: int = 10) -> tuple[str, str]:
    """
    Fetch HTML from policy URL and extract clean text.

    Args:
        url: Policy page URL to fetch
        timeout: Request timeout in seconds (default: 10)

    Returns:
        Tuple of (raw_html, clean_text)
        - raw_html: Complete HTML response
        - clean_text: Cleaned text with scripts/styles/navigation removed

    Raises:
        requests.RequestException: On network/HTTP errors
    """
    # Use realistic browser User-Agent to avoid being blocked
    headers = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
        "Accept-Encoding": "gzip, deflate, br",
        "DNT": "1",
        "Connection": "keep-alive",
        "Upgrade-Insecure-Requests": "1",
    }

    response = requests.get(url, headers=headers, timeout=timeout)
    response.raise_for_status()  # Raise for 4xx/5xx errors

    raw_html = response.text

    # Parse with BeautifulSoup and clean
    soup = BeautifulSoup(raw_html, "html.parser")

    # Remove unwanted elements
    for tag in soup.find_all(["script", "style", "nav", "footer", "header"]):
        tag.decompose()

    # Extract clean text
    clean_text = soup.get_text(separator="\n", strip=True)

    return raw_html, clean_text


def discover_policy_url(domain: str, support_url: str | None = None) -> list[str]:
    """
    Generate candidate policy URLs for a merchant domain.

    Returns URLs in priority order. If support_url is provided, it takes priority.

    Args:
        domain: Merchant domain (e.g., "nike.com")
        support_url: Optional known support/policy URL from merchant record

    Returns:
        List of candidate URLs in priority order
    """
    candidates = []

    # Priority 1: Known support URL from merchant record
    if support_url:
        candidates.append(support_url)

    # Ensure domain has protocol
    if not domain.startswith("http"):
        domain = f"https://{domain}"

    # Priority 2: Common policy URL patterns
    common_paths = [
        "/returns",
        "/return-policy",
        "/help/returns",
        "/customer-service/returns",
        "/policies/return-policy",
        "/support/returns",
        "/faq/returns",
    ]

    for path in common_paths:
        candidates.append(f"{domain}{path}")

    return candidates

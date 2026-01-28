"""
Merchant name normalization and matching utilities.

Provides functions to normalize merchant names and match them to canonical forms.
"""

import re
from urllib.parse import urlparse

# Known merchant canonical names mapped from common variations
# Keys are lowercase variations, values are canonical names
KNOWN_MERCHANTS: dict[str, str] = {
    # Amazon
    "amazon": "Amazon",
    "amazon.com": "Amazon",
    "amazon.co.uk": "Amazon UK",
    "amazon.ca": "Amazon Canada",
    "amazon.de": "Amazon Germany",
    "amazon.co.jp": "Amazon Japan",
    "amzn": "Amazon",
    # Apple
    "apple": "Apple",
    "apple.com": "Apple",
    "apple store": "Apple",
    # Nike
    "nike": "Nike",
    "nike.com": "Nike",
    "nike store": "Nike",
    # Adidas
    "adidas": "Adidas",
    "adidas.com": "Adidas",
    # Target
    "target": "Target",
    "target.com": "Target",
    # Walmart
    "walmart": "Walmart",
    "walmart.com": "Walmart",
    "wal-mart": "Walmart",
    # Best Buy
    "best buy": "Best Buy",
    "bestbuy": "Best Buy",
    "bestbuy.com": "Best Buy",
    # Home Depot
    "home depot": "Home Depot",
    "homedepot": "Home Depot",
    "homedepot.com": "Home Depot",
    "the home depot": "Home Depot",
    # Lowe's
    "lowes": "Lowe's",
    "lowe's": "Lowe's",
    "lowes.com": "Lowe's",
    # Costco
    "costco": "Costco",
    "costco.com": "Costco",
    "costco wholesale": "Costco",
    # Etsy
    "etsy": "Etsy",
    "etsy.com": "Etsy",
    # eBay
    "ebay": "eBay",
    "ebay.com": "eBay",
    # Nordstrom
    "nordstrom": "Nordstrom",
    "nordstrom.com": "Nordstrom",
    # Macy's
    "macys": "Macy's",
    "macy's": "Macy's",
    "macys.com": "Macy's",
    # Sephora
    "sephora": "Sephora",
    "sephora.com": "Sephora",
    # Ulta
    "ulta": "Ulta Beauty",
    "ulta beauty": "Ulta Beauty",
    "ulta.com": "Ulta Beauty",
    # Zara
    "zara": "Zara",
    "zara.com": "Zara",
    # H&M
    "h&m": "H&M",
    "hm": "H&M",
    "hm.com": "H&M",
    # Uniqlo
    "uniqlo": "Uniqlo",
    "uniqlo.com": "Uniqlo",
    # Gap
    "gap": "Gap",
    "gap.com": "Gap",
    # Old Navy
    "old navy": "Old Navy",
    "oldnavy": "Old Navy",
    "oldnavy.com": "Old Navy",
    # Banana Republic
    "banana republic": "Banana Republic",
    "bananarepublic": "Banana Republic",
    "bananarepublic.com": "Banana Republic",
    # REI
    "rei": "REI",
    "rei.com": "REI",
    # Patagonia
    "patagonia": "Patagonia",
    "patagonia.com": "Patagonia",
    # Wayfair
    "wayfair": "Wayfair",
    "wayfair.com": "Wayfair",
    # IKEA
    "ikea": "IKEA",
    "ikea.com": "IKEA",
    # Chewy
    "chewy": "Chewy",
    "chewy.com": "Chewy",
    # PetSmart
    "petsmart": "PetSmart",
    "petsmart.com": "PetSmart",
    # Newegg
    "newegg": "Newegg",
    "newegg.com": "Newegg",
    # B&H Photo
    "b&h": "B&H Photo",
    "b&h photo": "B&H Photo",
    "bhphoto": "B&H Photo",
    "bhphotovideo.com": "B&H Photo",
}

# Common suffixes to remove during normalization
DOMAIN_SUFFIXES = [
    ".com",
    ".co.uk",
    ".ca",
    ".de",
    ".fr",
    ".jp",
    ".co.jp",
    ".cn",
    ".au",
    ".in",
    ".net",
    ".org",
    ".io",
    ".store",
    ".shop",
]

# Common prefixes to remove
COMMON_PREFIXES = ["www.", "shop.", "store.", "order.", "orders."]


def normalize_domain(domain: str | None) -> str | None:
    """
    Normalize a domain to its canonical form.

    Removes common prefixes like 'www.' and converts to lowercase.

    Args:
        domain: Domain to normalize (e.g., "www.Amazon.com")

    Returns:
        Normalized domain (e.g., "amazon.com") or None if input is None
    """
    if not domain:
        return None

    domain = domain.lower().strip()

    # Remove common prefixes
    for prefix in COMMON_PREFIXES:
        if domain.startswith(prefix):
            domain = domain[len(prefix) :]
            break

    return domain


def extract_domain_from_url(url: str) -> str | None:
    """
    Extract and normalize domain from a URL.

    Args:
        url: Full URL (e.g., "https://www.amazon.com/order/123")

    Returns:
        Normalized domain (e.g., "amazon.com") or None
    """
    try:
        parsed = urlparse(url)
        if parsed.netloc:
            return normalize_domain(parsed.netloc)
        return None
    except Exception:
        return None


def normalize_merchant_name(name: str, domain: str | None = None) -> str:
    """
    Normalize a merchant name to its canonical form.

    Applies the following transformations:
    1. Checks known merchant mappings (case-insensitive)
    2. Checks domain-based mappings if domain is provided
    3. Falls back to title case with cleaned-up formatting

    Args:
        name: Raw merchant name (e.g., "AMAZON", "amazon.com", "Amazon Inc.")
        domain: Optional merchant domain for additional context

    Returns:
        Normalized merchant name (e.g., "Amazon")

    Examples:
        >>> normalize_merchant_name("AMAZON")
        'Amazon'
        >>> normalize_merchant_name("amazon.com")
        'Amazon'
        >>> normalize_merchant_name("Some New Store", "somenewstore.com")
        'Some New Store'
    """
    if not name:
        return name

    # Clean up the name
    cleaned_name = name.strip()
    lookup_key = cleaned_name.lower()

    # Try exact match in known merchants
    if lookup_key in KNOWN_MERCHANTS:
        return KNOWN_MERCHANTS[lookup_key]

    # Try domain match if domain is provided
    if domain:
        normalized_domain = normalize_domain(domain)
        if normalized_domain and normalized_domain in KNOWN_MERCHANTS:
            return KNOWN_MERCHANTS[normalized_domain]

    # Try extracting domain from name if it looks like a URL/domain
    if "." in lookup_key:
        # Check if the name itself is a domain
        name_as_domain = normalize_domain(lookup_key)
        if name_as_domain and name_as_domain in KNOWN_MERCHANTS:
            return KNOWN_MERCHANTS[name_as_domain]

        # Remove domain suffix and try again
        for suffix in DOMAIN_SUFFIXES:
            if lookup_key.endswith(suffix):
                base_name = lookup_key[: -len(suffix)]
                if base_name in KNOWN_MERCHANTS:
                    return KNOWN_MERCHANTS[base_name]
                break

    # Remove common corporate suffixes
    corporate_suffixes = [
        ", inc.",
        ", inc",
        " inc.",
        " inc",
        ", llc",
        " llc",
        ", ltd",
        " ltd",
        " co.",
        " co",
        ", corp",
        " corp",
    ]
    for suffix in corporate_suffixes:
        if lookup_key.endswith(suffix):
            cleaned_name = cleaned_name[: -len(suffix)].strip()
            lookup_key = cleaned_name.lower()
            # Check again after removing suffix
            if lookup_key in KNOWN_MERCHANTS:
                return KNOWN_MERCHANTS[lookup_key]
            break

    # Fall back to title case with proper handling
    return _title_case_merchant(cleaned_name)


def _title_case_merchant(name: str) -> str:
    """
    Apply proper title case to a merchant name.

    Handles special cases like acronyms and brand-specific casing.

    Args:
        name: Merchant name to convert

    Returns:
        Properly cased merchant name
    """
    # Already properly cased? Return as-is (mixed case that's not all upper/lower)
    if not name.isupper() and not name.islower():
        # Check if it looks intentionally cased (has uppercase in middle)
        has_mid_caps = any(c.isupper() for c in name[1:] if c.isalpha())
        if has_mid_caps:
            return name

    # Split on whitespace and hyphens, preserving delimiters
    words = re.split(r"(\s+|-)", name)
    result = []

    # Known acronyms to preserve
    known_acronyms = {"rei", "ikea", "h&m", "dhl", "ups", "usps", "bh"}

    for word in words:
        if not word or word.isspace() or word == "-":
            result.append(word)
            continue

        word_lower = word.lower()

        # Preserve known acronyms
        if word_lower in known_acronyms:
            result.append(word.upper())
        # Handle short all-caps words that look like acronyms (2-3 letters only)
        elif word.isupper() and 2 <= len(word) <= 3:
            result.append(word)
        else:
            # Standard title case
            result.append(word.capitalize())

    return "".join(result)


def generate_merchant_aliases(name: str, domain: str | None = None) -> list[str]:
    """
    Generate possible aliases/variations for a merchant.

    Creates a list of alternate names that might be used to refer
    to the same merchant, useful for fuzzy matching.

    Args:
        name: Canonical merchant name
        domain: Optional merchant domain

    Returns:
        List of lowercase aliases (including the canonical name)
    """
    aliases: set[str] = set()

    # Add lowercase canonical name
    canonical_lower = name.lower()
    aliases.add(canonical_lower)

    # Add version without spaces
    aliases.add(canonical_lower.replace(" ", ""))

    # Add version with hyphens instead of spaces
    aliases.add(canonical_lower.replace(" ", "-"))

    # Add domain if provided
    if domain:
        normalized_domain = normalize_domain(domain)
        if normalized_domain:
            aliases.add(normalized_domain)

            # Add domain without TLD
            for suffix in DOMAIN_SUFFIXES:
                if normalized_domain.endswith(suffix):
                    aliases.add(normalized_domain[: -len(suffix)])
                    break

    # Add special handling for names with punctuation
    # Remove apostrophes (Macy's -> macys)
    if "'" in canonical_lower:
        aliases.add(canonical_lower.replace("'", ""))

    # Remove ampersands and replace with 'and'
    if "&" in canonical_lower:
        aliases.add(canonical_lower.replace("&", "and"))
        aliases.add(canonical_lower.replace("&", ""))
        aliases.add(canonical_lower.replace(" & ", " "))

    return sorted(aliases)


def match_merchant_by_alias(
    query: str, aliases_map: dict[str, list[str]]
) -> str | None:
    """
    Find a merchant ID by searching through aliases.

    Args:
        query: Name or alias to search for
        aliases_map: Dictionary mapping merchant IDs to their aliases

    Returns:
        Merchant ID if found, None otherwise
    """
    query_lower = query.lower().strip()

    for merchant_id, aliases in aliases_map.items():
        if query_lower in aliases:
            return merchant_id

    return None

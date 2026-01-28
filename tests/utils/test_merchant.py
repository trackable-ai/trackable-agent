"""
Tests for merchant name normalization and matching utilities.
"""

import pytest

from trackable.utils.merchant import (
    extract_domain_from_url,
    generate_merchant_aliases,
    normalize_domain,
    normalize_merchant_name,
)


class TestNormalizeDomain:
    """Tests for normalize_domain function."""

    def test_none_input(self):
        assert normalize_domain(None) is None

    def test_empty_string(self):
        assert normalize_domain("") is None

    def test_simple_domain(self):
        assert normalize_domain("amazon.com") == "amazon.com"

    def test_uppercase_domain(self):
        assert normalize_domain("AMAZON.COM") == "amazon.com"

    def test_www_prefix(self):
        assert normalize_domain("www.amazon.com") == "amazon.com"

    def test_shop_prefix(self):
        assert normalize_domain("shop.nike.com") == "nike.com"

    def test_store_prefix(self):
        assert normalize_domain("store.apple.com") == "apple.com"

    def test_whitespace(self):
        assert normalize_domain("  amazon.com  ") == "amazon.com"

    def test_mixed_case_with_prefix(self):
        assert normalize_domain("WWW.Amazon.COM") == "amazon.com"


class TestExtractDomainFromUrl:
    """Tests for extract_domain_from_url function."""

    def test_simple_url(self):
        assert extract_domain_from_url("https://amazon.com") == "amazon.com"

    def test_url_with_path(self):
        assert (
            extract_domain_from_url("https://www.amazon.com/order/123") == "amazon.com"
        )

    def test_url_with_www(self):
        assert extract_domain_from_url("https://www.nike.com/products") == "nike.com"

    def test_http_url(self):
        assert extract_domain_from_url("http://target.com/cart") == "target.com"

    def test_invalid_url(self):
        assert extract_domain_from_url("not-a-url") is None

    def test_empty_url(self):
        assert extract_domain_from_url("") is None


class TestNormalizeMerchantName:
    """Tests for normalize_merchant_name function."""

    def test_known_merchant_uppercase(self):
        """Known merchants should be normalized to canonical form."""
        assert normalize_merchant_name("AMAZON") == "Amazon"

    def test_known_merchant_lowercase(self):
        assert normalize_merchant_name("amazon") == "Amazon"

    def test_known_merchant_mixed_case(self):
        assert normalize_merchant_name("AmAzOn") == "Amazon"

    def test_known_merchant_domain_in_name(self):
        """Name that looks like a domain should be normalized."""
        assert normalize_merchant_name("amazon.com") == "Amazon"

    def test_known_merchant_with_domain_context(self):
        """Should use domain context for normalization."""
        assert normalize_merchant_name("Some Store", "amazon.com") == "Amazon"

    def test_known_merchant_nike(self):
        assert normalize_merchant_name("NIKE") == "Nike"

    def test_known_merchant_target(self):
        assert normalize_merchant_name("target") == "Target"

    def test_known_merchant_walmart(self):
        assert normalize_merchant_name("wal-mart") == "Walmart"

    def test_known_merchant_macys(self):
        assert normalize_merchant_name("macys") == "Macy's"

    def test_known_merchant_bestbuy(self):
        assert normalize_merchant_name("bestbuy") == "Best Buy"

    def test_known_merchant_homedepot(self):
        assert normalize_merchant_name("homedepot") == "Home Depot"

    def test_unknown_merchant_title_case(self):
        """Unknown merchants should be title-cased."""
        assert normalize_merchant_name("some random store") == "Some Random Store"

    def test_unknown_merchant_all_caps(self):
        assert normalize_merchant_name("SOME RANDOM STORE") == "Some Random Store"

    def test_corporate_suffix_removal(self):
        """Corporate suffixes like Inc., LLC should be removed."""
        assert normalize_merchant_name("Some Store, Inc.") == "Some Store"

    def test_corporate_suffix_llc(self):
        assert normalize_merchant_name("Another Store LLC") == "Another Store"

    def test_empty_name(self):
        assert normalize_merchant_name("") == ""

    def test_preserves_intentional_casing(self):
        """Names with intentional mid-caps should be preserved."""
        assert normalize_merchant_name("eBay") == "eBay"

    def test_acronym_preservation(self):
        """Short all-caps words should stay as acronyms."""
        result = normalize_merchant_name("REI")
        assert result == "REI"

    def test_ulta_beauty(self):
        assert normalize_merchant_name("ulta") == "Ulta Beauty"


class TestGenerateMerchantAliases:
    """Tests for generate_merchant_aliases function."""

    def test_simple_name(self):
        aliases = generate_merchant_aliases("Nike")
        assert "nike" in aliases

    def test_name_without_spaces(self):
        aliases = generate_merchant_aliases("Best Buy")
        assert "bestbuy" in aliases
        assert "best buy" in aliases

    def test_name_with_hyphens(self):
        aliases = generate_merchant_aliases("Best Buy")
        assert "best-buy" in aliases

    def test_domain_included(self):
        aliases = generate_merchant_aliases("Nike", "nike.com")
        assert "nike.com" in aliases
        assert "nike" in aliases

    def test_domain_without_tld(self):
        aliases = generate_merchant_aliases("Amazon", "amazon.com")
        assert "amazon" in aliases

    def test_apostrophe_handling(self):
        aliases = generate_merchant_aliases("Macy's")
        assert "macy's" in aliases
        assert "macys" in aliases

    def test_ampersand_handling(self):
        aliases = generate_merchant_aliases("H&M")
        assert "h&m" in aliases
        assert "hm" in aliases
        # "handm" is generated by replacing & with nothing
        assert "handm" in aliases

    def test_returns_sorted_list(self):
        aliases = generate_merchant_aliases("Nike", "nike.com")
        assert aliases == sorted(aliases)


class TestIntegration:
    """Integration tests for merchant normalization workflow."""

    def test_normalize_and_generate_aliases(self):
        """Test the full workflow of normalizing and generating aliases."""
        raw_name = "AMAZON.COM"
        domain = "www.amazon.com"

        normalized = normalize_merchant_name(raw_name, domain)
        aliases = generate_merchant_aliases(normalized, domain)

        assert normalized == "Amazon"
        assert "amazon" in aliases
        assert "amazon.com" in aliases

    def test_unknown_merchant_workflow(self):
        """Test workflow for an unknown merchant."""
        raw_name = "my cool store"
        domain = "mycoolstore.com"

        normalized = normalize_merchant_name(raw_name, domain)
        aliases = generate_merchant_aliases(normalized, domain)

        assert normalized == "My Cool Store"
        assert "my cool store" in aliases
        assert "mycoolstore" in aliases
        assert "mycoolstore.com" in aliases

    def test_name_domain_mismatch(self):
        """Test when name doesn't match domain but domain is known."""
        raw_name = "Generic Store Name"
        domain = "nike.com"

        normalized = normalize_merchant_name(raw_name, domain)
        # Should use domain-based normalization since domain is known
        assert normalized == "Nike"

"""
Tests for web scraper utilities.
"""

from unittest.mock import Mock, patch

import pytest
import requests

from trackable.utils.web_scraper import discover_policy_url, fetch_policy_page


def test_discover_policy_url_with_support_url():
    """Test URL discovery with known support URL"""
    urls = discover_policy_url("example.com", "https://example.com/help/returns")

    # Support URL should be first
    assert urls[0] == "https://example.com/help/returns"
    # Common patterns should follow
    assert "https://example.com/returns" in urls
    assert "https://example.com/return-policy" in urls


def test_discover_policy_url_without_support_url():
    """Test URL discovery without support URL"""
    urls = discover_policy_url("nike.com", None)

    # Should start with common patterns
    assert urls[0] == "https://nike.com/returns"
    assert "https://nike.com/return-policy" in urls
    assert "https://nike.com/help/returns" in urls


def test_discover_policy_url_with_protocol():
    """Test URL discovery when domain already has protocol"""
    urls = discover_policy_url("https://example.com", None)

    # Should not duplicate protocol
    assert all(url.startswith("https://") for url in urls)
    assert not any("https://https://" in url for url in urls)


@patch("trackable.utils.web_scraper.requests.get")
def test_fetch_policy_page_success(mock_get):
    """Test successful policy page fetch"""
    mock_response = Mock()
    mock_response.text = """
    <html>
    <head><title>Policy</title></head>
    <body>
        <nav>Menu</nav>
        <main>
            <h1>Return Policy</h1>
            <p>30-day returns</p>
        </main>
        <script>console.log('test');</script>
    </body>
    </html>
    """
    mock_response.raise_for_status = Mock()
    mock_get.return_value = mock_response

    raw_html, clean_text = fetch_policy_page("https://example.com/returns")

    # Should return raw HTML
    assert "<html>" in raw_html
    assert "30-day returns" in raw_html

    # Should clean text (remove nav, script)
    assert "Return Policy" in clean_text
    assert "30-day returns" in clean_text
    assert "Menu" not in clean_text  # nav removed
    assert "console.log" not in clean_text  # script removed


@patch("trackable.utils.web_scraper.requests.get")
def test_fetch_policy_page_http_error(mock_get):
    """Test fetch with HTTP error"""
    mock_get.side_effect = requests.HTTPError("404 Not Found")

    with pytest.raises(requests.HTTPError):
        fetch_policy_page("https://example.com/nonexistent")


@patch("trackable.utils.web_scraper.requests.get")
def test_fetch_policy_page_timeout(mock_get):
    """Test fetch with timeout"""
    mock_get.side_effect = requests.Timeout("Connection timeout")

    with pytest.raises(requests.Timeout):
        fetch_policy_page("https://example.com/slow", timeout=5)


@patch("trackable.utils.web_scraper.requests.get")
def test_fetch_policy_page_user_agent(mock_get):
    """Test that fetch includes User-Agent header"""
    mock_response = Mock()
    mock_response.text = "<html><body>Test</body></html>"
    mock_response.raise_for_status = Mock()
    mock_get.return_value = mock_response

    fetch_policy_page("https://example.com/returns")

    # Verify User-Agent header was set (realistic browser User-Agent to avoid blocking)
    call_args = mock_get.call_args
    assert "headers" in call_args.kwargs
    assert "User-Agent" in call_args.kwargs["headers"]
    assert "Mozilla" in call_args.kwargs["headers"]["User-Agent"]
    # Should also have other browser-like headers
    assert "Accept" in call_args.kwargs["headers"]
    assert "Accept-Language" in call_args.kwargs["headers"]

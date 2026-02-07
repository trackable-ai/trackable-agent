"""
Manual integration tests for policy extractor agent.

These tests make real LLM API calls and are marked as manual.
Run with: pytest -m manual tests/agents/test_policy_extractor.py
"""

import json
from pathlib import Path

import pytest
from google.genai.types import Content, Part

from trackable.agents.policy_extractor import (
    PolicyExtractorOutput,
    convert_extracted_to_policy,
    policy_extractor_runner,
)
from trackable.models.policy import PolicyType, RefundMethod, ReturnCondition
from trackable.utils.web_scraper import fetch_policy_page

pytestmark = pytest.mark.manual


@pytest.fixture(scope="module")
def sample_policy_html(shared_datadir: Path) -> str:
    """Load sample return policy HTML"""
    policy_path = shared_datadir / "sample_return_policy.html"
    return policy_path.read_text(encoding="utf-8")


@pytest.mark.asyncio
async def test_extract_policy_from_html(sample_policy_html: str):
    """Test policy extraction from sample HTML with real LLM"""
    # Create prompt for policy extractor
    prompt = f"""Extract return and exchange policy information from this HTML content.

Merchant: Sample Store
Domain: samplestore.com

HTML Content:
{sample_policy_html}

Extract all policy details including return windows, conditions, refund methods, shipping responsibility, and exclusions."""

    content = Content(parts=[Part(text=prompt)])

    # Run policy extractor agent
    session = await policy_extractor_runner.session_service.create_session(
        app_name=policy_extractor_runner.app_name,
        user_id="test-user",
    )

    # Collect agent response
    result_text = ""
    async for event in policy_extractor_runner.run_async(
        user_id="test-user",
        session_id=session.id,
        new_message=content,
    ):
        if event.content and event.content.parts:
            for part in event.content.parts:
                if part.text:
                    result_text = part.text

    assert result_text, "No result from policy extractor agent"

    # Parse the JSON response
    result = json.loads(result_text)
    output = PolicyExtractorOutput(**result)

    # Verify output structure
    assert output.policies, "Should extract at least one policy"
    assert output.overall_confidence > 0, "Should have confidence score"

    # Get the first policy (should be return policy)
    policy_data = output.policies[0]

    # Verify policy type
    assert policy_data.policy_type in [PolicyType.RETURN, PolicyType.EXCHANGE]

    # Verify return policy details (from sample HTML)
    if policy_data.return_allowed:
        # Should extract 30-day window
        assert (
            policy_data.return_window_days == 30
        ), "Should extract 30-day return window"

        # Should extract return conditions
        assert ReturnCondition.UNUSED in policy_data.return_conditions
        assert ReturnCondition.TAGS_ATTACHED in policy_data.return_conditions
        assert ReturnCondition.ORIGINAL_PACKAGING in policy_data.return_conditions

        # Should extract refund method
        assert policy_data.refund_method == RefundMethod.ORIGINAL_PAYMENT

        # Should extract excluded categories
        assert (
            "personalized" in str(policy_data.excluded_categories).lower()
            or "custom" in str(policy_data.excluded_categories).lower()
        )
        assert (
            "gift cards" in str(policy_data.excluded_categories).lower()
            or "gift card" in str(policy_data.excluded_categories).lower()
        )

    print(f"\n✅ Policy extraction successful!")
    print(f"   - Type: {policy_data.policy_type}")
    print(f"   - Return window: {policy_data.return_window_days} days")
    print(f"   - Conditions: {policy_data.return_conditions}")
    print(f"   - Refund method: {policy_data.refund_method}")
    print(f"   - Confidence: {policy_data.confidence_score}")


@pytest.mark.asyncio
async def test_convert_extracted_to_policy_model(sample_policy_html: str):
    """Test conversion from extracted data to Policy model"""
    # Create prompt for policy extractor
    prompt = f"""Extract return and exchange policy information from this HTML content.

Merchant: Sample Store
Domain: samplestore.com

HTML Content:
{sample_policy_html}

Extract all policy details."""

    content = Content(parts=[Part(text=prompt)])

    # Run policy extractor agent
    session = await policy_extractor_runner.session_service.create_session(
        app_name=policy_extractor_runner.app_name,
        user_id="test-user",
    )

    result_text = ""
    async for event in policy_extractor_runner.run_async(
        user_id="test-user",
        session_id=session.id,
        new_message=content,
    ):
        if event.content and event.content.parts:
            for part in event.content.parts:
                if part.text:
                    result_text = part.text

    assert result_text, "No result from policy extractor agent"

    # Parse and convert to Policy model
    result = json.loads(result_text)
    output = PolicyExtractorOutput(**result)
    extracted = output.policies[0]

    # Convert to full Policy model
    policy = convert_extracted_to_policy(
        extracted=extracted,
        merchant_id="test-merchant-123",
        source_url="https://samplestore.com/returns",
        raw_text=sample_policy_html,
        country_code="US",
    )

    # Verify Policy model fields
    assert policy.id, "Should generate policy ID"
    assert policy.merchant_id == "test-merchant-123"
    assert policy.policy_type in [PolicyType.RETURN, PolicyType.EXCHANGE]
    assert policy.country_code == "US"
    assert policy.source_url == "https://samplestore.com/returns"
    assert policy.raw_text == sample_policy_html
    assert policy.confidence_score is not None

    # Verify needs_verification is set correctly based on confidence
    if extracted.confidence_score < 0.7:
        assert policy.needs_verification is True
    else:
        assert policy.needs_verification is False

    # Verify return_policy or exchange_policy exists
    assert policy.return_policy is not None or policy.exchange_policy is not None

    if policy.return_policy:
        assert policy.return_policy.allowed is not None
        assert policy.return_policy.window_days is not None
        assert len(policy.return_policy.conditions) > 0

    print(f"\n✅ Policy model conversion successful!")
    print(f"   - Policy ID: {policy.id}")
    print(f"   - Type: {policy.policy_type}")
    print(f"   - Needs verification: {policy.needs_verification}")
    print(f"   - Return policy: {policy.return_policy is not None}")
    print(f"   - Exchange policy: {policy.exchange_policy is not None}")


@pytest.mark.asyncio
async def test_policy_extraction_confidence_scoring():
    """Test that confidence scoring works correctly"""
    # Test with clear, well-structured policy
    clear_policy = """
    <h1>Return Policy</h1>
    <p>We offer a 60-day return policy from date of delivery.</p>
    <p>Items must be unused with tags attached.</p>
    <p>Refunds issued to original payment method within 7 business days.</p>
    <p>Customer pays return shipping.</p>
    """

    prompt = f"""Extract return policy from this clear HTML:

{clear_policy}

This should have high confidence since the policy is very clear."""

    content = Content(parts=[Part(text=prompt)])

    session = await policy_extractor_runner.session_service.create_session(
        app_name=policy_extractor_runner.app_name,
        user_id="test-user",
    )

    result_text = ""
    async for event in policy_extractor_runner.run_async(
        user_id="test-user",
        session_id=session.id,
        new_message=content,
    ):
        if event.content and event.content.parts:
            for part in event.content.parts:
                if part.text:
                    result_text = part.text

    assert result_text
    result = json.loads(result_text)
    output = PolicyExtractorOutput(**result)

    # Clear policy should have high confidence
    assert (
        output.overall_confidence >= 0.7
    ), "Clear policy should have confidence >= 0.7"
    assert output.policies[0].confidence_score >= 0.7

    print(f"\n✅ Confidence scoring test passed!")
    print(f"   - Overall confidence: {output.overall_confidence}")
    print(f"   - Policy confidence: {output.policies[0].confidence_score}")


@pytest.mark.asyncio
async def test_policy_extraction_with_exchange():
    """Test extraction when both return and exchange policies exist"""
    combined_policy = """
    <h1>Returns & Exchanges</h1>

    <h2>Returns</h2>
    <p>30-day return window from delivery</p>
    <p>Items unused, tags attached</p>
    <p>Refund to original payment</p>

    <h2>Exchanges</h2>
    <p>Free exchanges for size and color within 30 days</p>
    <p>Free exchange shipping label provided</p>
    """

    prompt = f"""Extract return and exchange policies from:

{combined_policy}"""

    content = Content(parts=[Part(text=prompt)])

    session = await policy_extractor_runner.session_service.create_session(
        app_name=policy_extractor_runner.app_name,
        user_id="test-user",
    )

    result_text = ""
    async for event in policy_extractor_runner.run_async(
        user_id="test-user",
        session_id=session.id,
        new_message=content,
    ):
        if event.content and event.content.parts:
            for part in event.content.parts:
                if part.text:
                    result_text = part.text

    assert result_text
    result = json.loads(result_text)
    output = PolicyExtractorOutput(**result)

    # Should extract both policies or combined
    assert len(output.policies) >= 1

    # Check if we got both return and exchange info
    has_return_info = any(p.return_allowed is not None for p in output.policies)
    has_exchange_info = any(p.exchange_allowed is not None for p in output.policies)

    assert has_return_info, "Should extract return policy information"
    assert has_exchange_info, "Should extract exchange policy information"

    print(f"\n✅ Combined policy extraction successful!")
    print(f"   - Policies extracted: {len(output.policies)}")
    print(f"   - Has return info: {has_return_info}")
    print(f"   - Has exchange info: {has_exchange_info}")


@pytest.mark.asyncio
async def test_amazon_policy_extraction_from_saved_html(shared_datadir: Path):
    """Test extraction from saved Amazon return policy HTML (no network required)"""
    amazon_policy_url = (
        "https://www.amazon.com/gp/help/customer/display.html?nodeId=GKM69DUUYKQWKWX7"
    )

    # Load saved clean text
    clean_text_path = shared_datadir / "amazon_return_policy_clean.txt"
    clean_text = clean_text_path.read_text(encoding="utf-8")
    print(f"\n📂 Loaded saved policy page ({len(clean_text)} chars)")

    # Extract policy using agent
    prompt = f"""Extract return policy information from this Amazon HTML content.

Merchant: Amazon
Domain: amazon.com

HTML Content (cleaned):
{clean_text[:15000]}  # Limit to avoid token limits

Extract all return policy details including windows, conditions, refund methods, etc."""

    content = Content(parts=[Part(text=prompt)])

    session = await policy_extractor_runner.session_service.create_session(
        app_name=policy_extractor_runner.app_name,
        user_id="test-user",
    )

    print("🤖 Running policy extractor agent...")
    result_text = ""
    async for event in policy_extractor_runner.run_async(
        user_id="test-user",
        session_id=session.id,
        new_message=content,
    ):
        if event.content and event.content.parts:
            for part in event.content.parts:
                if part.text:
                    result_text = part.text

    assert result_text, "No result from policy extractor agent"

    # Parse the response
    result = json.loads(result_text)
    output = PolicyExtractorOutput(**result)

    # Verify we got policy data
    assert output.policies, "Should extract Amazon return policy"
    assert output.overall_confidence > 0, "Should have confidence score"

    policy_data = output.policies[0]

    # Amazon typically has a 30-day return window for most items
    # Let's verify we extracted something reasonable
    assert (
        policy_data.return_allowed is not None
    ), "Should determine if returns are allowed"

    if policy_data.return_allowed:
        # Amazon's return window varies, but should be extracted
        assert (
            policy_data.return_window_days is not None
        ), "Should extract return window"
        assert policy_data.return_window_days > 0, "Return window should be positive"

    # Amazon typically refunds to original payment method
    if policy_data.refund_method:
        print(f"   - Refund method: {policy_data.refund_method}")

    # Print extracted information
    print(f"\n✅ Amazon policy extraction successful!")
    print(f"   - Policy type: {policy_data.policy_type}")
    print(f"   - Returns allowed: {policy_data.return_allowed}")
    print(f"   - Return window: {policy_data.return_window_days} days")
    print(f"   - Conditions: {policy_data.return_conditions}")
    print(f"   - Refund method: {policy_data.refund_method}")
    print(f"   - Shipping responsibility: {policy_data.return_shipping_responsibility}")
    print(f"   - Excluded categories: {policy_data.excluded_categories}")
    print(f"   - Confidence: {policy_data.confidence_score}")
    print(f"   - Overall confidence: {output.overall_confidence}")

    # Convert to Policy model
    policy = convert_extracted_to_policy(
        extracted=policy_data,
        merchant_id="amazon-123",
        source_url=amazon_policy_url,
        raw_text=clean_text,
        country_code="US",
    )

    assert policy.id
    assert policy.merchant_id == "amazon-123"
    assert str(policy.source_url) == amazon_policy_url
    assert policy.return_policy is not None

    print(f"   - Policy model created successfully")
    print(f"   - Needs verification: {policy.needs_verification}")


@pytest.mark.asyncio
async def test_fetch_amazon_policy_live():
    """
    Test fetching Amazon's return policy from live website.

    This test actually fetches from Amazon's servers, so it:
    - Requires network access
    - May be blocked by Amazon's anti-bot measures
    - Should be run sparingly to avoid hitting their servers

    Use this to verify the web scraper still works with Amazon's current page structure.
    """
    amazon_policy_url = (
        "https://www.amazon.com/gp/help/customer/display.html?nodeId=GKM69DUUYKQWKWX7"
    )

    print(f"\n📥 Fetching live Amazon policy from {amazon_policy_url}")
    try:
        raw_html, clean_text = fetch_policy_page(amazon_policy_url, timeout=15)
    except Exception as e:
        pytest.skip(f"Failed to fetch Amazon policy page: {e}")

    print(f"✅ Successfully fetched policy page ({len(clean_text)} chars)")

    # Verify we got actual policy content
    assert len(clean_text) > 1000, "Policy text should be substantial"
    assert "return" in clean_text.lower(), "Should contain return policy information"
    assert "Amazon" in clean_text, "Should mention Amazon"

    print(f"✅ Amazon policy page fetched and validated!")
    print(f"   - HTML size: {len(raw_html)} chars")
    print(f"   - Clean text size: {len(clean_text)} chars")

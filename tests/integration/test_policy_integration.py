"""
Integration tests for PolicyRepository and Amazon policy population.

These tests require actual Cloud SQL connection and are marked as manual.
Run with: uv run pytest tests/integration/test_policy_integration.py -v
"""

import asyncio
import json
import os
from pathlib import Path
from typing import Any
from uuid import uuid4

import pytest
from dotenv import load_dotenv
from google.genai.types import Content, Part
from pydantic import HttpUrl

from trackable.agents.policy_extractor import (
    PolicyExtractorOutput,
    convert_extracted_to_policy,
)
from trackable.db import UnitOfWork
from trackable.models.order import Merchant
from trackable.models.policy import (
    Policy,
    PolicyType,
    RefundMethod,
    ReturnCondition,
    ReturnPolicy,
    ReturnShippingResponsibility,
)
from trackable.worker.handlers import policy_extractor_runner

# Load environment variables from .env
load_dotenv()

# Skip all tests if database is not configured
pytestmark = pytest.mark.skipif(
    not os.getenv("INSTANCE_CONNECTION_NAME"),
    reason="Database not configured (INSTANCE_CONNECTION_NAME not set)",
)


@pytest.fixture(scope="module")
def db_connection() -> Any:
    """Initialize database connection for tests."""
    from trackable.db import DatabaseConnection

    DatabaseConnection.initialize()
    yield DatabaseConnection
    DatabaseConnection.close()


class TestPolicyRepository:
    """Integration tests for PolicyRepository."""

    def _create_merchant(self, name: str, domain: str) -> Merchant:
        """Helper to create a merchant."""
        with UnitOfWork() as uow:
            merchant = Merchant(
                id="",
                name=name,
                domain=domain,
                support_url=HttpUrl(f"https://{domain}/help"),
            )
            saved_merchant = uow.merchants.upsert_by_domain(merchant)
            uow.commit()
            return saved_merchant

    def _create_policy(
        self,
        merchant_id: str,
        policy_type: PolicyType = PolicyType.RETURN,
        return_window_days: int = 30,
    ) -> Policy:
        """Helper to create a policy."""
        return Policy(
            id="",
            merchant_id=merchant_id,
            policy_type=policy_type,
            country_code="US",
            name=f"{policy_type.value.title()} Policy",
            description=f"Test {policy_type.value} policy",
            return_policy=ReturnPolicy(
                allowed=True,
                window_days=return_window_days,
                conditions=[ReturnCondition.UNUSED, ReturnCondition.TAGS_ATTACHED],
                refund_method=RefundMethod.ORIGINAL_PAYMENT,
                shipping_responsibility=ReturnShippingResponsibility.CUSTOMER,
                free_return_label=False,
                excluded_categories=["gift cards", "final sale"],
            ),
            source_url=HttpUrl("https://example.com/returns"),
            raw_text="Sample return policy text for testing",
            confidence_score=0.95,
            needs_verification=False,
        )

    def test_create_policy(self, db_connection):
        """Test creating a policy."""
        merchant = self._create_merchant(
            f"Policy Test Store {uuid4().hex[:8]}", f"policytest-{uuid4().hex[:8]}.com"
        )
        policy = self._create_policy(merchant.id)

        with UnitOfWork() as uow:
            saved_policy = uow.policies.create(policy)
            uow.commit()

        assert saved_policy.id
        assert saved_policy.merchant_id == merchant.id
        assert saved_policy.policy_type == PolicyType.RETURN
        assert saved_policy.country_code == "US"
        assert saved_policy.return_policy is not None
        assert saved_policy.return_policy.allowed is True
        assert saved_policy.return_policy.window_days == 30

    def test_get_by_merchant(self, db_connection):
        """Test getting policy by merchant, type, and country."""
        merchant = self._create_merchant(
            f"Get Policy Store {uuid4().hex[:8]}", f"getpolicy-{uuid4().hex[:8]}.com"
        )
        policy = self._create_policy(merchant.id)

        with UnitOfWork() as uow:
            uow.policies.create(policy)
            uow.commit()

        with UnitOfWork() as uow:
            retrieved = uow.policies.get_by_merchant(
                merchant.id, PolicyType.RETURN, "US"
            )

        assert retrieved is not None
        assert retrieved.merchant_id == merchant.id
        assert retrieved.policy_type == PolicyType.RETURN
        assert retrieved.country_code == "US"

    def test_list_by_merchant(self, db_connection):
        """Test listing all policies for a merchant."""
        merchant = self._create_merchant(
            f"List Policy Store {uuid4().hex[:8]}", f"listpolicy-{uuid4().hex[:8]}.com"
        )

        # Create return and exchange policies
        return_policy = self._create_policy(merchant.id, PolicyType.RETURN)
        exchange_policy = self._create_policy(merchant.id, PolicyType.EXCHANGE)

        with UnitOfWork() as uow:
            uow.policies.create(return_policy)
            uow.policies.create(exchange_policy)
            uow.commit()

        with UnitOfWork() as uow:
            policies = uow.policies.list_by_merchant(merchant.id)

        assert len(policies) == 2
        policy_types = {p.policy_type for p in policies}
        assert PolicyType.RETURN in policy_types
        assert PolicyType.EXCHANGE in policy_types

    def test_upsert_creates_new_policy(self, db_connection):
        """Test upsert creates new policy when it doesn't exist."""
        merchant = self._create_merchant(
            f"Upsert New Store {uuid4().hex[:8]}", f"upsertnew-{uuid4().hex[:8]}.com"
        )
        policy = self._create_policy(merchant.id)

        with UnitOfWork() as uow:
            saved_policy = uow.policies.upsert_by_merchant_and_type(policy)
            uow.commit()

        assert saved_policy.id
        assert saved_policy.merchant_id == merchant.id

        # Verify it's in the database
        with UnitOfWork() as uow:
            retrieved = uow.policies.get_by_merchant(
                merchant.id, PolicyType.RETURN, "US"
            )

        assert retrieved is not None
        assert retrieved.id == saved_policy.id

    def test_upsert_updates_existing_policy(self, db_connection):
        """Test upsert updates existing policy when content changes."""
        merchant = self._create_merchant(
            f"Upsert Update Store {uuid4().hex[:8]}",
            f"upsertupdate-{uuid4().hex[:8]}.com",
        )
        policy = self._create_policy(merchant.id, return_window_days=30)

        # Create initial policy
        with UnitOfWork() as uow:
            saved_policy = uow.policies.upsert_by_merchant_and_type(policy)
            uow.commit()
            original_id = saved_policy.id

        # Update with different content
        policy.raw_text = "Updated return policy text"
        assert policy.return_policy is not None
        policy.return_policy.window_days = 60

        with UnitOfWork() as uow:
            updated_policy = uow.policies.upsert_by_merchant_and_type(policy)
            uow.commit()

        # Should have same ID but updated content
        assert updated_policy.id == original_id
        assert updated_policy.return_policy is not None
        assert updated_policy.return_policy.window_days == 60

    def test_upsert_skips_update_when_content_unchanged(self, db_connection):
        """Test upsert skips update when raw_text hash is the same."""
        merchant = self._create_merchant(
            f"Upsert Skip Store {uuid4().hex[:8]}", f"upsertskip-{uuid4().hex[:8]}.com"
        )
        policy = self._create_policy(merchant.id)

        # Create initial policy
        with UnitOfWork() as uow:
            saved_policy = uow.policies.upsert_by_merchant_and_type(policy)
            uow.commit()

        # Try to upsert again with same raw_text (but different window)
        assert policy.return_policy is not None
        policy.return_policy.window_days = 60  # Change this
        policy.raw_text = saved_policy.raw_text  # But keep raw_text same

        with UnitOfWork() as uow:
            result = uow.policies.upsert_by_merchant_and_type(policy)

        # Should return the existing policy without updating
        assert result.id == saved_policy.id
        # Window should NOT be updated because hash matched
        assert result.return_policy is not None
        assert result.return_policy.window_days == 30  # Original value


@pytest.mark.manual
class TestPopulateAmazonPolicy:
    """Test to populate Amazon's actual policy to the database."""

    def test_populate_amazon_policy_from_saved_html(self, db_connection):
        """
        Extract and save Amazon's return policy to database.

        This test uses the saved Amazon HTML and runs the policy extractor
        to populate the database with real policy data.

        Marked as manual because it calls the LLM.
        """
        # Load saved Amazon HTML
        test_data_dir = Path(__file__).parent.parent / "agents" / "data"
        clean_text_path = test_data_dir / "amazon_return_policy_clean.txt"
        clean_text = clean_text_path.read_text(encoding="utf-8")

        # Create or get Amazon merchant
        with UnitOfWork() as uow:
            merchant = Merchant(
                id="",
                name="Amazon",
                domain="amazon.com",
                support_url=HttpUrl(
                    "https://www.amazon.com/gp/help/customer/display.html"
                ),
            )
            amazon_merchant = uow.merchants.upsert_by_domain(merchant)
            uow.commit()

        print(f"\n✅ Amazon merchant: {amazon_merchant.id}")

        # Extract policy using agent
        amazon_policy_url = "https://www.amazon.com/gp/help/customer/display.html?nodeId=GKM69DUUYKQWKWX7"

        prompt = f"""Extract return policy information from this Amazon HTML content.

Merchant: Amazon
Domain: amazon.com

HTML Content (cleaned):
{clean_text[:15000]}

Extract all return policy details including windows, conditions, refund methods, etc."""

        content = Content(parts=[Part(text=prompt)])

        # Run policy extractor agent
        async def extract_policy():
            session = await policy_extractor_runner.session_service.create_session(
                app_name=policy_extractor_runner.app_name,
                user_id="integration-test",
            )

            print("🤖 Running policy extractor agent...")
            result_text = ""
            async for event in policy_extractor_runner.run_async(
                user_id="integration-test",
                session_id=session.id,
                new_message=content,
            ):
                if event.content and event.content.parts:
                    for part in event.content.parts:
                        if part.text:
                            result_text = part.text

            return result_text

        result_text = asyncio.run(extract_policy())
        assert result_text, "No result from policy extractor agent"

        # Parse the response
        result = json.loads(result_text)
        output = PolicyExtractorOutput(**result)

        print(f"✅ Extracted {len(output.policies)} policy/policies")
        print(f"   Overall confidence: {output.overall_confidence}")

        # Save policies to database
        saved_policies = []
        with UnitOfWork() as uow:
            for extracted in output.policies:
                policy = convert_extracted_to_policy(
                    extracted=extracted,
                    merchant_id=amazon_merchant.id,
                    source_url=amazon_policy_url,
                    raw_text=clean_text,
                    country_code="US",
                )

                saved_policy = uow.policies.upsert_by_merchant_and_type(policy)
                saved_policies.append(saved_policy)

                print(f"   ✅ Saved {saved_policy.policy_type.value} policy")
                print(f"      - ID: {saved_policy.id}")
                print(f"      - Confidence: {saved_policy.confidence_score}")
                if saved_policy.return_policy is not None:
                    print(
                        f"      - Return window: {saved_policy.return_policy.window_days} days"
                    )

            uow.commit()

        print(f"\n✅ Amazon policy populated to database!")
        print(f"   Merchant ID: {amazon_merchant.id}")
        print(f"   Policies saved: {len(saved_policies)}")

        # Verify policies are retrievable
        with UnitOfWork() as uow:
            policies = uow.policies.list_by_merchant(amazon_merchant.id)

        assert len(policies) >= 1
        print(f"   ✅ Verified {len(policies)} policy/policies in database")

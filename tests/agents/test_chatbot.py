"""Integration tests for chatbot agent with real database and LLM.

These tests are marked as manual because they:
1. Require a real Cloud SQL database connection (INSTANCE_CONNECTION_NAME)
2. Use the Gemini LLM API (requires API key)
3. Are slower and cost money per run
"""

import os
from datetime import datetime, timezone
from uuid import uuid4

import dotenv
import pytest
from google.adk.runners import InMemoryRunner

from trackable.agents.chatbot import chatbot_agent
from trackable.db import DatabaseConnection, UnitOfWork
from trackable.models.order import Item, Merchant, Money, Order, OrderStatus, SourceType

pytestmark = pytest.mark.manual

pytest_plugins = ("pytest_asyncio",)


@pytest.fixture(scope="module", autouse=True)
def load_env():
    dotenv.load_dotenv()


@pytest.fixture(scope="module")
def db_connection():
    """Initialize database connection for the module."""
    instance_connection_name = os.getenv("INSTANCE_CONNECTION_NAME")
    if not instance_connection_name:
        pytest.skip("INSTANCE_CONNECTION_NAME not set")

    DatabaseConnection.initialize(
        instance_connection_name=instance_connection_name,
        db_name=os.getenv("DB_NAME", "trackable"),
        db_user=os.getenv("DB_USER", "postgres"),
    )
    yield
    DatabaseConnection.close()


@pytest.fixture(scope="module")
def test_user(db_connection):
    """Get or create a fixed test user for all tests."""
    from trackable.models.user import User

    test_email = "chatbot-integration-test@trackable.test"

    with UnitOfWork() as uow:
        # Try to find existing user
        from sqlalchemy import select

        stmt = select(uow.users.table).where(uow.users.table.c.email == test_email)
        result = uow.session.execute(stmt)
        row = result.fetchone()

        if row:
            user_id = str(row.id)
        else:
            # Create new user
            user = User(
                id=str(uuid4()),
                email=test_email,
                name="Chatbot Test User",
                status="active",
            )
            created = uow.users.create(user)
            uow.commit()
            user_id = created.id

    return user_id


class TestChatbotSearchIntegration:
    """Test chatbot agent using search_orders tool with real database."""

    def _create_merchant(self, name: str) -> Merchant:
        """Create and persist a merchant."""
        merchant = Merchant(
            id=str(uuid4()),
            name=name,
            domain=f"{name.lower().replace(' ', '-')}-{uuid4().hex[:8]}.com",
        )
        with UnitOfWork() as uow:
            saved = uow.merchants.create(merchant)
            uow.commit()
        return saved

    def _create_order(
        self,
        user_id: str,
        merchant: Merchant,
        order_number: str,
        item_names: list[str],
    ) -> Order:
        """Create and persist an order with items."""
        order_id = str(uuid4())
        now = datetime.now(timezone.utc)
        items = [
            Item(
                id=str(uuid4()),
                order_id=order_id,
                name=name,
                quantity=1,
                price=Money(amount="99.99"),
            )
            for name in item_names
        ]
        order = Order(
            id=order_id,
            user_id=user_id,
            merchant=merchant,
            order_number=order_number,
            order_date=now,
            status=OrderStatus.SHIPPED,
            items=items,
            total=Money(amount="99.99"),
            source_type=SourceType.EMAIL,
            created_at=now,
            updated_at=now,
        )
        with UnitOfWork() as uow:
            created = uow.orders.create(order)
            uow.commit()
        return created

    @pytest.mark.asyncio
    async def test_chatbot_can_search_by_product_name(
        self, db_connection, test_user: str
    ):
        """Chatbot should use search_orders to find orders by product name."""
        # Create test data
        tag = uuid4().hex[:8]
        merchant = self._create_merchant("Apple Store")
        order = self._create_order(
            test_user,
            merchant,
            f"APL-{tag}",
            [f"MacBook Pro M4 {tag}"],
        )

        # Create chatbot session with user context
        runner = InMemoryRunner(agent=chatbot_agent, app_name="test-chatbot")
        session = await runner.session_service.create_session(
            agent_id=chatbot_agent.name
        )

        # User asks about their MacBook order
        user_message = f"[Context: The current user_id is '{test_user}']\n\nWhat's the status of my MacBook Pro M4 {tag} order?"

        # Run agent and collect response
        response_text = ""
        async for event in runner.run_async(
            session_id=session.id, new_message=user_message
        ):
            if event.content and event.content.parts:
                for part in event.content.parts:
                    if part.text:
                        response_text += part.text

        # Verify the agent found the order and mentioned key details
        assert response_text, "Chatbot should return a response"
        assert (
            "shipped" in response_text.lower()
        ), "Response should mention order status"
        # The agent should have found the order via search_orders
        assert (
            tag in response_text or "macbook" in response_text.lower()
        ), "Response should reference the MacBook order"

    @pytest.mark.asyncio
    async def test_chatbot_can_search_by_merchant(self, db_connection, test_user: str):
        """Chatbot should use search_orders to find orders by merchant name."""
        # Create test data
        tag = uuid4().hex[:8]
        merchant = self._create_merchant(f"UniqueStore {tag}")
        order = self._create_order(
            test_user,
            merchant,
            f"UNQ-{tag}",
            ["Test Widget"],
        )

        # Create chatbot session
        runner = InMemoryRunner(agent=chatbot_agent, app_name="test-chatbot")
        session = await runner.session_service.create_session(
            agent_id=chatbot_agent.name
        )

        # User asks about orders from a specific merchant
        user_message = f"[Context: The current user_id is '{test_user}']\n\nShow me my orders from UniqueStore {tag}"

        # Run agent
        response_text = ""
        async for event in runner.run_async(
            session_id=session.id, new_message=user_message
        ):
            if event.content and event.content.parts:
                for part in event.content.parts:
                    if part.text:
                        response_text += part.text

        # Verify the agent found the merchant's orders
        assert response_text, "Chatbot should return a response"
        assert tag in response_text, "Response should reference the unique merchant"

    @pytest.mark.asyncio
    async def test_chatbot_handles_no_search_results(
        self, db_connection, test_user: str
    ):
        """Chatbot should gracefully handle when search finds nothing."""
        # Create chatbot session
        runner = InMemoryRunner(agent=chatbot_agent, app_name="test-chatbot")
        session = await runner.session_service.create_session(
            agent_id=chatbot_agent.name
        )

        # User asks about a non-existent product
        nonexistent = f"ZZZNonexistent-{uuid4().hex}"
        user_message = f"[Context: The current user_id is '{test_user}']\n\nWhere is my {nonexistent} order?"

        # Run agent
        response_text = ""
        async for event in runner.run_async(
            session_id=session.id, new_message=user_message
        ):
            if event.content and event.content.parts:
                for part in event.content.parts:
                    if part.text:
                        response_text += part.text

        # Verify the agent responds appropriately
        assert response_text, "Chatbot should return a response"
        # Should indicate no results found
        assert any(
            phrase in response_text.lower()
            for phrase in ["not found", "no orders", "couldn't find", "no results"]
        ), "Response should indicate no orders were found"

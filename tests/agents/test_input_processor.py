"""
Tests for the input processor subagent.
"""

from decimal import Decimal
from email import message_from_file
from email.message import Message
from pathlib import Path
from uuid import uuid4

import dotenv
import pytest
from google.adk.runners import InMemoryRunner
from google.genai.types import Content, Part

from trackable.agents import (
    ExtractedOrderData,
    InputProcessorInput,
    InputProcessorOutput,
    convert_extracted_to_order,
    input_processor_agent,
)
from trackable.models.order import Carrier, Item, Money, OrderStatus, SourceType

pytest_plugins = ("pytest_asyncio",)


@pytest.fixture(scope="session", autouse=True)
def load_env():
    dotenv.load_dotenv()


class TestInputProcessorSchemas:
    """Test input/output schemas"""

    def test_input_schema_email(self):
        """Test creating email input"""
        input_data = InputProcessorInput(
            input_type="email",
            query="subject:(order confirmation)",
            max_results=5,
        )
        assert input_data.input_type == "email"
        assert input_data.query == "subject:(order confirmation)"
        assert input_data.max_results == 5

    def test_input_schema_image(self):
        """Test creating image input"""
        input_data = InputProcessorInput(
            input_type="image",
            source_id="screenshot_001",
            image_data="/path/to/image.png",
        )
        assert input_data.input_type == "image"
        assert input_data.source_id == "screenshot_001"
        assert input_data.image_data == "/path/to/image.png"

    def test_extracted_order_data(self):
        """Test extracted order data schema"""
        extracted = ExtractedOrderData(
            merchant_name="Nike",
            merchant_domain="nike.com",
            merchant_order_id="NKE-2024-001234",
            order_total=Decimal("132.50"),
            currency="USD",
            items=[
                Item(
                    name="Air Max 90",
                    quantity=1,
                    price=Money(amount=Decimal("120.00"), currency="USD"),
                    id=uuid4().hex,
                    order_id="",
                ),
            ],
            tracking_number="1Z999AA10123456784",
            carrier="UPS",
            confidence_score=0.95,
            needs_clarification=False,
            extraction_notes="Clear order confirmation email",
        )

        assert extracted.merchant_name == "Nike"
        assert extracted.order_total == Decimal("132.50")
        assert len(extracted.items) == 1
        assert extracted.confidence_score == 0.95
        assert not extracted.needs_clarification

    def test_output_schema(self):
        """Test output schema"""
        output = InputProcessorOutput(
            orders=[
                ExtractedOrderData(
                    merchant_name="Test Store",
                    confidence_score=0.8,
                )
            ],
            processing_status="success",
            total_processed=1,
        )

        assert len(output.orders) == 1
        assert output.processing_status == "success"
        assert output.total_processed == 1


class TestConvertExtractedToOrder:
    """Test converting extracted data to Order model"""

    def test_convert_basic_order(self):
        """Test converting basic extracted order"""
        extracted = ExtractedOrderData(
            merchant_name="Nike",
            merchant_domain="nike.com",
            merchant_order_id="NKE-001",
            order_total=Decimal("100.00"),
            items=[
                Item(
                    id=uuid4().hex,
                    order_id="",
                    name="Running Shoes",
                    quantity=1,
                    price=Money(amount=Decimal("100.00"), currency="USD"),
                ),
            ],
            confidence_score=0.9,
        )

        order = convert_extracted_to_order(
            extracted=extracted,
            user_id="user_123",
            source_type=SourceType.EMAIL,
            source_id="email_456",
        )

        assert order.user_id == "user_123"
        assert order.merchant.name == "Nike"
        assert order.merchant.domain == "nike.com"
        assert order.order_number == "NKE-001"
        assert order.status == OrderStatus.DETECTED
        assert order.source_type == SourceType.EMAIL
        assert order.source_id == "email_456"
        assert order.confidence_score == 0.9
        assert len(order.items) == 1
        assert order.items[0].name == "Running Shoes"

    def test_convert_order_with_shipment(self):
        """Test converting order with tracking info"""
        extracted = ExtractedOrderData(
            merchant_name="Amazon",
            merchant_order_id="AMZ-789",
            order_total=Decimal("50.00"),
            items=[
                Item(
                    id=uuid4().hex,
                    order_id="",
                    name="Book",
                    quantity=1,
                    price=Money(amount=Decimal("50.00"), currency="USD"),
                )
            ],
            tracking_number="1Z999AA10123456784",
            carrier="UPS",
            confidence_score=0.85,
        )

        order = convert_extracted_to_order(
            extracted=extracted,
            user_id="user_123",
            source_type=SourceType.EMAIL,
            source_id="email_789",
        )

        assert len(order.shipments) == 1
        assert order.shipments[0].tracking_number == "1Z999AA10123456784"
        assert order.shipments[0].carrier == Carrier.UPS

    def test_convert_order_with_clarifications(self):
        """Test converting order that needs clarification"""
        extracted = ExtractedOrderData(
            merchant_name="Unknown Store",
            items=[],
            confidence_score=0.4,
            needs_clarification=True,
            clarification_questions=[
                "What items were in this order?",
                "What is the total amount?",
            ],
            extraction_notes="Very limited information in email",
        )

        order = convert_extracted_to_order(
            extracted=extracted,
            user_id="user_123",
            source_type=SourceType.EMAIL,
            source_id="email_unclear",
        )

        assert order.needs_clarification is True
        assert len(order.clarification_questions) == 2
        assert len(order.notes) == 1
        assert order.notes[0] == "Very limited information in email"
        assert order.confidence_score == 0.4


class TestInputProcessorAgent:
    """Test the input processor agent configuration"""

    def test_agent_configuration(self):
        """Test agent has correct configuration"""
        assert input_processor_agent.name == "input_processor"
        assert "diverse inputs" in input_processor_agent.description
        assert input_processor_agent.output_schema == InputProcessorOutput


class TestInputProcessorWithRealData:
    """
    Integration tests with real email data.

    Uses pytest-datadir fixture to access test files from
    tests/subagents/test_input_processor/ directory.
    """

    @pytest.mark.manual
    @pytest.mark.asyncio
    async def test_extract_order_from_sample_email(self, shared_datadir: Path):
        """Test extracting order information from sample email"""
        email_file = shared_datadir / "sample_email.eml"

        with open(email_file, "r", encoding="utf-8") as f:
            msg: Message[str, str] = message_from_file(f)

        runner = InMemoryRunner(agent=input_processor_agent)
        session = await runner.session_service.create_session(
            app_name=runner.app_name, user_id="test_user"
        )
        content: Content = Content(
            parts=[Part.from_bytes(data=msg.as_bytes(), mime_type="text/plain")]
        )
        response = ""
        async for event in runner.run_async(
            user_id=session.user_id,
            session_id=session.id,
            new_message=content,
        ):
            if event.content is None:
                continue

            if (
                event.content.parts is not None
                and event.content.parts[0].text is not None
            ):
                response = event.content.parts[0].text
                print("Agent Response:", response)
        assert len(response) > 0

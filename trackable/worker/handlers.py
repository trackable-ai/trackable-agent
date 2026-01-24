"""
Task handlers for Cloud Tasks processing.

These handlers contain the business logic for processing different task types.
"""

import json

from google.adk.runners import InMemoryRunner
from google.genai.types import Blob, Content, Part

from trackable.agents.input_processor import (
    InputProcessorOutput,
    convert_extracted_to_order,
    input_processor_agent,
)
from trackable.models.order import SourceType

# Create runner for input processor agent
input_processor_runner = InMemoryRunner(
    agent=input_processor_agent, app_name="input-processor"
)


def detect_image_mime_type(image_bytes: bytes) -> str:
    """
    Detect MIME type from image bytes.

    Args:
        image_bytes: Image data as bytes

    Returns:
        MIME type string (e.g., 'image/png', 'image/jpeg')
    """
    # Check magic bytes for common image formats
    if image_bytes.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png"
    elif image_bytes.startswith(b"\xff\xd8\xff"):
        return "image/jpeg"
    elif image_bytes.startswith(b"GIF87a") or image_bytes.startswith(b"GIF89a"):
        return "image/gif"
    elif image_bytes.startswith(b"RIFF") and b"WEBP" in image_bytes[:20]:
        return "image/webp"
    elif image_bytes.startswith(b"BM"):
        return "image/bmp"
    else:
        return "application/octet-stream"


async def handle_gmail_sync(
    user_email: str,
    user_id: str,
    history_id: str | None = None,
) -> dict:
    """
    Handle Gmail sync task.

    Fetches new emails from Gmail using the history API and processes
    order confirmation emails.

    Args:
        user_email: User's Gmail address
        user_id: Internal user ID
        history_id: Last history ID for incremental sync

    Returns:
        dict: Processing result with counts
    """
    # TODO: Implement Gmail API integration
    # 1. Fetch emails since history_id using Gmail API
    # 2. Filter for order confirmation emails
    # 3. For each email, call handle_parse_email
    # 4. Update user's last_history_id in database

    print(f"📧 Gmail sync for {user_email}, history_id={history_id}")

    # Placeholder implementation
    return {
        "orders_created": 0,
        "orders_updated": 0,
        "emails_processed": 0,
        "new_history_id": history_id,
    }


async def handle_parse_email(
    job_id: str,
    user_id: str,
    source_id: str,
    email_content: str,
) -> dict:
    """
    Handle email parsing task.

    Parses an email to extract order information using the input processor agent.

    Args:
        job_id: Job ID in database
        user_id: User ID who submitted the email
        source_id: Source ID for tracking
        email_content: Email content to parse

    Returns:
        dict: Processing result with order info
    """
    print(f"📨 Parsing email for job_id={job_id}")

    try:
        # Create prompt for input processor
        prompt = f"""Extract order information from this email:

{email_content}

Parse all order details including:
- Merchant name and domain
- Order number and date
- Items ordered (with names, quantities, prices)
- Tracking information (if available)
- Total amount and currency

Return structured data with confidence score."""

        # Create content for agent
        content = Content(parts=[Part(text=prompt)])

        # Run agent with session
        session = await input_processor_runner.session_service.create_session(
            app_name=input_processor_runner.app_name,
            user_id=user_id,
        )

        # Collect agent response
        result_text = ""
        async for event in input_processor_runner.run_async(
            user_id=user_id,
            session_id=session.id,
            new_message=content,
        ):
            # Collect the text response
            if event.content and event.content.parts:
                for part in event.content.parts:
                    if part.text:
                        result_text = part.text

        if not result_text:
            raise ValueError("No result from input processor agent")

        # Parse the JSON response from the agent
        result = json.loads(result_text)

        # Parse the output
        if isinstance(result, dict):
            output = InputProcessorOutput(**result)
        else:
            output = result

        if not output.orders or len(output.orders) == 0:
            print(f"⚠️  No orders found in email")
            # TODO: Update job status to failed in database
            return {
                "status": "no_orders_found",
                "job_id": job_id,
                "order_id": None,
            }

        # Get the first extracted order
        extracted = output.orders[0]

        # Convert to Order model
        order = convert_extracted_to_order(
            extracted=extracted,
            user_id=user_id,
            source_type=SourceType.EMAIL,
            source_id=source_id,
        )

        print(
            f"✅ Extracted order: merchant={order.merchant.name}, confidence={order.confidence_score}"
        )

        # TODO: Save order to database
        # TODO: Update job status to completed in database

        return {
            "status": "success",
            "job_id": job_id,
            "order_id": order.id,
            "merchant_name": order.merchant.name,
            "confidence_score": order.confidence_score,
            "needs_clarification": order.needs_clarification,
        }

    except Exception as e:
        print(f"❌ Email parsing error: {e}")
        # TODO: Update job status to failed in database
        raise


async def handle_parse_image(
    job_id: str,
    user_id: str,
    source_id: str,
    image_url: str | None = None,
    image_data: bytes | None = None,
) -> dict:
    """
    Handle image/screenshot parsing task.

    Parses a screenshot to extract order information using the input processor agent.

    Args:
        job_id: Job ID in database
        user_id: User ID who uploaded the image
        source_id: Source ID for tracking
        image_url: GCS URL or public URL of image
        image_data: image data

    Returns:
        dict: Processing result with order info and duplicate detection
    """
    print(f"🖼️  Parsing image for job_id={job_id}")

    try:
        # TODO: Check for duplicate images using perceptual hashing
        # If duplicate found, return existing order info

        # TODO: Download image from URL or decode base64 data
        # For now, we'll work with URLs or base64 data directly

        if not image_url and not image_data:
            raise ValueError("Either image_url or image_data must be provided")

        # Create prompt for input processor
        prompt = """Extract order information from this screenshot or receipt image.

Look for:
- Merchant/store name and logo
- Order number or confirmation code
- Date of order
- Items purchased (names, quantities, prices)
- Tracking numbers (if visible)
- Total amount and currency
- Any delivery information

Return structured data with confidence score. If information is unclear or missing, set needs_clarification=true and include questions."""

        # Create content for agent (with vision capability)
        # Note: The input processor uses gemini-2.5-flash which has vision
        parts = [Part(text=prompt)]

        if image_url:
            # For URLs, we would need to download first
            # For now, include as text reference
            parts.append(Part(text=f"Image URL: {image_url}"))
        elif image_data:
            # Detect MIME type from image data
            mime_type = detect_image_mime_type(image_data)

            # Create inline data part for vision
            parts.append(Part(inline_data=Blob(data=image_data, mime_type=mime_type)))

        content = Content(parts=parts)

        # Run agent with session
        session = await input_processor_runner.session_service.create_session(
            app_name=input_processor_runner.app_name,
            user_id=user_id,
        )

        # Collect agent response
        result_text = ""
        async for event in input_processor_runner.run_async(
            user_id=user_id,
            session_id=session.id,
            new_message=content,
        ):
            # Collect the text response
            if event.content and event.content.parts:
                for part in event.content.parts:
                    if part.text:
                        result_text = part.text

        if not result_text:
            raise ValueError("No result from input processor agent")

        # Parse the JSON response from the agent
        result = json.loads(result_text)

        # Parse the output
        if isinstance(result, dict):
            output = InputProcessorOutput(**result)
        else:
            output = result

        if not output.orders or len(output.orders) == 0:
            print(f"⚠️  No orders found in image")
            # TODO: Update job status to failed in database
            return {
                "status": "no_orders_found",
                "job_id": job_id,
                "order_id": None,
                "is_duplicate": False,
            }

        # Get the first extracted order
        extracted = output.orders[0]

        # Convert to Order model
        order = convert_extracted_to_order(
            extracted=extracted,
            user_id=user_id,
            source_type=SourceType.SCREENSHOT,
            source_id=source_id,
        )

        print(
            f"✅ Extracted order from image: merchant={order.merchant.name}, confidence={order.confidence_score}"
        )

        # TODO: Save order to database
        # TODO: Update job status to completed in database
        # TODO: Store image hash for duplicate detection

        return {
            "status": "success",
            "job_id": job_id,
            "order_id": order.id,
            "merchant_name": order.merchant.name,
            "confidence_score": order.confidence_score,
            "needs_clarification": order.needs_clarification,
            "is_duplicate": False,  # TODO: Implement duplicate detection
        }

    except Exception as e:
        print(f"❌ Image parsing error: {e}")
        # TODO: Update job status to failed in database
        raise

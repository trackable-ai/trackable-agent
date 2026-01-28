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
from trackable.db import DatabaseConnection, UnitOfWork
from trackable.models.order import Merchant, SourceType
from trackable.utils.hash import compute_sha256

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

    # Mark job as started (if DB is available)
    if DatabaseConnection.is_initialized():
        with UnitOfWork() as uow:
            uow.jobs.mark_started(job_id)
            uow.commit()

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
            # Update job status to completed with no orders
            if DatabaseConnection.is_initialized():
                with UnitOfWork() as uow:
                    uow.jobs.mark_completed(job_id, {"status": "no_orders_found"})
                    uow.commit()
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

        # Save to database if available
        is_new_order = True
        if DatabaseConnection.is_initialized():
            with UnitOfWork() as uow:
                # Upsert merchant by domain (handles name normalization and aliases)
                merchant_model = Merchant(
                    id="",  # Will be generated by repository
                    name=order.merchant.name,
                    domain=order.merchant.domain,
                    support_email=order.merchant.support_email,
                    support_url=order.merchant.support_url,
                    return_portal_url=order.merchant.return_portal_url,
                )
                saved_merchant = uow.merchants.upsert_by_domain(merchant_model)

                # Update order with persisted merchant ID
                order.merchant.id = saved_merchant.id

                # Upsert order (update existing or create new)
                saved_order, is_new_order = uow.orders.upsert_by_order_number(order)

                # Mark source as processed
                uow.sources.mark_processed(source_id, saved_order.id)

                # Mark job as completed
                uow.jobs.mark_completed(
                    job_id,
                    {
                        "order_id": saved_order.id,
                        "merchant_name": saved_merchant.name,
                        "confidence_score": order.confidence_score,
                        "is_new_order": is_new_order,
                    },
                )
                uow.commit()

                order_id = saved_order.id
        else:
            order_id = order.id

        status = "created" if is_new_order else "updated"
        print(f"✅ Order {status}: {order_id}")

        return {
            "status": status,
            "job_id": job_id,
            "order_id": order_id,
            "merchant_name": order.merchant.name,
            "confidence_score": order.confidence_score,
            "needs_clarification": order.needs_clarification,
            "is_new_order": is_new_order,
        }

    except Exception as e:
        print(f"❌ Email parsing error: {e}")
        # Update job status to failed
        if DatabaseConnection.is_initialized():
            with UnitOfWork() as uow:
                uow.jobs.mark_failed(job_id, str(e))
                uow.commit()
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

    # Mark job as started
    if DatabaseConnection.is_initialized():
        with UnitOfWork() as uow:
            uow.jobs.mark_started(job_id)
            uow.commit()

    try:
        if not image_url and not image_data:
            raise ValueError("Either image_url or image_data must be provided")

        # Check for duplicate images using hash
        is_duplicate = False
        existing_order_id = None

        if image_data and DatabaseConnection.is_initialized():
            image_hash = compute_sha256(image_data)
            with UnitOfWork() as uow:
                existing_source = uow.sources.find_by_image_hash(user_id, image_hash)
                if existing_source and existing_source.order_id:
                    is_duplicate = True
                    existing_order_id = existing_source.order_id
                    print(
                        f"⚠️  Duplicate image detected, existing order: {existing_order_id}"
                    )

                    # Mark job as completed with duplicate info
                    uow.jobs.mark_completed(
                        job_id,
                        {
                            "status": "duplicate",
                            "existing_order_id": existing_order_id,
                        },
                    )
                    uow.commit()

                    return {
                        "status": "duplicate",
                        "job_id": job_id,
                        "order_id": existing_order_id,
                        "is_duplicate": True,
                    }

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
        parts = [Part(text=prompt)]

        if image_url:
            parts.append(Part(text=f"Image URL: {image_url}"))
        elif image_data:
            mime_type = detect_image_mime_type(image_data)
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
            if event.content and event.content.parts:
                for part in event.content.parts:
                    if part.text:
                        result_text = part.text

        if not result_text:
            raise ValueError("No result from input processor agent")

        # Parse the JSON response
        result = json.loads(result_text)

        if isinstance(result, dict):
            output = InputProcessorOutput(**result)
        else:
            output = result

        if not output.orders or len(output.orders) == 0:
            print(f"⚠️  No orders found in image")
            if DatabaseConnection.is_initialized():
                with UnitOfWork() as uow:
                    uow.jobs.mark_completed(job_id, {"status": "no_orders_found"})
                    uow.commit()
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
            f"✅ Extracted order from image: merchant={order.merchant.name}, "
            f"confidence={order.confidence_score}"
        )

        # Save to database if available
        is_new_order = True
        if DatabaseConnection.is_initialized():
            with UnitOfWork() as uow:
                # Upsert merchant by domain (handles name normalization and aliases)
                merchant_model = Merchant(
                    id="",  # Will be generated by repository
                    name=order.merchant.name,
                    domain=order.merchant.domain,
                    support_email=order.merchant.support_email,
                    support_url=order.merchant.support_url,
                    return_portal_url=order.merchant.return_portal_url,
                )
                saved_merchant = uow.merchants.upsert_by_domain(merchant_model)

                # Update order with persisted merchant ID
                order.merchant.id = saved_merchant.id

                # Upsert order (update existing or create new)
                saved_order, is_new_order = uow.orders.upsert_by_order_number(order)

                # Mark source as processed (and store image hash)
                uow.sources.mark_processed(source_id, saved_order.id)

                # Mark job as completed
                uow.jobs.mark_completed(
                    job_id,
                    {
                        "order_id": saved_order.id,
                        "merchant_name": saved_merchant.name,
                        "confidence_score": order.confidence_score,
                        "is_new_order": is_new_order,
                    },
                )
                uow.commit()

                order_id = saved_order.id
        else:
            order_id = order.id

        status = "created" if is_new_order else "updated"
        print(f"✅ Order {status}: {order_id}")

        return {
            "status": status,
            "job_id": job_id,
            "order_id": order_id,
            "merchant_name": order.merchant.name,
            "confidence_score": order.confidence_score,
            "needs_clarification": order.needs_clarification,
            "is_duplicate": False,
            "is_new_order": is_new_order,
        }

    except Exception as e:
        print(f"❌ Image parsing error: {e}")
        if DatabaseConnection.is_initialized():
            with UnitOfWork() as uow:
                uow.jobs.mark_failed(job_id, str(e))
                uow.commit()
        raise

"""
Task handlers for Cloud Tasks processing.

These handlers contain the business logic for processing different task types.
"""

import json
import logging

logger = logging.getLogger(__name__)

from google.adk.runners import InMemoryRunner
from google.genai.types import Blob, Content, Part

from trackable.agents.input_processor import (
    InputProcessorOutput,
    convert_extracted_to_order,
    input_processor_agent,
)

# Minimum confidence score required to save an extracted order
MIN_ORDER_CONFIDENCE = 0.9
from trackable.agents.policy_extractor import (
    PolicyExtractorOutput,
    convert_extracted_to_policy,
    policy_extractor_agent,
)
from trackable.db import DatabaseConnection, UnitOfWork
from trackable.models.order import Merchant, SourceType
from trackable.utils.hash import compute_sha256
from trackable.utils.web_scraper import fetch_policy_page

# Create runner for input processor agent
input_processor_runner = InMemoryRunner(
    agent=input_processor_agent, app_name="input-processor"
)
# Create runner for policy extractor agent
policy_extractor_runner = InMemoryRunner(
    agent=policy_extractor_agent, app_name="trackable-policy-extractor"
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

    logger.info("Gmail sync for %s, history_id=%s", user_email, history_id)

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
    logger.info("Parsing email for job_id=%s", job_id)

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
            logger.warning("No orders found in email")
            # Update job status to completed with no orders
            if DatabaseConnection.is_initialized():
                with UnitOfWork() as uow:
                    uow.jobs.mark_completed(job_id, {"status": "no_orders_found"})
                    uow.sources.mark_processed_no_order(source_id)
                    uow.commit()
            return {
                "status": "no_orders_found",
                "job_id": job_id,
                "order_id": None,
            }

        # Get the first extracted order
        extracted = output.orders[0]

        # Reject low-confidence extractions
        if extracted.confidence_score < MIN_ORDER_CONFIDENCE:
            logger.warning(
                "Low confidence (%.2f) for email order from %s, threshold=%.2f",
                extracted.confidence_score,
                extracted.merchant_name,
                MIN_ORDER_CONFIDENCE,
            )
            if DatabaseConnection.is_initialized():
                with UnitOfWork() as uow:
                    uow.jobs.mark_completed(
                        job_id,
                        {
                            "status": "low_confidence",
                            "confidence_score": extracted.confidence_score,
                            "threshold": MIN_ORDER_CONFIDENCE,
                            "merchant_name": extracted.merchant_name,
                        },
                    )
                    uow.sources.mark_processed_no_order(source_id)
                    uow.commit()
            return {
                "status": "low_confidence",
                "job_id": job_id,
                "order_id": None,
                "confidence_score": extracted.confidence_score,
                "threshold": MIN_ORDER_CONFIDENCE,
            }

        # Convert to Order model
        order = convert_extracted_to_order(
            extracted=extracted,
            user_id=user_id,
            source_type=SourceType.EMAIL,
            source_id=source_id,
        )

        logger.info(
            "Extracted order: merchant=%s, confidence=%.2f",
            order.merchant.name,
            order.confidence_score,
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
                logger.info(
                    "Upserting merchant: name=%s, domain=%s",
                    merchant_model.name,
                    merchant_model.domain,
                )
                saved_merchant = uow.merchants.upsert_by_domain(merchant_model)
                logger.info(
                    "Merchant upsert result: id=%s, name=%s, domain=%s",
                    saved_merchant.id,
                    saved_merchant.name,
                    saved_merchant.domain,
                )

                # Update order with persisted merchant ID
                order.merchant.id = saved_merchant.id

                # Upsert order (update existing or create new)
                logger.info(
                    "Upserting order: order_number=%s, merchant_id=%s, user_id=%s",
                    order.order_number,
                    order.merchant.id,
                    order.user_id,
                )
                saved_order, is_new_order = uow.orders.upsert_by_order_number(order)
                logger.info(
                    "Order upsert result: id=%s, order_number=%s, is_new=%s",
                    saved_order.id,
                    saved_order.order_number,
                    is_new_order,
                )

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
        logger.info("Order %s: %s", status, order_id)

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
        logger.exception("Email parsing error: %s", e)
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
    logger.info("Parsing image for job_id=%s", job_id)

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
                    logger.warning(
                        "Duplicate image detected, existing order: %s",
                        existing_order_id,
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
            logger.warning("No orders found in image")
            if DatabaseConnection.is_initialized():
                with UnitOfWork() as uow:
                    uow.jobs.mark_completed(job_id, {"status": "no_orders_found"})
                    uow.sources.mark_processed_no_order(source_id)
                    uow.commit()
            return {
                "status": "no_orders_found",
                "job_id": job_id,
                "order_id": None,
                "is_duplicate": False,
            }

        # Get the first extracted order
        extracted = output.orders[0]

        # Reject low-confidence extractions
        if extracted.confidence_score < MIN_ORDER_CONFIDENCE:
            logger.warning(
                "Low confidence (%.2f) for image order from %s, threshold=%.2f",
                extracted.confidence_score,
                extracted.merchant_name,
                MIN_ORDER_CONFIDENCE,
            )
            if DatabaseConnection.is_initialized():
                with UnitOfWork() as uow:
                    uow.jobs.mark_completed(
                        job_id,
                        {
                            "status": "low_confidence",
                            "confidence_score": extracted.confidence_score,
                            "threshold": MIN_ORDER_CONFIDENCE,
                            "merchant_name": extracted.merchant_name,
                        },
                    )
                    uow.sources.mark_processed_no_order(source_id)
                    uow.commit()
            return {
                "status": "low_confidence",
                "job_id": job_id,
                "order_id": None,
                "confidence_score": extracted.confidence_score,
                "threshold": MIN_ORDER_CONFIDENCE,
                "is_duplicate": False,
            }

        # Convert to Order model
        order = convert_extracted_to_order(
            extracted=extracted,
            user_id=user_id,
            source_type=SourceType.SCREENSHOT,
            source_id=source_id,
        )

        logger.info(
            "Extracted order from image: merchant=%s, confidence=%.2f",
            order.merchant.name,
            order.confidence_score,
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
                logger.info(
                    "Upserting merchant: name=%s, domain=%s",
                    merchant_model.name,
                    merchant_model.domain,
                )
                saved_merchant = uow.merchants.upsert_by_domain(merchant_model)
                logger.info(
                    "Merchant upsert result: id=%s, name=%s, domain=%s",
                    saved_merchant.id,
                    saved_merchant.name,
                    saved_merchant.domain,
                )

                # Update order with persisted merchant ID
                order.merchant.id = saved_merchant.id

                # Upsert order (update existing or create new)
                logger.info(
                    "Upserting order: order_number=%s, merchant_id=%s, user_id=%s",
                    order.order_number,
                    order.merchant.id,
                    order.user_id,
                )
                saved_order, is_new_order = uow.orders.upsert_by_order_number(order)
                logger.info(
                    "Order upsert result: id=%s, order_number=%s, is_new=%s",
                    saved_order.id,
                    saved_order.order_number,
                    is_new_order,
                )

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
        logger.info("Order %s: %s", status, order_id)

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
        logger.exception("Image parsing error: %s", e)
        if DatabaseConnection.is_initialized():
            with UnitOfWork() as uow:
                uow.jobs.mark_failed(job_id, str(e))
                uow.commit()
        raise


async def handle_policy_refresh(
    job_id: str,
    merchant_id: str,
    merchant_domain: str,
    force_refresh: bool = False,
) -> dict:
    """
    Handle policy refresh task.

    Fetches merchant return/exchange policy from their website and extracts
    structured policy information using the policy extractor agent.

    Args:
        job_id: Job ID in database
        merchant_id: Merchant ID to refresh policy for
        merchant_domain: Merchant domain for URL discovery
        force_refresh: Force refresh even if policy hasn't changed (default: False)

    Returns:
        dict: Processing result with policy info
    """
    logger.info(
        "Refreshing policy for merchant_id=%s, domain=%s", merchant_id, merchant_domain
    )

    # Mark job as started
    if DatabaseConnection.is_initialized():
        with UnitOfWork() as uow:
            uow.jobs.mark_started(job_id)
            uow.commit()

    try:
        # Fetch merchant from database
        merchant = None
        if DatabaseConnection.is_initialized():
            with UnitOfWork() as uow:
                merchant = uow.merchants.get_by_id(merchant_id)

        if not merchant or not merchant.policy_urls:
            logger.info("No policy URLs configured for %s", merchant_domain)
            if DatabaseConnection.is_initialized():
                with UnitOfWork() as uow:
                    uow.jobs.mark_completed(
                        job_id,
                        {
                            "status": "no_policy_urls",
                            "merchant_domain": merchant_domain,
                        },
                    )
                    uow.commit()
            return {
                "status": "no_policy_urls",
                "job_id": job_id,
                "merchant_id": merchant_id,
                "merchant_domain": merchant_domain,
            }

        # Try fetching from configured policy URLs
        candidate_urls = merchant.policy_urls
        logger.info("Policy URLs for %s: %s", merchant_domain, candidate_urls)

        raw_html = None
        clean_text = None
        source_url = None

        for url in candidate_urls:
            try:
                logger.info("Fetching from %s", url)
                raw_html, clean_text = fetch_policy_page(url, timeout=10)
                source_url = url
                logger.info("Successfully fetched from %s", url)
                break
            except Exception as e:
                logger.warning("Failed to fetch from %s: %s", url, e)
                continue

        if not raw_html or not clean_text or not source_url:
            logger.info("Failed to fetch from any policy URL for %s", merchant_domain)
            if DatabaseConnection.is_initialized():
                with UnitOfWork() as uow:
                    uow.jobs.mark_completed(
                        job_id,
                        {"status": "fetch_failed", "attempted_urls": candidate_urls},
                    )
                    uow.commit()
            return {
                "status": "fetch_failed",
                "job_id": job_id,
                "merchant_id": merchant_id,
                "attempted_urls": candidate_urls,
            }

        # Check if content has changed using hash (skip if force_refresh)
        if not force_refresh and DatabaseConnection.is_initialized():
            with UnitOfWork() as uow:
                # Get existing policy for this merchant (check return_policy data)
                existing_policy = uow.policies.get_return_policy_by_merchant(
                    merchant_id, "US"
                )
                if existing_policy and existing_policy.raw_text:
                    existing_hash = compute_sha256(existing_policy.raw_text.encode())
                    new_hash = compute_sha256(clean_text.encode())
                    if existing_hash == new_hash:
                        logger.info("Policy unchanged (hash match), skipping update")
                        uow.jobs.mark_completed(
                            job_id,
                            {
                                "status": "unchanged",
                                "source_url": source_url,
                                "policy_id": existing_policy.id,
                            },
                        )
                        uow.commit()
                        return {
                            "status": "unchanged",
                            "job_id": job_id,
                            "merchant_id": merchant_id,
                            "source_url": source_url,
                            "policy_id": existing_policy.id,
                        }

        # Extract policy using policy extractor agent
        logger.info("Extracting policy with agent")

        # Create prompt for policy extractor
        prompt = f"""Extract return and exchange policy information from this HTML content.

Merchant: {merchant.name if merchant else merchant_domain}
Domain: {merchant_domain}

HTML Content:
{clean_text[:10000]}  # Limit to first 10k chars to avoid token limits

Extract all policy details including return windows, conditions, refund methods, shipping responsibility, and exclusions."""

        content = Content(parts=[Part(text=prompt)])

        # Run policy extractor agent
        session = await policy_extractor_runner.session_service.create_session(
            app_name=policy_extractor_runner.app_name,
            user_id="system",  # System job, no user
        )

        # Collect agent response
        result_text = ""
        async for event in policy_extractor_runner.run_async(
            user_id="system",
            session_id=session.id,
            new_message=content,
        ):
            if event.content and event.content.parts:
                for part in event.content.parts:
                    if part.text:
                        result_text = part.text

        if not result_text:
            raise ValueError("No result from policy extractor agent")

        # Parse the JSON response
        result = json.loads(result_text)

        if isinstance(result, dict):
            output = PolicyExtractorOutput(**result)
        else:
            output = result

        if not output.policies or len(output.policies) == 0:
            logger.warning("No policies found in content")
            if DatabaseConnection.is_initialized():
                with UnitOfWork() as uow:
                    uow.jobs.mark_completed(
                        job_id,
                        {"status": "no_policies_found", "source_url": source_url},
                    )
                    uow.commit()
            return {
                "status": "no_policies_found",
                "job_id": job_id,
                "merchant_id": merchant_id,
                "source_url": source_url,
            }

        # Convert extracted policies to Policy models and save
        saved_policy_ids = []
        policy_details = []

        if DatabaseConnection.is_initialized():
            with UnitOfWork() as uow:
                for extracted in output.policies:
                    policy = convert_extracted_to_policy(
                        extracted=extracted,
                        merchant_id=merchant_id,
                        source_url=source_url,
                        raw_text=clean_text,
                        country_code="US",
                    )

                    # Upsert policy (insert or update)
                    saved_policy = uow.policies.upsert_by_merchant_and_type(policy)
                    saved_policy_ids.append(saved_policy.id)

                    policy_details.append(
                        {
                            "policy_id": saved_policy.id,
                            "policy_type": saved_policy.policy_type.value,
                            "confidence_score": saved_policy.confidence_score,
                            "needs_verification": saved_policy.needs_verification,
                        }
                    )

                    logger.info(
                        "Saved policy: type=%s, confidence=%s",
                        saved_policy.policy_type.value,
                        saved_policy.confidence_score,
                    )

                # Mark job as completed
                uow.jobs.mark_completed(
                    job_id,
                    {
                        "status": "success",
                        "source_url": source_url,
                        "policies_saved": len(saved_policy_ids),
                        "policy_ids": saved_policy_ids,
                        "policy_details": policy_details,
                        "overall_confidence": output.overall_confidence,
                    },
                )
                uow.commit()

        logger.info(
            "Policy refresh completed: %d policies saved", len(saved_policy_ids)
        )

        return {
            "status": "success",
            "job_id": job_id,
            "merchant_id": merchant_id,
            "source_url": source_url,
            "policies_saved": len(saved_policy_ids),
            "policy_ids": saved_policy_ids,
            "policy_details": policy_details,
            "overall_confidence": output.overall_confidence,
        }

    except Exception as e:
        logger.exception("Policy refresh error: %s", e)
        if DatabaseConnection.is_initialized():
            with UnitOfWork() as uow:
                uow.jobs.mark_failed(job_id, str(e))
                uow.commit()
        raise

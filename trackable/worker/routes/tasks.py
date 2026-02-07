"""
Cloud Tasks endpoint handlers for async job processing.

Cloud Tasks sends HTTP POST requests to these endpoints with task payloads.
"""

import base64

from fastapi import APIRouter, HTTPException, Request

from trackable.models.task import (
    GmailSyncTask,
    ParseEmailTask,
    ParseImageTask,
    PolicyRefreshTask,
)
from trackable.worker.handlers import (
    handle_gmail_sync,
    handle_parse_email,
    handle_parse_image,
    handle_policy_refresh,
)

router = APIRouter()


@router.post("/gmail-sync")
async def gmail_sync_task(task: GmailSyncTask):
    """
    Process Gmail sync task.

    Cloud Tasks triggers this endpoint to sync new emails from Gmail
    using the Gmail API's history sync mechanism.

    Args:
        task: Gmail sync task payload

    Returns:
        dict: Processing result with order counts

    Flow:
        1. Fetch new emails since last history_id
        2. Filter for order confirmation emails
        3. Parse each email using input_processor_agent
        4. Create/update orders in database
        5. Update user's last_history_id
    """
    try:
        print(f"📧 Processing Gmail sync task for {task.user_email}")

        result = await handle_gmail_sync(
            user_email=task.user_email,
            user_id=task.user_id,
            history_id=task.history_id,
        )

        print(
            f"✅ Gmail sync completed: {result['orders_created']} created, {result['orders_updated']} updated"
        )

        return {
            "status": "success",
            "user_email": task.user_email,
            "result": result,
        }

    except Exception as e:
        print(f"❌ Gmail sync failed: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Gmail sync failed: {str(e)}",
        )


@router.post("/parse-email")
async def parse_email_task(task: ParseEmailTask):
    """
    Process email parsing task.

    Cloud Tasks triggers this endpoint when a user manually submits
    an email for order parsing.

    Args:
        task: Email parsing task payload

    Returns:
        dict: Processing result with order info

    Flow:
        1. Load job from database
        2. Parse email content using input_processor_agent
        3. Create/update order in database
        4. Mark job as completed
    """
    try:
        print(f"📨 Processing parse email task: job_id={task.job_id}")

        result = await handle_parse_email(
            job_id=task.job_id,
            user_id=task.user_id,
            source_id=task.source_id,
            email_content=task.email_content,
        )

        print(f"✅ Email parsing completed: order_id={result.get('order_id')}")

        return {
            "status": "success",
            "job_id": task.job_id,
            "result": result,
        }

    except Exception as e:
        print(f"❌ Email parsing failed: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Email parsing failed: {str(e)}",
        )


@router.post("/parse-image")
async def parse_image_task(task: ParseImageTask):
    """
    Process image/screenshot parsing task.

    Cloud Tasks triggers this endpoint when a user uploads
    a screenshot of an order confirmation.

    Args:
        task: Image parsing task payload

    Returns:
        dict: Processing result with order info

    Flow:
        1. Load job from database
        2. Download image if URL provided, or decode base64 data
        3. Check for duplicate images using perceptual hashing
        4. Parse image using input_processor_agent (with vision)
        5. Create/update order in database
        6. Mark job as completed
    """
    try:
        print(f"🖼️  Processing parse image task: job_id={task.job_id}")

        image_bytes = base64.b64decode(task.image_data) if task.image_data else None

        result = await handle_parse_image(
            job_id=task.job_id,
            user_id=task.user_id,
            source_id=task.source_id,
            image_url=task.image_url,
            image_data=image_bytes,
        )

        if result.get("is_duplicate"):
            print(
                f"⚠️  Image is duplicate of order_id={result.get('existing_order_id')}"
            )
        else:
            print(f"✅ Image parsing completed: order_id={result.get('order_id')}")

        return {
            "status": "success",
            "job_id": task.job_id,
            "result": result,
        }

    except Exception as e:
        print(f"❌ Image parsing failed: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Image parsing failed: {str(e)}",
        )


@router.post("/policy-refresh")
async def policy_refresh_task(task: PolicyRefreshTask):
    """
    Process policy refresh task.

    Cloud Tasks triggers this endpoint to refresh merchant return/exchange policies.
    Scheduled periodically by Cloud Scheduler or triggered manually.

    Args:
        task: Policy refresh task payload

    Returns:
        dict: Processing result with policy info

    Flow:
        1. Create job record for tracking
        2. Fetch merchant from database
        3. Discover policy URL from merchant domain/support_url
        4. Fetch policy page HTML
        5. Check if content changed (hash comparison)
        6. Extract policy using policy_extractor_agent
        7. Save policy to database (upsert)
        8. Mark job as completed
    """
    try:
        print(
            f"🔄 Processing policy refresh task: merchant_id={task.merchant_id}, "
            f"domain={task.merchant_domain}"
        )

        # Create job for this policy refresh
        from trackable.db import DatabaseConnection, UnitOfWork
        from trackable.models.job import Job, JobType

        job_id = None
        if DatabaseConnection.is_initialized():
            with UnitOfWork() as uow:
                job = Job(
                    id="",  # Will be generated
                    job_type=JobType.POLICY_REFRESH,
                    user_id=None,  # System job
                    source_id=None,
                    metadata={
                        "merchant_id": task.merchant_id,
                        "merchant_domain": task.merchant_domain,
                        "force_refresh": task.force_refresh,
                    },
                )
                created_job = uow.jobs.create(job)
                job_id = created_job.id
                uow.commit()

        result = await handle_policy_refresh(
            job_id=job_id,
            merchant_id=task.merchant_id,
            merchant_domain=task.merchant_domain,
            force_refresh=task.force_refresh,
        )

        print(f"✅ Policy refresh completed: status={result.get('status')}")

        return {
            "status": "success",
            "merchant_id": task.merchant_id,
            "result": result,
        }

    except Exception as e:
        print(f"❌ Policy refresh failed: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Policy refresh failed: {str(e)}",
        )


# Test endpoint for local development
@router.post("/test")
async def test_task(request: Request):
    """
    Test endpoint for local development.

    Accepts arbitrary JSON payload for testing task handlers.
    """
    payload = await request.json()
    task_type = payload.get("task_type")

    print(f"🧪 Test task: {task_type}")

    if task_type == "gmail_sync":
        return await gmail_sync_task(GmailSyncTask(**payload))
    elif task_type == "parse_email":
        return await parse_email_task(ParseEmailTask(**payload))
    elif task_type == "parse_image":
        return await parse_image_task(ParseImageTask(**payload))
    else:
        raise HTTPException(status_code=400, detail=f"Unknown task type: {task_type}")

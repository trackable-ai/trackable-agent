"""
Pub/Sub handlers for Gmail notifications and scheduled tasks.

These endpoints receive push messages from Pub/Sub:
- Gmail notification handler: Triggered when users receive new emails
- Policy refresh handler: Triggered by Cloud Scheduler for periodic policy updates
"""

import base64
import json
import logging
from datetime import datetime, timezone
from uuid import uuid4

from fastapi import APIRouter, HTTPException

from trackable.api.cloud_tasks import create_gmail_sync_task, create_policy_refresh_task
from trackable.db import DatabaseConnection, UnitOfWork
from trackable.models.job import Job, JobStatus, JobType
from trackable.models.pubsub import (
    GmailNotificationPayload,
    PolicyRefreshPayload,
    PubSubPushMessage,
    PubSubResponse,
)

router = APIRouter()
logger = logging.getLogger(__name__)


def _decode_pubsub_data(data: str) -> dict:
    """
    Decode base64-encoded Pub/Sub message data.

    Args:
        data: Base64-encoded JSON string

    Returns:
        Decoded JSON as dict

    Raises:
        ValueError: If data cannot be decoded
    """
    try:
        decoded_bytes = base64.b64decode(data)
        return json.loads(decoded_bytes.decode("utf-8"))
    except Exception as e:
        raise ValueError(f"Failed to decode Pub/Sub data: {e}")


@router.post(
    "/pubsub/gmail",
    response_model=PubSubResponse,
    operation_id="handleGmailNotification",
)
async def handle_gmail_notification(message: PubSubPushMessage) -> PubSubResponse:
    """
    Handle Gmail Pub/Sub push notifications.

    When Gmail detects new emails for a watched mailbox, it sends a notification
    containing the email address and history ID. This handler:
    1. Decodes the notification payload
    2. Looks up the user by their Gmail address
    3. Creates a Cloud Task to sync the user's Gmail

    Args:
        message: Pub/Sub push message envelope

    Returns:
        PubSubResponse with processing status
    """
    try:
        # Decode the notification payload
        payload_data = _decode_pubsub_data(message.message.data)
        payload = GmailNotificationPayload.model_validate(payload_data)
    except Exception as e:
        logger.error(f"Failed to parse Gmail notification: {e}")
        raise HTTPException(
            status_code=400,
            detail=f"Invalid Gmail notification payload: {e}",
        )

    logger.info(
        f"Received Gmail notification for {payload.emailAddress}, "
        f"historyId={payload.historyId}"
    )

    # Look up user by Gmail address
    if not DatabaseConnection.is_initialized():
        logger.warning("Database not initialized, skipping Gmail sync")
        return PubSubResponse(
            status="skipped",
            message="Database not configured",
            tasks_created=0,
            details={"email": payload.emailAddress},
        )

    now = datetime.now(timezone.utc)
    job_id = str(uuid4())
    user_id: str | None = None

    with UnitOfWork() as uow:
        oauth_token = uow.oauth_tokens.get_by_provider_email(
            provider="gmail", provider_email=payload.emailAddress
        )

        if oauth_token is None:
            logger.warning(f"No OAuth token found for {payload.emailAddress}")
            return PubSubResponse(
                status="ignored",
                message="User not found or Gmail not connected",
                tasks_created=0,
                details={"email": payload.emailAddress},
            )

        user_id = oauth_token.user_id

        # Create Job record to track the sync
        job = Job(
            id=job_id,
            user_id=user_id,
            job_type=JobType.GMAIL_SYNC,
            status=JobStatus.QUEUED,
            input_data={
                "email": payload.emailAddress,
                "history_id": payload.historyId,
                "message_id": message.message.messageId,
            },
            queued_at=now,
            created_at=now,
            updated_at=now,
        )
        uow.jobs.create(job)
        uow.commit()

    # Create Cloud Task for Gmail sync
    try:
        task_name = create_gmail_sync_task(
            user_id=user_id,
            user_email=payload.emailAddress,
            history_id=payload.historyId,
        )
        logger.info(f"Created Gmail sync task: {task_name}")

        # Update job with task name
        with UnitOfWork() as uow:
            uow.jobs.update_by_id(job_id, task_name=task_name)
            uow.commit()

        return PubSubResponse(
            status="queued",
            message="Gmail sync task created",
            tasks_created=1,
            details={
                "job_id": job_id,
                "email": payload.emailAddress,
                "history_id": payload.historyId,
                "task_name": task_name,
            },
        )
    except Exception as e:
        logger.error(f"Failed to create Gmail sync task: {e}")
        # Mark job as failed
        with UnitOfWork() as uow:
            uow.jobs.mark_failed(job_id, str(e))
            uow.commit()
        raise HTTPException(
            status_code=500,
            detail=f"Failed to create Gmail sync task: {e}",
        )


@router.post(
    "/pubsub/policy", response_model=PubSubResponse, operation_id="handlePolicyRefresh"
)
async def handle_policy_refresh(message: PubSubPushMessage) -> PubSubResponse:
    """
    Handle policy refresh Pub/Sub trigger from Cloud Scheduler.

    This endpoint is called periodically to refresh merchant return policies.
    It creates Cloud Tasks for each merchant that needs a policy refresh.

    Args:
        message: Pub/Sub push message envelope

    Returns:
        PubSubResponse with processing status
    """
    try:
        # Decode payload (may be empty or contain configuration)
        if message.message.data:
            payload_data = _decode_pubsub_data(message.message.data)
            payload = PolicyRefreshPayload.model_validate(payload_data)
        else:
            # Default: refresh all merchants
            payload = PolicyRefreshPayload()
    except Exception as e:
        logger.warning(f"Failed to parse policy refresh payload, using defaults: {e}")
        payload = PolicyRefreshPayload()

    logger.info(
        f"Received policy refresh trigger: "
        f"refresh_all={payload.refresh_all}, "
        f"merchant_ids={payload.merchant_ids}"
    )

    # Get merchants to refresh
    if not DatabaseConnection.is_initialized():
        logger.warning("Database not initialized, skipping policy refresh")
        return PubSubResponse(
            status="skipped",
            message="Database not configured",
            tasks_created=0,
        )

    now = datetime.now(timezone.utc)
    merchants_to_refresh = []

    with UnitOfWork() as uow:
        if payload.refresh_all:
            # Get all merchants
            merchants_to_refresh = uow.merchants.list_all(limit=1000)
        else:
            # Get specific merchants by ID
            for merchant_id in payload.merchant_ids:
                merchant = uow.merchants.get_by_id(merchant_id)
                if merchant:
                    merchants_to_refresh.append(merchant)

    if not merchants_to_refresh:
        logger.info("No merchants found to refresh")
        return PubSubResponse(
            status="completed",
            message="No merchants to refresh",
            tasks_created=0,
        )

    # Create Cloud Tasks and Job records for each merchant
    tasks_created = 0
    task_errors = []
    job_ids = []

    for merchant in merchants_to_refresh:
        if merchant.domain is None:
            continue  # Skip merchants without domain

        job_id = str(uuid4())

        try:
            # Create Job record first
            with UnitOfWork() as uow:
                job = Job(
                    id=job_id,
                    user_id=None,  # System job, no user
                    job_type=JobType.POLICY_REFRESH,
                    status=JobStatus.QUEUED,
                    input_data={
                        "merchant_id": merchant.id,
                        "merchant_domain": merchant.domain,
                    },
                    queued_at=now,
                    created_at=now,
                    updated_at=now,
                )
                uow.jobs.create(job)
                uow.commit()

            # Create Cloud Task
            task_name = create_policy_refresh_task(
                merchant_id=merchant.id,
                merchant_domain=merchant.domain,
                force_refresh=False,
                delay_seconds=tasks_created * 2,  # Stagger tasks by 2 seconds
            )

            # Update job with task name
            with UnitOfWork() as uow:
                uow.jobs.update_by_id(job_id, task_name=task_name)
                uow.commit()

            tasks_created += 1
            job_ids.append(job_id)
            logger.info(
                f"Created policy refresh task for {merchant.domain}: {task_name}"
            )
        except Exception as e:
            logger.error(f"Failed to create task for {merchant.domain}: {e}")
            # Mark job as failed if it was created
            try:
                with UnitOfWork() as uow:
                    uow.jobs.mark_failed(job_id, str(e))
                    uow.commit()
            except Exception:
                pass  # Job might not have been created yet
            task_errors.append({"merchant": merchant.domain, "error": str(e)})

    return PubSubResponse(
        status="queued" if tasks_created > 0 else "failed",
        message=f"Created {tasks_created} policy refresh tasks",
        tasks_created=tasks_created,
        details={
            "merchants_found": len(merchants_to_refresh),
            "job_ids": job_ids if job_ids else None,
            "errors": task_errors if task_errors else None,
        },
    )

"""
Ingest API routes for manual email/screenshot submission.

These endpoints allow users to manually submit emails and screenshots
for order extraction. Each submission creates a job that is processed
asynchronously by the Worker service via Cloud Tasks.
"""

import base64
from datetime import datetime, timezone
from uuid import uuid4

from fastapi import APIRouter, HTTPException

from trackable.api.cloud_tasks import create_parse_email_task, create_parse_image_task
from trackable.db import DatabaseConnection, UnitOfWork
from trackable.models.ingest import (
    IngestEmailRequest,
    IngestImageRequest,
    IngestResponse,
)
from trackable.models.job import Job, JobStatus, JobType
from trackable.models.order import SourceType
from trackable.models.source import Source
from trackable.utils.hash import compute_sha256

router = APIRouter()


@router.post("/ingest/email", response_model=IngestResponse)
async def ingest_email(
    request: IngestEmailRequest,
    user_id: str = "user_default",  # TODO: Get from authentication
) -> IngestResponse:
    """
    Submit an email for order extraction.

    Creates a job and Cloud Task to process the email asynchronously.
    The email content will be parsed by the input processor agent
    to extract order information.

    Args:
        request: Email content and optional metadata
        user_id: User ID (will come from auth in production)

    Returns:
        IngestResponse with job_id for tracking
    """
    now = datetime.now(timezone.utc)
    job_id = str(uuid4())
    source_id = str(uuid4())

    # Save Job and Source to database
    if DatabaseConnection.is_initialized():
        with UnitOfWork() as uow:
            job = Job(
                id=job_id,
                user_id=user_id,
                job_type=JobType.PARSE_EMAIL,
                status=JobStatus.QUEUED,
                input_data={
                    "source_id": source_id,
                    "email_subject": request.email_subject,
                    "email_from": request.email_from,
                },
                queued_at=now,
                created_at=now,
                updated_at=now,
            )
            uow.jobs.create(job)

            source = Source(
                id=source_id,
                user_id=user_id,
                source_type=SourceType.EMAIL,
                email_subject=request.email_subject,
                email_from=request.email_from,
                email_date=now,
                processed=False,
                created_at=now,
                updated_at=now,
            )
            uow.sources.create(source)
            uow.commit()

    try:
        # Create Cloud Task to process the email
        task_name = create_parse_email_task(
            job_id=job_id,
            user_id=user_id,
            source_id=source_id,
            email_content=request.email_content,
        )
        print(f"Created task: {task_name}")

        # Update job with task name
        if DatabaseConnection.is_initialized():
            with UnitOfWork() as uow:
                uow.jobs.update_by_id(job_id, task_name=task_name)
                uow.commit()

    except Exception as e:
        if DatabaseConnection.is_initialized():
            with UnitOfWork() as uow:
                uow.jobs.mark_failed(job_id, str(e))
                uow.commit()
        raise HTTPException(
            status_code=500,
            detail=f"Failed to create processing task: {str(e)}",
        )

    return IngestResponse(
        job_id=job_id,
        source_id=source_id,
        status="queued",
        message="Email submitted for processing. Use the job_id to check status.",
    )


@router.post("/ingest/image", response_model=IngestResponse)
async def ingest_image(
    request: IngestImageRequest,
    user_id: str = "user_default",  # TODO: Get from authentication
) -> IngestResponse:
    """
    Submit a screenshot for order extraction.

    Creates a job and Cloud Task to process the image asynchronously.
    The image will be analyzed by the input processor agent (with vision)
    to extract order information.

    Args:
        request: Base64 encoded image data and optional metadata
        user_id: User ID (will come from auth in production)

    Returns:
        IngestResponse with job_id for tracking
    """
    now = datetime.now(timezone.utc)
    job_id = str(uuid4())
    source_id = str(uuid4())

    # Decode image and compute hash for duplicate detection
    try:
        image_bytes = base64.b64decode(request.image_data)
        image_hash = compute_sha256(image_bytes)
    except Exception as e:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid base64 image data: {str(e)}",
        )

    # Check for duplicate and save Job/Source to database
    if DatabaseConnection.is_initialized():
        with UnitOfWork() as uow:
            # Check for duplicate image
            existing_source = uow.sources.find_by_image_hash(user_id, image_hash)
            if existing_source and existing_source.order_id:
                return IngestResponse(
                    job_id="",
                    source_id=existing_source.id,
                    status="duplicate",
                    message=f"Duplicate image detected. Existing order: {existing_source.order_id}",
                )

            # Create Job record
            job = Job(
                id=job_id,
                user_id=user_id,
                job_type=JobType.PARSE_IMAGE,
                status=JobStatus.QUEUED,
                input_data={
                    "source_id": source_id,
                    "filename": request.filename,
                    "image_hash": image_hash,
                },
                queued_at=now,
                created_at=now,
                updated_at=now,
            )
            uow.jobs.create(job)

            # Create Source record with image hash
            source = Source(
                id=source_id,
                user_id=user_id,
                source_type=SourceType.SCREENSHOT,
                image_hash=image_hash,
                processed=False,
                created_at=now,
                updated_at=now,
            )
            uow.sources.create(source)
            uow.commit()

    try:
        # Create Cloud Task to process the image
        task_name = create_parse_image_task(
            job_id=job_id,
            user_id=user_id,
            source_id=source_id,
            image_data=request.image_data,
        )
        print(f"Created task: {task_name}")

        # Update job with task name
        if DatabaseConnection.is_initialized():
            with UnitOfWork() as uow:
                uow.jobs.update_by_id(job_id, task_name=task_name)
                uow.commit()

    except Exception as e:
        if DatabaseConnection.is_initialized():
            with UnitOfWork() as uow:
                uow.jobs.mark_failed(job_id, str(e))
                uow.commit()
        raise HTTPException(
            status_code=500,
            detail=f"Failed to create processing task: {str(e)}",
        )

    return IngestResponse(
        job_id=job_id,
        source_id=source_id,
        status="queued",
        message="Image submitted for processing. Use the job_id to check status.",
    )

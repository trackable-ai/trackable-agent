"""
Ingest API routes for manual email/screenshot submission.

These endpoints allow users to manually submit emails and screenshots
for order extraction. Each submission creates a job that is processed
asynchronously by the Worker service via Cloud Tasks.
"""

import base64
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Literal
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException

from trackable.api.auth import get_user_id
from trackable.api.cloud_tasks import create_parse_email_task, create_parse_image_task
from trackable.db import DatabaseConnection, UnitOfWork
from trackable.models.ingest import (
    BatchItemResult,
    BatchItemStatus,
    IngestBatchEmailRequest,
    IngestBatchImageRequest,
    IngestBatchResponse,
    IngestEmailRequest,
    IngestImageRequest,
    IngestResponse,
)
from trackable.models.job import Job, JobStatus, JobType
from trackable.models.order import SourceType
from trackable.models.source import Source
from trackable.utils.hash import compute_sha256

router = APIRouter()


@dataclass
class IngestResult:
    """Internal result from processing a single ingest item."""

    status: Literal["queued", "duplicate", "failed"]
    job_id: str | None = None
    source_id: str | None = None
    error: str | None = None
    message: str | None = None


async def _process_single_email(
    email_content: str,
    email_subject: str | None,
    email_from: str | None,
    user_id: str,
) -> IngestResult:
    """
    Process a single email submission.

    Creates Job/Source records and Cloud Task.
    Returns IngestResult with status and IDs.
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
                    "email_subject": email_subject,
                    "email_from": email_from,
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
                email_subject=email_subject,
                email_from=email_from,
                email_date=now,
                processed=False,
                created_at=now,
                updated_at=now,
            )
            uow.sources.create(source)
            uow.commit()

    try:
        task_name = create_parse_email_task(
            job_id=job_id,
            user_id=user_id,
            source_id=source_id,
            email_content=email_content,
        )
        print(f"Created task: {task_name}")

        if DatabaseConnection.is_initialized():
            with UnitOfWork() as uow:
                uow.jobs.update_by_id(job_id, task_name=task_name)
                uow.commit()

        return IngestResult(
            status="queued",
            job_id=job_id,
            source_id=source_id,
            message="Email submitted for processing.",
        )

    except Exception as e:
        if DatabaseConnection.is_initialized():
            with UnitOfWork() as uow:
                uow.jobs.mark_failed(job_id, str(e))
                uow.commit()
        return IngestResult(
            status="failed",
            job_id=job_id,
            source_id=source_id,
            error=f"Failed to create processing task: {str(e)}",
        )


async def _process_single_image(
    image_data: str,
    filename: str | None,
    user_id: str,
) -> IngestResult:
    """
    Process a single image submission.

    Decodes image, checks for duplicates, creates Job/Source records and Cloud Task.
    Returns IngestResult with status and IDs.
    """
    now = datetime.now(timezone.utc)
    job_id = str(uuid4())
    source_id = str(uuid4())

    # Decode image and compute hash
    try:
        image_bytes = base64.b64decode(image_data)
        image_hash = compute_sha256(image_bytes)
    except Exception as e:
        return IngestResult(
            status="failed",
            error=f"Invalid base64 image data: {str(e)}",
        )

    # Check for duplicate and create records
    if DatabaseConnection.is_initialized():
        with UnitOfWork() as uow:
            existing_source = uow.sources.find_by_image_hash(user_id, image_hash)
            if existing_source and existing_source.order_id:
                return IngestResult(
                    status="duplicate",
                    source_id=existing_source.id,
                    message=f"Duplicate image detected. Existing order: {existing_source.order_id}",
                )

            job = Job(
                id=job_id,
                user_id=user_id,
                job_type=JobType.PARSE_IMAGE,
                status=JobStatus.QUEUED,
                input_data={
                    "source_id": source_id,
                    "filename": filename,
                    "image_hash": image_hash,
                },
                queued_at=now,
                created_at=now,
                updated_at=now,
            )
            uow.jobs.create(job)

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
        task_name = create_parse_image_task(
            job_id=job_id,
            user_id=user_id,
            source_id=source_id,
            image_data=image_data,
        )
        print(f"Created task: {task_name}")

        if DatabaseConnection.is_initialized():
            with UnitOfWork() as uow:
                uow.jobs.update_by_id(job_id, task_name=task_name)
                uow.commit()

        return IngestResult(
            status="queued",
            job_id=job_id,
            source_id=source_id,
            message="Image submitted for processing.",
        )

    except Exception as e:
        if DatabaseConnection.is_initialized():
            with UnitOfWork() as uow:
                uow.jobs.mark_failed(job_id, str(e))
                uow.commit()
        return IngestResult(
            status="failed",
            job_id=job_id,
            source_id=source_id,
            error=f"Failed to create processing task: {str(e)}",
        )


@router.post("/ingest/email", response_model=IngestResponse)
async def ingest_email(
    request: IngestEmailRequest,
    user_id: str = Depends(get_user_id),
) -> IngestResponse:
    """
    Submit an email for order extraction.

    Creates a job and Cloud Task to process the email asynchronously.
    The email content will be parsed by the input processor agent
    to extract order information.

    Args:
        request: Email content and optional metadata
        user_id: User ID from X-User-ID header

    Returns:
        IngestResponse with job_id for tracking
    """
    result = await _process_single_email(
        email_content=request.email_content,
        email_subject=request.email_subject,
        email_from=request.email_from,
        user_id=user_id,
    )

    if result.status == "failed":
        raise HTTPException(status_code=500, detail=result.error)

    return IngestResponse(
        job_id=result.job_id or "",
        source_id=result.source_id or "",
        status=result.status,
        message=result.message
        or "Email submitted for processing. Use the job_id to check status.",
    )


@router.post("/ingest/image", response_model=IngestResponse)
async def ingest_image(
    request: IngestImageRequest,
    user_id: str = Depends(get_user_id),
) -> IngestResponse:
    """
    Submit a screenshot for order extraction.

    Creates a job and Cloud Task to process the image asynchronously.
    The image will be analyzed by the input processor agent (with vision)
    to extract order information.

    Args:
        request: Base64 encoded image data and optional metadata
        user_id: User ID from X-User-ID header

    Returns:
        IngestResponse with job_id for tracking
    """
    result = await _process_single_image(
        image_data=request.image_data,
        filename=request.filename,
        user_id=user_id,
    )

    if result.status == "failed":
        # For invalid base64, return 400; for task creation failures, return 500
        status_code = 400 if "Invalid base64" in (result.error or "") else 500
        raise HTTPException(status_code=status_code, detail=result.error)

    return IngestResponse(
        job_id=result.job_id or "",
        source_id=result.source_id or "",
        status=result.status,
        message=result.message
        or "Image submitted for processing. Use the job_id to check status.",
    )


@router.post("/ingest/email/batch", response_model=IngestBatchResponse)
async def ingest_email_batch(
    request: IngestBatchEmailRequest,
    user_id: str = Depends(get_user_id),
) -> IngestBatchResponse:
    """
    Submit multiple emails for order extraction.

    Processes all emails in the batch, even if some fail.
    Each email is processed independently with its own database transaction.

    Args:
        request: List of emails to process (max 50)
        user_id: User ID from X-User-ID header

    Returns:
        IngestBatchResponse with individual results for each item
    """
    results: list[BatchItemResult] = []
    succeeded = 0
    failed = 0

    for index, item in enumerate(request.items):
        result = await _process_single_email(
            email_content=item.email_content,
            email_subject=item.email_subject,
            email_from=item.email_from,
            user_id=user_id,
        )

        if result.status == "queued":
            results.append(
                BatchItemResult(
                    index=index,
                    status=BatchItemStatus.SUCCESS,
                    job_id=result.job_id,
                    source_id=result.source_id,
                    message=result.message,
                )
            )
            succeeded += 1
        else:
            results.append(
                BatchItemResult(
                    index=index,
                    status=BatchItemStatus.FAILED,
                    job_id=result.job_id,
                    source_id=result.source_id,
                    error=result.error,
                )
            )
            failed += 1

    return IngestBatchResponse(
        total=len(request.items),
        succeeded=succeeded,
        duplicates=0,  # Emails don't have duplicate detection
        failed=failed,
        results=results,
    )


@router.post("/ingest/image/batch", response_model=IngestBatchResponse)
async def ingest_image_batch(
    request: IngestBatchImageRequest,
    user_id: str = Depends(get_user_id),
) -> IngestBatchResponse:
    """
    Submit multiple screenshots for order extraction.

    Processes all images in the batch, even if some fail or are duplicates.
    Each image is processed independently with its own database transaction.

    Args:
        request: List of images to process (max 50)
        user_id: User ID from X-User-ID header

    Returns:
        IngestBatchResponse with individual results for each item
    """
    results: list[BatchItemResult] = []
    succeeded = 0
    duplicates = 0
    failed = 0

    for index, item in enumerate(request.items):
        result = await _process_single_image(
            image_data=item.image_data,
            filename=item.filename,
            user_id=user_id,
        )

        if result.status == "queued":
            results.append(
                BatchItemResult(
                    index=index,
                    status=BatchItemStatus.SUCCESS,
                    job_id=result.job_id,
                    source_id=result.source_id,
                    message=result.message,
                )
            )
            succeeded += 1
        elif result.status == "duplicate":
            results.append(
                BatchItemResult(
                    index=index,
                    status=BatchItemStatus.DUPLICATE,
                    source_id=result.source_id,
                    message=result.message,
                )
            )
            duplicates += 1
        else:
            results.append(
                BatchItemResult(
                    index=index,
                    status=BatchItemStatus.FAILED,
                    job_id=result.job_id,
                    source_id=result.source_id,
                    error=result.error,
                )
            )
            failed += 1

    return IngestBatchResponse(
        total=len(request.items),
        succeeded=succeeded,
        duplicates=duplicates,
        failed=failed,
        results=results,
    )

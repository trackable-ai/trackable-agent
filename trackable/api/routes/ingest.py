"""
Ingest API routes for manual email/screenshot submission.

These endpoints allow users to manually submit emails and screenshots
for order extraction. Each submission creates a job that is processed
asynchronously by the Worker service via Cloud Tasks.
"""

import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException

from trackable.api.cloud_tasks import create_parse_email_task, create_parse_image_task
from trackable.models.ingest import (
    IngestEmailRequest,
    IngestImageRequest,
    IngestResponse,
)

router = APIRouter()


def generate_id(prefix: str) -> str:
    """Generate a unique ID with a prefix."""
    return f"{prefix}_{uuid.uuid4().hex[:12]}"


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
    # Generate IDs for job and source
    job_id = generate_id("job")
    source_id = generate_id("src")

    # TODO: Save Job to database with status "queued"
    # TODO: Save Source to database

    try:
        # Create Cloud Task to process the email
        task_name = create_parse_email_task(
            job_id=job_id,
            user_id=user_id,
            source_id=source_id,
            email_content=request.email_content,
        )
        print(f"Created task: {task_name}")

    except Exception as e:
        # TODO: Update job status to "failed" in database
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
    # Generate IDs for job and source
    job_id = generate_id("job")
    source_id = generate_id("src")

    # TODO: Save Job to database with status "queued"
    # TODO: Save Source to database with image_hash for duplicate detection
    # TODO: Check for duplicate images using perceptual hash

    try:
        # Create Cloud Task to process the image
        task_name = create_parse_image_task(
            job_id=job_id,
            user_id=user_id,
            source_id=source_id,
            image_data=request.image_data,
        )
        print(f"Created task: {task_name}")

    except Exception as e:
        # TODO: Update job status to "failed" in database
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

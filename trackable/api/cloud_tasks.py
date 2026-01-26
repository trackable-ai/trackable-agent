"""
Cloud Tasks client for creating async processing tasks.

This module provides functions to create Cloud Tasks that target
the Worker service endpoints for email/image parsing.
"""

import json
import os
from typing import Any

from google.cloud import tasks_v2
from google.protobuf import timestamp_pb2

from trackable.models.task import ParseEmailTask, ParseImageTask
from trackable.utils.gcp import get_service_account_email, get_worker_service_url

# Configuration from environment
PROJECT_ID = os.getenv("GOOGLE_CLOUD_PROJECT", "")
LOCATION = os.getenv("GOOGLE_CLOUD_LOCATION", "us-central1")
QUEUE_NAME = os.getenv("CLOUD_TASKS_QUEUE", "order-parsing-tasks")


def create_parse_email_task(
    job_id: str,
    user_id: str,
    source_id: str,
    email_content: str,
    delay_seconds: int = 0,
) -> str:
    """
    Create a Cloud Task to parse an email.

    Args:
        job_id: Job ID for tracking
        user_id: User who submitted the email
        source_id: Source ID for the email
        email_content: Raw email content to parse
        delay_seconds: Optional delay before task execution

    Returns:
        Task name (full resource path)
    """
    payload = ParseEmailTask(
        job_id=job_id,
        user_id=user_id,
        source_id=source_id,
        email_content=email_content,
    )

    return _create_task(
        endpoint="/tasks/parse-email",
        payload=payload.model_dump(),
        task_id=f"parse-email-{job_id}",
        delay_seconds=delay_seconds,
    )


def create_parse_image_task(
    job_id: str,
    user_id: str,
    source_id: str,
    image_data: str | None = None,
    image_url: str | None = None,
    delay_seconds: int = 0,
) -> str:
    """
    Create a Cloud Task to parse a screenshot.

    Args:
        job_id: Job ID for tracking
        user_id: User who uploaded the image
        source_id: Source ID for the image
        image_data: Base64 encoded image data
        image_url: URL to image (alternative to image_data)
        delay_seconds: Optional delay before task execution

    Returns:
        Task name (full resource path)
    """
    payload = ParseImageTask(
        job_id=job_id,
        user_id=user_id,
        source_id=source_id,
        image_data=image_data,
        image_url=image_url,
    )

    return _create_task(
        endpoint="/tasks/parse-image",
        payload=payload.model_dump(),
        task_id=f"parse-image-{job_id}",
        delay_seconds=delay_seconds,
    )


def _create_task(
    endpoint: str,
    payload: dict[str, Any],
    task_id: str,
    delay_seconds: int = 0,
) -> str:
    """
    Internal function to create a Cloud Task.

    In local development (no PROJECT_ID), this is a no-op that returns
    a mock task name. In production, it creates an actual Cloud Task.

    Args:
        endpoint: Worker service endpoint path
        payload: Task payload dictionary
        task_id: Unique task identifier
        delay_seconds: Delay before task execution

    Returns:
        Task name (full resource path or mock name)
    """
    # Local development mode - skip actual task creation
    if not PROJECT_ID:
        print(f"[LOCAL] Would create task: {task_id} -> {endpoint}")
        print(f"[LOCAL] Payload: {json.dumps(payload, indent=2)[:200]}...")
        return f"local-task/{task_id}"

    # Production mode - create actual Cloud Task
    client = tasks_v2.CloudTasksClient()
    queue_path = client.queue_path(PROJECT_ID, LOCATION, QUEUE_NAME)
    worker_url = get_worker_service_url()

    # Build OIDC token for authenticated Cloud Run services
    oidc_token = None
    service_account = get_service_account_email()
    if worker_url.startswith("https://") and service_account:
        oidc_token = tasks_v2.OidcToken(
            service_account_email=service_account,
            audience=worker_url,
        )

    # Build the HTTP request
    http_request = tasks_v2.HttpRequest(
        http_method=tasks_v2.HttpMethod.POST,
        url=f"{worker_url}{endpoint}",
        headers={"Content-Type": "application/json"},
        body=json.dumps(payload).encode("utf-8"),
        oidc_token=oidc_token,
    )

    # Build the task
    task = tasks_v2.Task(
        name=f"{queue_path}/tasks/{task_id}",
        http_request=http_request,
    )

    # Add delay if specified
    if delay_seconds > 0:
        schedule_time = timestamp_pb2.Timestamp()
        schedule_time.FromSeconds(int(schedule_time.ToSeconds()) + delay_seconds)
        task.schedule_time = schedule_time

    # Create the task
    response = client.create_task(
        request=tasks_v2.CreateTaskRequest(parent=queue_path, task=task)
    )

    return response.name

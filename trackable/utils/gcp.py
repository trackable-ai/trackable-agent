"""
Google Cloud Platform utility functions.

Provides helper functions for GCP credentials, project info, and service URLs.
"""

import os
from functools import lru_cache

import google.auth
import requests

# Configuration from environment
WORKER_SERVICE_LOCATION = os.getenv("WORKER_SERVICE_LOCATION", "us-central1")
WORKER_SERVICE_NAME = os.getenv("WORKER_SERVICE_NAME", "trackable-worker")


@lru_cache(maxsize=1)
def get_credentials_info() -> tuple[str, str]:
    """
    Get service account email and project number from credentials.

    Returns:
        Tuple of (service_account_email, project_number)
    """
    try:
        credentials, project = google.auth.default()
        service_account = ""
        project_number = ""

        if hasattr(credentials, "service_account_email"):
            service_account = credentials.service_account_email

        # On Cloud Run/GCE, service_account_email is "default" - fetch actual email
        if service_account == "default":
            try:
                resp = requests.get(
                    "http://metadata.google.internal/computeMetadata/v1/instance/service-accounts/default/email",
                    headers={"Metadata-Flavor": "Google"},
                    timeout=2,
                )
                if resp.ok:
                    service_account = resp.text
            except requests.RequestException:
                service_account = ""  # Fall back to empty if metadata unavailable

        # Get project number from the resource manager API
        if project:
            from google.cloud import resourcemanager_v3

            client = resourcemanager_v3.ProjectsClient()
            project_resource = client.get_project(name=f"projects/{project}")
            # Project name format: projects/{project_number}
            project_number = project_resource.name.split("/")[-1]

        return service_account, project_number
    except Exception:
        return "", ""


def get_service_account_email() -> str:
    """Get the service account email for OIDC authentication."""
    service_account, _ = get_credentials_info()
    return service_account


def get_project_number() -> str:
    """Get the GCP project number."""
    _, project_number = get_credentials_info()
    return project_number


@lru_cache(maxsize=1)
def get_worker_service_url() -> str:
    """
    Build the Worker service URL.

    Builds URL from service name, project number, and location.
    Format: https://{service-name}-{project-number}.{location}.run.app

    Returns:
        Worker service URL

    Raises:
        ValueError: If project number cannot be determined
    """
    project_number = get_project_number()
    if not project_number:
        raise ValueError(
            "Cannot determine project number. "
            "Ensure GOOGLE_CLOUD_PROJECT is set and Cloud Resource Manager API is enabled."
        )

    return f"https://{WORKER_SERVICE_NAME}-{project_number}.{WORKER_SERVICE_LOCATION}.run.app"

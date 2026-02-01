"""
Logging configuration for Cloud Run.

Configures Python logging to work with Google Cloud Logging.
In Cloud Run, logs are automatically collected from stdout/stderr
when formatted as structured JSON.
"""

import json
import logging
import os
import sys

# Flag to track if logging is already configured
_logging_configured = False


class LocalFormatter(logging.Formatter):
    """Custom formatter that displays json_fields from extra dict."""

    def format(self, record: logging.LogRecord) -> str:
        # Get base formatted message
        message = super().format(record)

        # Check for json_fields in extra
        json_fields = getattr(record, "json_fields", None)
        if json_fields:
            # Append JSON fields to the message
            fields_str = json.dumps(json_fields, indent=2, default=str)
            message = f"{message}\n{fields_str}"

        return message


def setup_logging(service_name: str = "trackable"):
    """
    Configure logging for Cloud Run.

    In GCP (Cloud Run), uses google-cloud-logging to integrate with Cloud Logging.
    Locally, uses standard Python logging with a simple format.

    Args:
        service_name: Name of the service for log identification
    """
    global _logging_configured

    if _logging_configured:
        return

    # Determine if running in GCP
    is_gcp = bool(os.getenv("K_SERVICE"))

    if is_gcp:
        _setup_cloud_logging(service_name)
    else:
        _setup_local_logging()

    _logging_configured = True


def _setup_cloud_logging(service_name: str):
    """Configure logging for Cloud Run using google-cloud-logging."""
    try:
        import google.cloud.logging

        client = google.cloud.logging.Client()
        # This sets up the root logger to send logs to Cloud Logging
        client.setup_logging(log_level=logging.INFO)

        logging.info(f"Cloud Logging configured for service: {service_name}")
    except Exception as e:
        # Fall back to local logging if Cloud Logging setup fails
        _setup_local_logging()
        logging.warning(f"Failed to setup Cloud Logging, using local logging: {e}")


def _setup_local_logging():
    """Configure logging for local development."""
    # Create handler with custom formatter
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(
        LocalFormatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
    )

    # Configure root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.INFO)
    root_logger.addHandler(handler)

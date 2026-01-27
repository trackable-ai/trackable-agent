"""Hash utility functions for Trackable."""

import hashlib


def compute_sha256(data: bytes) -> str:
    """
    Compute SHA-256 hash of data.

    Args:
        data: Raw bytes to hash

    Returns:
        Hexadecimal SHA-256 hash string
    """
    return hashlib.sha256(data).hexdigest()

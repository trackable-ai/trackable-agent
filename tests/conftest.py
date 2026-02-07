"""
pytest configuration and fixtures.

Loads environment variables from .env file for all tests.
"""

import os
from pathlib import Path

from dotenv import load_dotenv


def pytest_configure(config):
    """Load .env file before running tests"""
    # Find the project root (where .env is located)
    project_root = Path(__file__).parent.parent
    env_file = project_root / ".env"

    if env_file.exists():
        print(f"Loading environment from {env_file}")
        load_dotenv(env_file)
    else:
        print(f"Warning: .env file not found at {env_file}")

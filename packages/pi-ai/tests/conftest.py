"""Pytest configuration for pi-ai tests."""

import pytest


@pytest.fixture
def sample_timestamp():
    """Provide a consistent timestamp for tests."""
    return 1234567890000  # Unix timestamp in milliseconds

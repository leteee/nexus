"""
Test configuration and fixtures for the Nexus project.

This module provides common test fixtures and configuration
following Vibecode testing best practices.
"""

import pytest


@pytest.fixture
def sample_data():
    """
    Provide sample data for testing.

    Returns:
        dict: Sample data for use in tests
    """
    return {"name": "test_user", "value": 42, "items": ["apple", "banana", "cherry"]}

"""Pytest configuration and shared fixtures for IterateSwarm tests."""

import sys
from pathlib import Path
from unittest.mock import MagicMock

import pytest
import asyncio

# Add src directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))


@pytest.fixture(scope="session")
def event_loop():
    """Create an instance of the default event loop for the test session."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()

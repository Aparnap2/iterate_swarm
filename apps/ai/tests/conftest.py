"""Pytest configuration and fixtures."""

import pytest
from unittest.mock import AsyncMock, MagicMock


@pytest.fixture
def mock_config():
    """Mock configuration for testing."""
    from src.config import Config, TemporalConfig, OllamaConfig, QdrantConfig

    return Config(
        temporal=TemporalConfig(
            host="localhost",
            port=7233,
            namespace="default",
            task_queue="AI_TASK_QUEUE",
        ),
        ollama=OllamaConfig(
            base_url="http://localhost:11434/v1",
            api_key="ollama",
            model="qwen2.5-coder:3b",
            embedding_model="nomic-embed-text",
        ),
        qdrant=QdrantConfig(
            url="http://localhost:6333",
            collection="feedback_items",
            similarity_threshold=0.85,
        ),
    )


@pytest.fixture
def sample_feedback():
    """Sample feedback for testing."""
    return {
        "feedback_id": "test-feedback-123",
        "content": "The login button is not working on mobile Safari. When I click it, nothing happens.",
        "source": "discord",
    }


@pytest.fixture
def mock_llm_response():
    """Mock LLM response for testing."""
    class MockChoice:
        message = MagicMock()

    class MockResponse:
        choices = [MockChoice()]

    return MockResponse()

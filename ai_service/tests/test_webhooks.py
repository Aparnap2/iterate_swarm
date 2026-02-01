"""Tests for webhook API endpoints.

Uses unittest.mock.AsyncMock to mock KafkaService for isolated testing.
"""

from typing import Any, AsyncGenerator, Generator
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi.testclient import TestClient

from src.main import app
from src.schemas.ingestion import DiscordWebhookPayload, SlackWebhookPayload
from src.services.kafka import KafkaService, get_kafka_service


# ========================
# Test Fixtures
# ========================


@pytest.fixture
def mock_kafka_service() -> MagicMock:
    """Create a mocked KafkaService with AsyncMock for publish."""
    mock = MagicMock()
    mock.publish = AsyncMock(return_value={"status": "success"})
    return mock


@pytest.fixture
async def async_kafka_service(mock_kafka_service: MagicMock) -> AsyncGenerator[KafkaService, None]:
    """Yield the mocked KafkaService for async context."""
    yield mock_kafka_service  # type: ignore[assignment]


@pytest.fixture
def client_with_mocks(mock_kafka_service: MagicMock) -> Generator[TestClient, None, None]:
    """Create test client with mocked Kafka service.

    Overrides the get_kafka_service dependency with a sync wrapper.
    """
    async def override_get_kafka():
        yield mock_kafka_service

    app.dependency_overrides[get_kafka_service] = override_get_kafka

    with TestClient(app) as client:
        yield client

    # Cleanup
    app.dependency_overrides.clear()


# ========================
# Discord Webhook Tests
# ========================


class TestDiscordWebhook:
    """Tests for Discord webhook endpoint."""

    def test_discord_webhook_success(self, client_with_mocks: TestClient, mock_kafka_service: MagicMock) -> None:
        """Test successful Discord webhook processing."""
        payload = {
            "id": "123456789",
            "channel_id": "987654321",
            "content": "The login button is broken on mobile",
            "guild_id": "111222333",
            "author": {
                "id": "444555666",
                "username": "testuser",
            },
        }

        response = client_with_mocks.post("/webhooks/discord", json=payload)

        assert response.status_code == 202
        data = response.json()
        assert data["status"] == "queued"
        assert "id" in data
        assert data["topic"] == "feedback.raw"

        # Verify Kafka was called
        mock_kafka_service.publish.assert_called_once()
        call_args = mock_kafka_service.publish.call_args
        assert call_args.kwargs["topic"] == "feedback.raw"
        message_data = call_args.kwargs["data"]
        assert message_data["source"] == "discord"
        assert "raw_content" in message_data

    def test_discord_webhook_with_embed(self, client_with_mocks: TestClient, mock_kafka_service: MagicMock) -> None:
        """Test Discord webhook with embed content."""
        payload = {
            "id": "123456789",
            "channel_id": "987654321",
            "embeds": [
                {
                    "description": "Bug report: App crashes on upload",
                    "title": "Crash Bug",
                    "color": 16711680,
                }
            ],
        }

        response = client_with_mocks.post("/webhooks/discord", json=payload)

        assert response.status_code == 202
        call_args = mock_kafka_service.publish.call_args
        message_data = call_args.kwargs["data"]
        assert "App crashes on upload" in message_data["raw_content"]

    def test_discord_webhook_empty_content(self, client_with_mocks: TestClient, mock_kafka_service: MagicMock) -> None:
        """Test Discord webhook with no content returns 400."""
        payload = {
            "id": "123456789",
            "channel_id": "987654321",
            "content": "",
        }

        response = client_with_mocks.post("/webhooks/discord", json=payload)

        assert response.status_code == 400
        assert "No extractable content" in response.json()["detail"]
        mock_kafka_service.publish.assert_not_called()

    def test_discord_webhook_strips_content(self, client_with_mocks: TestClient, mock_kafka_service: MagicMock) -> None:
        """Test that whitespace is stripped from content."""
        payload = {
            "id": "123456789",
            "content": "   Bug report here   ",
        }

        response = client_with_mocks.post("/webhooks/discord", json=payload)

        assert response.status_code == 202
        call_args = mock_kafka_service.publish.call_args
        message_data = call_args.kwargs["data"]
        assert message_data["raw_content"] == "Bug report here"


# ========================
# Slack Webhook Tests
# ========================


class TestSlackWebhook:
    """Tests for Slack webhook endpoint."""

    def test_slack_webhook_success(self, client_with_mocks: TestClient, mock_kafka_service: MagicMock) -> None:
        """Test successful Slack webhook processing."""
        payload = {
            "channel": "C12345678",
            "user": "U12345678",
            "text": "The checkout flow is confusing",
            "ts": "1234567890.123456",
        }

        response = client_with_mocks.post("/webhooks/slack", json=payload)

        assert response.status_code == 202
        data = response.json()
        assert data["status"] == "queued"
        assert "id" in data

        mock_kafka_service.publish.assert_called_once()
        call_args = mock_kafka_service.publish.call_args
        assert call_args.kwargs["topic"] == "feedback.raw"
        message_data = call_args.kwargs["data"]
        assert message_data["source"] == "slack"
        assert message_data["raw_content"] == "The checkout flow is confusing"

    def test_slack_webhook_with_blocks(self, client_with_mocks: TestClient, mock_kafka_service: MagicMock) -> None:
        """Test Slack webhook with block kit."""
        payload = {
            "channel": "C12345678",
            "blocks": [
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": "*Feature Request:* Dark mode support",
                    },
                }
            ],
        }

        response = client_with_mocks.post("/webhooks/slack", json=payload)

        assert response.status_code == 202
        call_args = mock_kafka_service.publish.call_args
        message_data = call_args.kwargs["data"]
        assert "*Feature Request:* Dark mode support" in message_data["raw_content"]

    def test_slack_webhook_with_attachments(self, client_with_mocks: TestClient, mock_kafka_service: MagicMock) -> None:
        """Test Slack webhook with legacy attachments."""
        payload = {
            "channel": "C12345678",
            "attachments": [
                {
                    "text": "Error in dashboard widget",
                    "fallback": "Error in dashboard widget",
                }
            ],
        }

        response = client_with_mocks.post("/webhooks/slack", json=payload)

        assert response.status_code == 202
        call_args = mock_kafka_service.publish.call_args
        message_data = call_args.kwargs["data"]
        assert message_data["raw_content"] == "Error in dashboard widget"

    def test_slack_webhook_empty_content(self, client_with_mocks: TestClient, mock_kafka_service: MagicMock) -> None:
        """Test Slack webhook with no content returns 400."""
        payload = {
            "channel": "C12345678",
            "text": "",
        }

        response = client_with_mocks.post("/webhooks/slack", json=payload)

        assert response.status_code == 400
        assert "No extractable content" in response.json()["detail"]
        mock_kafka_service.publish.assert_not_called()


# ========================
# Health Check Tests
# ========================


class TestWebhookHealth:
    """Tests for webhook health endpoint."""

    def test_webhook_health(self, client_with_mocks: TestClient) -> None:
        """Test webhook health endpoint."""
        response = client_with_mocks.get("/webhooks/health")

        assert response.status_code == 200
        assert response.json() == {"status": "webhookshealthy"}


# ========================
# Schema Validation Tests
# ========================


class TestDiscordSchema:
    """Unit tests for Discord schema validation."""

    def test_parse_valid_discord_payload(self) -> None:
        """Test parsing a valid Discord webhook payload."""
        payload = {
            "id": "123",
            "channel_id": "456",
            "content": "Test message",
            "author": {"id": "789", "username": "test"},
        }

        model = DiscordWebhookPayload(**payload)

        assert model.id == "123"
        assert model.channel_id == "456"
        assert model.content == "Test message"
        assert model.author.username == "test"

    def test_discord_with_embeds_extracts_content(self) -> None:
        """Test that embed content is extracted when main content is empty."""
        payload = {
            "id": "123",
            "content": "",
            "embeds": [
                {"description": "Embedded bug report", "title": "Bug"}
            ],
        }

        model = DiscordWebhookPayload(**payload)
        extracted = model.extract_feedback_text()

        assert extracted == "Embedded bug report"

    def test_discord_content_is_stripped(self) -> None:
        """Test that content whitespace is stripped."""
        payload = {"content": "  spaced out  "}

        model = DiscordWebhookPayload(**payload)

        assert model.content == "spaced out"


class TestSlackSchema:
    """Unit tests for Slack schema validation."""

    def test_parse_valid_slack_payload(self) -> None:
        """Test parsing a valid Slack webhook payload."""
        payload = {
            "channel": "C123",
            "user": "U123",
            "text": "Test feedback",
            "ts": "1234567890.123",
        }

        model = SlackWebhookPayload(**payload)

        assert model.channel == "C123"
        assert model.user == "U123"
        assert model.text == "Test feedback"

    def test_slack_blocks_extract_content(self) -> None:
        """Test that block text is extracted when main text is empty."""
        payload = {
            "text": "",
            "blocks": [
                {
                    "type": "section",
                    "text": {"type": "mrkdwn", "text": "Block content"},
                }
            ],
        }

        model = SlackWebhookPayload(**payload)
        extracted = model.extract_feedback_text()

        assert extracted == "Block content"


# ========================
# Run Tests
# ========================


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

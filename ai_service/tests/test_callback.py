"""Integration tests for the AI Service callback client.

These tests verify that the callback client correctly sends issue data
to the web app's internal API.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime

from src.client.callback import CallbackClient, get_callback_client


class TestCallbackClient:
    """Tests for the CallbackClient class."""

    @pytest.fixture
    def mock_client(self):
        """Create a mock httpx AsyncClient."""
        return AsyncMock()

    @pytest.fixture
    def callback_client(self, mock_client):
        """Create a CallbackClient with mocked dependencies."""
        with patch("src.client.callback.settings") as mock_settings:
            mock_settings.web_app_url = "http://localhost:3000"
            mock_settings.internal_api_key.get_secret_value.return_value = "test-api-key"

            client = CallbackClient(base_url="http://localhost:3000")
            client._client = mock_client
            return client

    @pytest.mark.asyncio
    async def test_save_issue_success(self, callback_client, mock_client):
        """Test successful issue saving."""
        # Setup mock response
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"issueId": "issue-123"}
        mock_client.post.return_value = mock_response

        # Call the method
        result = await callback_client.save_issue(
            feedback_id="fb-123",
            content="Test feedback",
            title="Test Issue",
            body="Test body",
            classification="bug",
            severity="high",
            reasoning="Test reasoning",
            confidence=0.9,
            reproduction_steps=["Step 1", "Step 2"],
            affected_components=["api", "frontend"],
            acceptance_criteria=["Done"],
            suggested_labels=["bug", "high"],
        )

        # Verify result
        assert result is True
        mock_client.post.assert_called_once()

        # Verify the call arguments
        call_args = mock_client.post.call_args
        assert call_args.args[0] == "http://localhost:3000/api/internal/save-issue"
        assert "Authorization" in call_args.kwargs["headers"]
        assert call_args.kwargs["headers"]["Authorization"] == "Bearer test-api-key"

        # Verify payload
        payload = call_args.kwargs["json"]
        assert payload["feedbackId"] == "fb-123"
        assert payload["title"] == "Test Issue"
        assert payload["classification"] == "bug"
        assert payload["severity"] == "high"

    @pytest.mark.asyncio
    async def test_save_issue_http_error(self, callback_client, mock_client):
        """Test handling of HTTP errors."""
        mock_response = MagicMock()
        mock_response.status_code = 500
        mock_response.text = "Internal Server Error"
        mock_client.post.return_value = mock_response

        result = await callback_client.save_issue(
            feedback_id="fb-123",
            content="Test feedback",
            title="Test Issue",
            body="Test body",
            classification="bug",
            severity="high",
            reasoning="Test reasoning",
            confidence=0.9,
            reproduction_steps=[],
            affected_components=["api"],
            acceptance_criteria=[],
            suggested_labels=[],
        )

        assert result is False

    @pytest.mark.asyncio
    async def test_save_issue_request_error(self, callback_client, mock_client):
        """Test handling of request errors (connection failures)."""
        import httpx

        mock_client.post.side_effect = httpx.RequestError("Connection failed")

        result = await callback_client.save_issue(
            feedback_id="fb-123",
            content="Test feedback",
            title="Test Issue",
            body="Test body",
            classification="bug",
            severity="high",
            reasoning="Test reasoning",
            confidence=0.9,
            reproduction_steps=[],
            affected_components=["api"],
            acceptance_criteria=[],
            suggested_labels=[],
        )

        assert result is False

    @pytest.mark.asyncio
    async def test_close_client(self, callback_client, mock_client):
        """Test closing the httpx client."""
        await callback_client.close()
        mock_client.aclose.assert_called_once()
        assert callback_client._client is None

    @pytest.mark.asyncio
    async def test_context_manager(self, callback_client, mock_client):
        """Test using the client as a context manager."""
        async with callback_client as client:
            assert client is callback_client
            assert client._client is mock_client

        mock_client.aclose.assert_called_once()


class TestCallbackClientWithRealSettings:
    """Tests using real settings for integration testing."""

    def test_client_initialization_with_defaults(self):
        """Test client initializes with settings defaults."""
        with patch("src.client.callback.settings") as mock_settings:
            mock_settings.web_app_url = "http://localhost:3000"
            mock_settings.internal_api_key = None

            client = CallbackClient()

            assert client._base_url == "http://localhost:3000"
            assert client._api_key is None

    def test_client_initialization_with_custom_url(self):
        """Test client initializes with custom base URL."""
        with patch("src.client.callback.settings") as mock_settings:
            mock_settings.web_app_url = "http://localhost:3000"
            mock_settings.internal_api_key = None

            client = CallbackClient(base_url="http://custom:4000")

            assert client._base_url == "http://custom:4000"

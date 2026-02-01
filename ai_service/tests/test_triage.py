"""Integration tests for the Triage Agent.

These tests verify that the triage agent correctly classifies feedback
into bug/feature/question categories with appropriate severity levels.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from pydantic import ValidationError

from src.agents.triage import (
    TriageState,
    TriageResult,
    triage_node,
    classify_feedback,
    get_llm_client,
)


class TestTriageResult:
    """Tests for the TriageResult Pydantic model."""

    def test_valid_bug_classification(self):
        """Test creating a valid bug classification."""
        result = TriageResult(
            classification="bug",
            severity="high",
            reasoning="The user reports a crash when clicking submit",
            confidence=0.95,
        )
        assert result.classification == "bug"
        assert result.severity == "high"
        assert result.confidence == 0.95

    def test_valid_feature_classification(self):
        """Test creating a valid feature classification."""
        result = TriageResult(
            classification="feature",
            severity="medium",
            reasoning="User requests dark mode support",
            confidence=0.85,
        )
        assert result.classification == "feature"
        assert result.severity == "medium"

    def test_valid_question_classification(self):
        """Test creating a valid question classification."""
        result = TriageResult(
            classification="question",
            severity="low",
            reasoning="User asks how to reset password",
            confidence=0.9,
        )
        assert result.classification == "question"

    def test_invalid_classification_rejected(self):
        """Test that invalid classification is rejected."""
        with pytest.raises(ValidationError):
            TriageResult(
                classification="invalid",
                severity="high",
                reasoning="Test reasoning",
                confidence=0.9,
            )

    def test_invalid_severity_rejected(self):
        """Test that invalid severity is rejected."""
        with pytest.raises(ValidationError):
            TriageResult(
                classification="bug",
                severity="invalid",
                reasoning="Test reasoning",
                confidence=0.9,
            )

    def test_confidence_bounds(self):
        """Test confidence score bounds."""
        # Valid bounds
        result = TriageResult(
            classification="bug",
            severity="low",
            reasoning="Test reasoning for triage",
            confidence=0.0,
        )
        assert result.confidence == 0.0

        result = TriageResult(
            classification="bug",
            severity="low",
            reasoning="Test reasoning for triage",
            confidence=1.0,
        )
        assert result.confidence == 1.0

        # Invalid bounds
        with pytest.raises(ValidationError):
            TriageResult(
                classification="bug",
                severity="low",
                reasoning="Test reasoning",
                confidence=1.5,
            )

        with pytest.raises(ValidationError):
            TriageResult(
                classification="bug",
                severity="low",
                reasoning="Test reasoning",
                confidence=-0.1,
            )


class TestTriageState:
    """Tests for the TriageState TypedDict."""

    def test_valid_state(self):
        """Test creating a valid state."""
        state: TriageState = {
            "feedback_id": "fb-123",
            "content": "Test feedback",
            "source": "discord",
            "classification": "bug",
            "severity": "high",
            "reasoning": "Test reasoning",
            "confidence": 0.9,
        }
        assert state["feedback_id"] == "fb-123"
        assert state["classification"] == "bug"


class TestTriageNode:
    """Tests for the triage node function."""

    @pytest.mark.asyncio
    async def test_triage_bug_classification(self):
        """Test triage node correctly identifies a bug."""
        # Mock the LLM client
        mock_response = MagicMock()
        mock_response.choices = [
            MagicMock(
                message=MagicMock(
                    content='{"classification": "bug", "severity": "high", "reasoning": "User reports crash on submit", "confidence": 0.95}'
                )
            )
        ]

        with patch("src.agents.triage.get_llm_client") as mock_get_client:
            mock_client = AsyncMock()
            mock_client.chat.completions.create = AsyncMock(return_value=mock_response)
            mock_get_client.return_value = mock_client

            result = await triage_node(
                TriageState(
                    feedback_id="fb-123",
                    content="The app crashes when I click submit button",
                    source="discord",
                    classification="question",
                    severity="low",
                    reasoning="",
                    confidence=0.0,
                )
            )

            assert result["classification"] == "bug"
            assert result["severity"] == "high"
            assert result["confidence"] == 0.95

    @pytest.mark.asyncio
    async def test_triage_question_classification(self):
        """Test triage node correctly identifies a question."""
        mock_response = MagicMock()
        mock_response.choices = [
            MagicMock(
                message=MagicMock(
                    content='{"classification": "question", "severity": "low", "reasoning": "User asks for clarification", "confidence": 0.9}'
                )
            )
        ]

        with patch("src.agents.triage.get_llm_client") as mock_get_client:
            mock_client = AsyncMock()
            mock_client.chat.completions.create = AsyncMock(return_value=mock_response)
            mock_get_client.return_value = mock_client

            result = await triage_node(
                TriageState(
                    feedback_id="fb-456",
                    content="How do I reset my password?",
                    source="slack",
                    classification="question",
                    severity="low",
                    reasoning="",
                    confidence=0.0,
                )
            )

            assert result["classification"] == "question"

    @pytest.mark.asyncio
    async def test_triage_fallback_on_error(self):
        """Test triage returns safe defaults on error."""
        with patch("src.agents.triage.get_llm_client") as mock_get_client:
            mock_get_client.side_effect = Exception("LLM connection failed")

            result = await triage_node(
                TriageState(
                    feedback_id="fb-789",
                    content="Test content",
                    source="discord",
                    classification="question",
                    severity="low",
                    reasoning="",
                    confidence=0.0,
                )
            )

            # Should return safe defaults
            assert result["classification"] == "question"
            assert result["severity"] == "low"
            assert result["confidence"] == 0.0
            assert "Classification failed" in result["reasoning"]


class TestClassifyFeedback:
    """Tests for the classify_feedback convenience function."""

    @pytest.mark.asyncio
    async def test_classify_feedback_success(self):
        """Test classifying feedback returns TriageResult."""
        mock_response = MagicMock()
        mock_response.choices = [
            MagicMock(
                message=MagicMock(
                    content='{"classification": "feature", "severity": "medium", "reasoning": "New feature request", "confidence": 0.85}'
                )
            )
        ]

        with patch("src.agents.triage.get_llm_client") as mock_get_client:
            mock_client = AsyncMock()
            mock_client.chat.completions.create = AsyncMock(return_value=mock_response)
            mock_get_client.return_value = mock_client

            result = await classify_feedback(
                feedback_id="fb-test",
                content="Please add dark mode",
                source="discord",
            )

            assert isinstance(result, TriageResult)
            assert result.classification == "feature"
            assert result.severity == "medium"


class TestGetLLMClient:
    """Tests for the LLM client factory."""

    def test_returns_openai_client(self):
        """Test get_llm_client returns an AsyncOpenAI client."""
        with patch("src.agents.triage.settings") as mock_settings:
            mock_settings.openai_api_key.get_secret_value.return_value = "test-key"
            mock_settings.local_llm_url = "http://localhost:11434/v1"
            mock_settings.local_llm_model = "qwen2.5-coder:3b"

            # Mock the AsyncOpenAI to avoid actual connection
            with patch("src.agents.triage.AsyncOpenAI") as mock_openai:
                mock_client = MagicMock()
                mock_openai.return_value = mock_client

                client = get_llm_client()

                # Verify it was called with correct parameters
                mock_openai.assert_called_once()
                call_kwargs = mock_openai.call_args.kwargs
                assert "http://localhost:11434/v1" in call_kwargs["base_url"]
                assert call_kwargs["api_key"] == "ollama"
                assert call_kwargs["model"] == "qwen2.5-coder:3b"

"""Integration tests for the Spec Writer Agent.

These tests verify that the spec writer correctly generates
GitHub issue specs from classified feedback.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from pydantic import ValidationError

from src.agents.spec import (
    SpecState,
    SpecResult,
    spec_writer_node,
    write_spec,
    get_llm_client,
)


class TestSpecResult:
    """Tests for the SpecResult Pydantic model."""

    def test_valid_spec_result(self):
        """Test creating a valid spec result."""
        result = SpecResult(
            title="Fix login timeout on mobile Safari",
            reproduction_steps=[
                "Open the app on mobile Safari",
                "Tap the login button",
                "Wait for timeout",
            ],
            affected_components=["auth", "frontend"],
            acceptance_criteria=[
                "Login completes within 5 seconds",
                "Error message is displayed on failure",
            ],
            suggested_labels=["bug", "high", "mobile"],
            spec_confidence=0.9,
        )
        assert result.title == "Fix login timeout on mobile Safari"
        assert len(result.reproduction_steps) == 3
        assert len(result.affected_components) == 2

    def test_empty_reproduction_steps_for_feature(self):
        """Test that features can have empty reproduction steps."""
        result = SpecResult(
            title="Add dark mode support",
            reproduction_steps=[],
            affected_components=["frontend"],
            acceptance_criteria=[
                "Dark mode toggle appears in settings",
                "Theme persists across sessions",
            ],
            suggested_labels=["feature", "ui"],
            spec_confidence=0.85,
        )
        assert len(result.reproduction_steps) == 0

    def test_title_length_constraints(self):
        """Test title length validation."""
        # Too short
        with pytest.raises(ValidationError):
            SpecResult(
                title="Hi",
                reproduction_steps=[],
                affected_components=["api"],
                acceptance_criteria=["Done"],
                suggested_labels=["bug"],
                spec_confidence=0.9,
            )

        # Too long (over 100 chars)
        long_title = "x" * 101
        with pytest.raises(ValidationError):
            SpecResult(
                title=long_title,
                reproduction_steps=[],
                affected_components=["api"],
                acceptance_criteria=["Done"],
                suggested_labels=["bug"],
                spec_confidence=0.9,
            )

    def test_confidence_bounds(self):
        """Test confidence score bounds."""
        result = SpecResult(
            title="Test Issue",
            reproduction_steps=[],
            affected_components=["api"],
            acceptance_criteria=["Done"],
            suggested_labels=["bug"],
            spec_confidence=0.0,
        )
        assert result.spec_confidence == 0.0

        result = SpecResult(
            title="Test Issue",
            reproduction_steps=[],
            affected_components=["api"],
            acceptance_criteria=["Done"],
            suggested_labels=["bug"],
            spec_confidence=1.0,
        )
        assert result.spec_confidence == 1.0

    def test_list_length_constraints(self):
        """Test list length constraints."""
        # Too many components
        with pytest.raises(ValidationError):
            SpecResult(
                title="Test Issue",
                reproduction_steps=["1", "2", "3", "4", "5", "6", "7", "8", "9", "10", "11"],
                affected_components=["api"],
                acceptance_criteria=["Done"],
                suggested_labels=["bug"],
                spec_confidence=0.9,
            )


class TestSpecState:
    """Tests for the SpecState TypedDict."""

    def test_valid_state(self):
        """Test creating a valid spec state."""
        state: SpecState = {
            "feedback_id": "fb-123",
            "content": "The app crashes on login",
            "source": "discord",
            "classification": "bug",
            "severity": "high",
            "reasoning": "Critical bug affecting all users",
            "confidence": 0.95,
            "title": "Fix login crash",
            "reproduction_steps": ["Step 1", "Step 2"],
            "affected_components": ["auth"],
            "acceptance_criteria": ["Login works"],
            "suggested_labels": ["bug", "high"],
            "spec_confidence": 0.9,
        }
        assert state["feedback_id"] == "fb-123"
        assert state["classification"] == "bug"


class TestSpecWriterNode:
    """Tests for the spec writer node function."""

    @pytest.mark.asyncio
    async def test_write_bug_spec(self):
        """Test spec writer creates a proper bug report."""
        mock_response = MagicMock()
        mock_response.choices = [
            MagicMock(
                message=MagicMock(
                    content='{"title": "Fix login timeout on mobile Safari", "reproduction_steps": ["Open app on mobile Safari", "Tap login", "Wait"], "affected_components": ["auth", "frontend"], "acceptance_criteria": ["Login completes within 5 seconds"], "suggested_labels": ["bug", "high", "mobile"], "spec_confidence": 0.9}'
                )
            )
        ]

        with patch("src.agents.spec.get_llm_client") as mock_get_client:
            mock_client = AsyncMock()
            mock_client.chat.completions.create = AsyncMock(return_value=mock_response)
            mock_get_client.return_value = mock_client

            result = await spec_writer_node(
                SpecState(
                    feedback_id="fb-123",
                    content="The app times out when logging in on mobile Safari",
                    source="discord",
                    classification="bug",
                    severity="high",
                    reasoning="Critical issue affecting user login",
                    confidence=0.95,
                    title="",
                    reproduction_steps=[],
                    affected_components=[],
                    acceptance_criteria=[],
                    suggested_labels=[],
                    spec_confidence=0.0,
                )
            )

            assert "Fix login timeout" in result["title"]
            assert len(result["reproduction_steps"]) >= 1
            assert len(result["affected_components"]) >= 1
            assert "bug" in result["suggested_labels"]

    @pytest.mark.asyncio
    async def test_write_feature_spec(self):
        """Test spec writer creates a proper feature request."""
        mock_response = MagicMock()
        mock_response.choices = [
            MagicMock(
                message=MagicMock(
                    content='{"title": "Add dark mode support", "reproduction_steps": [], "affected_components": ["frontend", "ui"], "acceptance_criteria": ["Dark mode toggle in settings", "Theme persists"], "suggested_labels": ["feature", "ui", "enhancement"], "spec_confidence": 0.85}'
                )
            )
        ]

        with patch("src.agents.spec.get_llm_client") as mock_get_client:
            mock_client = AsyncMock()
            mock_client.chat.completions.create = AsyncMock(return_value=mock_response)
            mock_get_client.return_value = mock_client

            result = await spec_writer_node(
                SpecState(
                    feedback_id="fb-456",
                    content="Please add dark mode to the app",
                    source="slack",
                    classification="feature",
                    severity="medium",
                    reasoning="User request for UI improvement",
                    confidence=0.8,
                    title="",
                    reproduction_steps=[],
                    affected_components=[],
                    acceptance_criteria=[],
                    suggested_labels=[],
                    spec_confidence=0.0,
                )
            )

            assert "dark mode" in result["title"].lower() or "dark" in result["title"].lower()
            assert len(result["reproduction_steps"]) == 0  # Features don't have repro steps
            assert len(result["acceptance_criteria"]) >= 1

    @pytest.mark.asyncio
    async def test_spec_writer_fallback_on_error(self):
        """Test spec writer returns safe defaults on error."""
        with patch("src.agents.spec.get_llm_client") as mock_get_client:
            mock_get_client.side_effect = Exception("LLM connection failed")

            result = await spec_writer_node(
                SpecState(
                    feedback_id="fb-789",
                    content="Test content",
                    source="discord",
                    classification="bug",
                    severity="low",
                    reasoning="Test",
                    confidence=0.9,
                    title="",
                    reproduction_steps=[],
                    affected_components=[],
                    acceptance_criteria=[],
                    suggested_labels=[],
                    spec_confidence=0.0,
                )
            )

            # Should return safe defaults with classification prefix
            assert "[BUG]" in result["title"]
            assert "unknown" in result["affected_components"]
            assert "bug" in result["suggested_labels"]
            assert result["spec_confidence"] == 0.0


class TestWriteSpec:
    """Tests for the write_spec convenience function."""

    @pytest.mark.asyncio
    async def test_write_spec_success(self):
        """Test writing a spec returns SpecResult."""
        mock_response = MagicMock()
        mock_response.choices = [
            MagicMock(
                message=MagicMock(
                    content='{"title": "Test Issue", "reproduction_steps": [], "affected_components": ["api"], "acceptance_criteria": ["Done"], "suggested_labels": ["bug"], "spec_confidence": 0.9}'
                )
            )
        ]

        with patch("src.agents.spec.get_llm_client") as mock_get_client:
            mock_client = AsyncMock()
            mock_client.chat.completions.create = AsyncMock(return_value=mock_response)
            mock_get_client.return_value = mock_client

            result = await write_spec(
                feedback_id="fb-test",
                content="Test content",
                source="discord",
                classification="bug",
                severity="high",
                reasoning="Test reasoning",
                confidence=0.9,
            )

            assert isinstance(result, SpecResult)
            assert result.title == "Test Issue"


class TestGetLLMClient:
    """Tests for the LLM client factory."""

    def test_returns_openai_client(self):
        """Test get_llm_client returns an AsyncOpenAI client."""
        with patch("src.agents.spec.settings") as mock_settings:
            mock_settings.openai_api_key.get_secret_value.return_value = "test-key"
            mock_settings.local_llm_url = "http://localhost:11434/v1"
            mock_settings.local_llm_model = "qwen2.5-coder:3b"

            # Mock the AsyncOpenAI to avoid actual connection
            with patch("src.agents.spec.AsyncOpenAI") as mock_openai:
                mock_client = MagicMock()
                mock_openai.return_value = mock_client

                client = get_llm_client()

                # Verify it was called with correct parameters
                mock_openai.assert_called_once()
                call_kwargs = mock_openai.call_args.kwargs
                assert "http://localhost:11434/v1" in call_kwargs["base_url"]
                assert call_kwargs["api_key"] == "ollama"
                assert call_kwargs["model"] == "qwen2.5-coder:3b"

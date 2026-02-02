"""Tests for Temporal Activities."""

import pytest
from unittest.mock import AsyncMock, patch, MagicMock
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent))


class TestAnalyzeFeedbackInput:
    """Tests for AnalyzeFeedbackInput model."""

    def test_valid_input(self):
        """Test creating valid input."""
        from src.activities import AnalyzeFeedbackInput

        input_data = AnalyzeFeedbackInput(
            feedback_id="test-123",
            content="Test feedback content",
            source="discord",
        )

        assert input_data.feedback_id == "test-123"
        assert input_data.content == "Test feedback content"
        assert input_data.source == "discord"

    def test_default_source(self):
        """Test default source is discord."""
        from src.activities import AnalyzeFeedbackInput

        input_data = AnalyzeFeedbackInput(
            feedback_id="test-123",
            content="Test feedback content",
        )

        assert input_data.source == "discord"


class TestAnalyzeFeedbackOutput:
    """Tests for AnalyzeFeedbackOutput model."""

    def test_valid_output(self):
        """Test creating valid output."""
        from src.activities import AnalyzeFeedbackOutput

        output = AnalyzeFeedbackOutput(
            is_duplicate=False,
            duplicate_score=0.0,
            classification="bug",
            severity="high",
            reasoning="Test reasoning",
            title="Fix login button",
            reproduction_steps=["Step 1", "Step 2"],
            affected_components=["auth", "frontend"],
            acceptance_criteria=["Button works"],
            suggested_labels=["bug", "high"],
            confidence=0.9,
        )

        assert output.is_duplicate is False
        assert output.classification == "bug"
        assert output.severity == "high"

    def test_duplicate_output(self):
        """Test creating duplicate output."""
        from src.activities import AnalyzeFeedbackOutput

        output = AnalyzeFeedbackOutput(
            is_duplicate=True,
            duplicate_score=0.92,
            classification="duplicate",
            severity="low",
            reasoning="Similar to existing issue",
            title="[DUPLICATE] Login button issue",
            confidence=0.92,
        )

        assert output.is_duplicate is True
        assert output.duplicate_score == 0.92


@pytest.mark.asyncio
class TestAnalyzeFeedbackActivity:
    """Tests for the analyze_feedback activity."""

    async def test_analyze_feedback_success(self, sample_feedback):
        """Test successful feedback analysis."""
        from src.activities import AnalyzeFeedbackInput, analyze_feedback

        # Mock the agent functions
        with patch("src.activities.classify_feedback") as mock_classify, \
             patch("src.activities.write_spec") as mock_spec, \
             patch("src.activities.get_qdrant_service") as mock_get_qdrant:

            # Setup mocks
            mock_qdrant = AsyncMock()
            mock_qdrant.check_duplicate = AsyncMock(return_value=(False, 0.0))
            mock_qdrant.index_feedback = AsyncMock()
            mock_get_qdrant.return_value = mock_qdrant

            mock_classify.return_value = MagicMock(
                classification="bug",
                severity="high",
                reasoning="Clear bug report",
                confidence=0.95,
            )

            mock_spec.return_value = MagicMock(
                title="Fix login button on mobile",
                reproduction_steps=["Open Safari", "Go to login"],
                affected_components=["auth", "frontend"],
                acceptance_criteria=["Button responds to click"],
                suggested_labels=["bug", "high", "mobile"],
                spec_confidence=0.92,
            )

            # Create input
            input_data = AnalyzeFeedbackInput(**sample_feedback)

            # Call activity
            result = await analyze_feedback(input_data)

            # Verify results
            assert result.is_duplicate is False
            assert result.classification == "bug"
            assert result.severity == "high"
            assert result.title == "Fix login button on mobile"

    async def test_duplicate_detection(self, sample_feedback):
        """Test that duplicates are detected and skipped."""
        from src.activities import AnalyzeFeedbackInput, analyze_feedback

        with patch("src.activities.get_qdrant_service") as mock_get_qdrant:
            mock_qdrant = AsyncMock()
            mock_qdrant.check_duplicate = AsyncMock(return_value=(True, 0.92))
            mock_get_qdrant.return_value = mock_qdrant

            input_data = AnalyzeFeedbackInput(**sample_feedback)
            result = await analyze_feedback(input_data)

            assert result.is_duplicate is True
            assert result.duplicate_score == 0.92
            assert result.classification == "duplicate"

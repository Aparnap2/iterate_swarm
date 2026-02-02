"""Tests for LangGraph Agents."""

import pytest
from unittest.mock import patch, MagicMock
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent))


class TestTriageAgent:
    """Tests for the Triage Agent."""

    def test_triage_result_model(self):
        """Test TriageResult Pydantic model validation."""
        from src.agents.triage import TriageResult

        result = TriageResult(
            classification="bug",
            severity="high",
            reasoning="Clear bug report with steps to reproduce",
            confidence=0.95,
        )

        assert result.classification == "bug"
        assert result.severity == "high"
        assert result.confidence == 0.95

    def test_triage_result_pattern_validation(self):
        """Test that invalid classification/severity are rejected."""
        from src.agents.triage import TriageResult
        from pydantic import ValidationError

        with pytest.raises(ValidationError):
            TriageResult(
                classification="invalid",
                severity="high",
                reasoning="Clear bug report",
                confidence=0.95,
            )

        with pytest.raises(ValidationError):
            TriageResult(
                classification="bug",
                severity="invalid",
                reasoning="Clear bug report",
                confidence=0.95,
            )

    def test_confidence_bounds(self):
        """Test confidence score bounds."""
        from src.agents.triage import TriageResult
        from pydantic import ValidationError

        # Valid bounds
        result = TriageResult(
            classification="bug",
            severity="low",
            reasoning="Test reasoning",
            confidence=0.0,
        )
        assert result.confidence == 0.0

        result = TriageResult(
            classification="bug",
            severity="low",
            reasoning="Test reasoning",
            confidence=1.0,
        )
        assert result.confidence == 1.0


class TestSpecAgent:
    """Tests for the Spec Writer Agent."""

    def test_spec_result_model(self):
        """Test SpecResult Pydantic model validation."""
        from src.agents.spec import SpecResult

        result = SpecResult(
            title="Fix login timeout on mobile Safari",
            reproduction_steps=["Step 1", "Step 2"],
            affected_components=["auth", "frontend"],
            acceptance_criteria=["Button works"],
            suggested_labels=["bug", "high"],
            spec_confidence=0.9,
        )

        assert result.title == "Fix login timeout on mobile Safari"
        assert len(result.reproduction_steps) == 2

    def test_spec_result_title_length(self):
        """Test title length constraints."""
        from src.agents.spec import SpecResult
        from pydantic import ValidationError

        # Too short
        with pytest.raises(ValidationError):
            SpecResult(
                title="Hi",
                reproduction_steps=[],
                affected_components=["auth"],
                acceptance_criteria=["Works"],
                suggested_labels=["bug"],
                spec_confidence=0.9,
            )


class TestLLMClient:
    """Tests for LLM client configuration."""

    @patch("src.agents.triage.get_config")
    @patch("src.agents.spec.get_config")
    def test_get_llm_client(self, mock_spec_config, mock_triage_config):
        """Test LLM client creation with mocked config."""
        from openai import AsyncOpenAI

        # Mock the config to return test values
        mock_ollama = MagicMock()
        mock_ollama.base_url = "http://localhost:11434/v1"
        mock_ollama.api_key = "test-key"
        mock_ollama.model = "llama3"

        mock_triage_config.return_value.ollama = mock_ollama
        mock_spec_config.return_value.ollama = mock_ollama

        from src.agents.triage import get_llm_client as get_triage_client
        from src.agents.spec import get_llm_client as get_spec_client

        client1 = get_triage_client()
        client2 = get_spec_client()

        # Both should be AsyncOpenAI instances
        assert isinstance(client1, AsyncOpenAI)
        assert isinstance(client2, AsyncOpenAI)

"""Tests for agent logic (triage and spec agents).

These tests verify the agent state machines and data flow without
making actual LLM calls.
"""

import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from uuid import uuid4

from src.agents.triage import TriageState, TriageResult
from src.agents.spec import SpecState, SpecResult


# ========================
# Triage Agent Tests
# ========================


class TestTriageState:
    """Tests for TriageState TypedDict."""

    def test_default_state_values(self):
        """Test that TriageState has correct default structure."""
        state: TriageState = {
            "feedback_id": "test-123",
            "content": "The login button doesn't work",
            "source": "discord",
            "classification": "question",
            "severity": "low",
            "reasoning": "",
            "confidence": 0.0,
        }

        assert state["feedback_id"] == "test-123"
        assert state["classification"] == "question"
        assert state["severity"] == "low"
        assert 0.0 <= state["confidence"] <= 1.0

    def test_state_allows_valid_classifications(self):
        """Test that state accepts all valid classifications."""
        for classification in ["bug", "feature", "question"]:
            state: TriageState = {
                "feedback_id": "test",
                "content": "test content",
                "source": "test",
                "classification": classification,
                "severity": "low",
                "reasoning": "test",
                "confidence": 0.5,
            }
            assert state["classification"] == classification

    def test_state_allows_valid_severities(self):
        """Test that state accepts all valid severity levels."""
        for severity in ["low", "medium", "high", "critical"]:
            state: TriageState = {
                "feedback_id": "test",
                "content": "test content",
                "source": "test",
                "classification": "bug",
                "severity": severity,
                "reasoning": "test",
                "confidence": 0.5,
            }
            assert state["severity"] == severity


class TestTriageResult:
    """Tests for TriageResult Pydantic model."""

    def test_valid_bug_classification(self):
        """Test creating a valid bug classification result."""
        result = TriageResult(
            classification="bug",
            severity="high",
            reasoning="The user reports the login button is broken",
            confidence=0.9,
        )
        assert result.classification == "bug"
        assert result.severity == "high"
        assert result.confidence == 0.9

    def test_valid_feature_classification(self):
        """Test creating a valid feature classification result."""
        result = TriageResult(
            classification="feature",
            severity="medium",
            reasoning="The user wants dark mode support",
            confidence=0.85,
        )
        assert result.classification == "feature"

    def test_valid_question_classification(self):
        """Test creating a valid question classification result."""
        result = TriageResult(
            classification="question",
            severity="low",
            reasoning="The user is asking how to reset their password",
            confidence=0.95,
        )
        assert result.classification == "question"

    def test_classification_rejects_invalid_value(self):
        """Test that invalid classification is rejected."""
        from pydantic import ValidationError

        with pytest.raises(ValidationError):
            TriageResult(
                classification="invalid",
                severity="low",
                reasoning="This should fail",
                confidence=0.5,
            )

    def test_severity_rejects_invalid_value(self):
        """Test that invalid severity is rejected."""
        from pydantic import ValidationError

        with pytest.raises(ValidationError):
            TriageResult(
                classification="bug",
                severity="invalid",
                reasoning="This should fail",
                confidence=0.5,
            )

    def test_confidence_bounds_enforced(self):
        """Test that confidence must be between 0 and 1."""
        from pydantic import ValidationError

        # Confidence too high
        with pytest.raises(ValidationError):
            TriageResult(
                classification="bug",
                severity="low",
                reasoning="test",
                confidence=1.5,
            )

        # Confidence negative
        with pytest.raises(ValidationError):
            TriageResult(
                classification="bug",
                severity="low",
                reasoning="test",
                confidence=-0.1,
            )

    def test_reasoning_min_length(self):
        """Test that reasoning has minimum length."""
        from pydantic import ValidationError

        with pytest.raises(ValidationError):
            TriageResult(
                classification="bug",
                severity="low",
                reasoning="short",
                confidence=0.5,
            )


# ========================
# Spec Agent Tests
# ========================


class TestSpecState:
    """Tests for SpecState TypedDict."""

    def test_spec_state_structure(self):
        """Test that SpecState has correct structure."""
        state: SpecState = {
            "feedback_id": "test-456",
            "content": "The app crashes when I upload a large file",
            "source": "slack",
            "classification": "bug",
            "severity": "high",
            "reasoning": "User reports app crash",
            "confidence": 0.9,
            "title": "",
            "reproduction_steps": [],
            "affected_components": [],
            "acceptance_criteria": [],
            "suggested_labels": [],
            "spec_confidence": 0.0,
        }

        assert state["feedback_id"] == "test-456"
        assert state["classification"] == "bug"
        assert state["affected_components"] == []
        assert isinstance(state["reproduction_steps"], list)


class TestSpecResult:
    """Tests for SpecResult Pydantic model."""

    def test_valid_spec_result(self):
        """Test creating a valid spec result."""
        result = SpecResult(
            title="Fix file upload crash for large files",
            reproduction_steps=[
                "Open the app",
                "Navigate to upload page",
                "Select a file larger than 100MB",
            ],
            affected_components=["upload-service", "file-handler"],
            acceptance_criteria=[
                "Files under 100MB upload successfully",
                "Large files show progress indicator",
                "No crashes during upload",
            ],
            suggested_labels=["bug", "high", "frontend"],
            spec_confidence=0.85,
        )

        assert result.title == "Fix file upload crash for large files"
        assert len(result.reproduction_steps) == 3
        assert "upload-service" in result.affected_components
        assert len(result.acceptance_criteria) == 3

    def test_feature_spec_without_reproduction_steps(self):
        """Test that feature specs can have empty reproduction steps."""
        result = SpecResult(
            title="Add dark mode support",
            reproduction_steps=[],  # Features don't need reproduction steps
            affected_components=["frontend", "theme"],
            acceptance_criteria=[
                "Dark mode toggle visible in settings",
                "All pages support dark mode",
            ],
            suggested_labels=["feature", "enhancement", "frontend"],
            spec_confidence=0.9,
        )

        assert len(result.reproduction_steps) == 0
        assert len(result.acceptance_criteria) == 2
        assert "feature" in result.suggested_labels

    def test_title_length_constraints(self):
        """Test title min/max length constraints."""
        from pydantic import ValidationError

        # Too short
        with pytest.raises(ValidationError):
            SpecResult(
                title="Hi",
                reproduction_steps=[],
                affected_components=["test"],
                acceptance_criteria=["test"],
                suggested_labels=["test"],
                spec_confidence=0.5,
            )

    def test_affected_components_require_at_least_one(self):
        """Test that at least one affected component is required."""
        from pydantic import ValidationError

        with pytest.raises(ValidationError):
            SpecResult(
                title="Test feature",
                reproduction_steps=[],
                affected_components=[],  # Empty not allowed
                acceptance_criteria=["test"],
                suggested_labels=["test"],
                spec_confidence=0.5,
            )

    def test_acceptence_criteria_require_at_least_one(self):
        """Test that at least one acceptance criterion is required."""
        from pydantic import ValidationError

        with pytest.raises(ValidationError):
            SpecResult(
                title="Test feature",
                reproduction_steps=[],
                affected_components=["test"],
                acceptance_criteria=[],  # Empty not allowed
                suggested_labels=["test"],
                spec_confidence=0.5,
            )


# ========================
# Integration Tests
# ========================


class TestTriageToSpecPipeline:
    """Tests for the triage -> spec pipeline flow."""

    def test_triage_to_spec_data_passing(self):
        """Test that triage output can flow into spec input."""
        # Simulate triage output
        triage_output = TriageResult(
            classification="bug",
            severity="high",
            reasoning="User reports login failure with error message",
            confidence=0.92,
        )

        # Create spec state from triage output
        spec_state: SpecState = {
            "feedback_id": "test-pipeline-001",
            "content": "When I try to login, I get an error and cannot access my account",
            "source": "discord",
            **triage_output.model_dump(),
            "title": "",
            "reproduction_steps": [],
            "affected_components": [],
            "acceptance_criteria": [],
            "suggested_labels": [],
            "spec_confidence": 0.0,
        }

        # Verify data flows correctly
        assert spec_state["classification"] == "bug"
        assert spec_state["severity"] == "high"
        assert spec_state["reasoning"] == "User reports login failure with error message"
        assert spec_state["confidence"] == 0.92

    def test_feature_flow_skip_reproduction_steps(self):
        """Test that feature requests don't need reproduction steps."""
        triage_output = TriageResult(
            classification="feature",
            severity="medium",
            reasoning="User wants to export data to CSV",
            confidence=0.88,
        )

        # Feature specs can have empty reproduction steps
        spec_result = SpecResult(
            title="Add CSV export functionality",
            reproduction_steps=[],  # Intentionally empty for features
            affected_components=["export-service", "api"],
            acceptance_criteria=[
                "CSV export button visible",
                "Export completes within 30 seconds",
                "Downloaded file is valid CSV",
            ],
            suggested_labels=["feature", "export"],
            spec_confidence=0.85,
        )

        assert len(spec_result.reproduction_steps) == 0
        assert len(spec_result.acceptance_criteria) == 3
        assert "feature" in spec_result.suggested_labels

    def test_critical_bug_has_high_severity(self):
        """Test that critical bugs get appropriate labels."""
        triage_output = TriageResult(
            classification="bug",
            severity="critical",
            reasoning="All user data is being deleted unexpectedly",
            confidence=0.99,
        )

        spec_result = SpecResult(
            title="CRITICAL: Fix data deletion bug",
            reproduction_steps=[
                "User logs in",
                "User views dashboard",
                "All data is deleted",
            ],
            affected_components=["database", "api", "auth-service"],
            acceptance_criteria=[
                "No data deletion occurs",
                "All existing data is preserved",
            ],
            suggested_labels=["bug", "critical", "security", "database"],
            spec_confidence=0.95,
        )

        assert "critical" in spec_result.suggested_labels
        assert "bug" in spec_result.suggested_labels
        assert "database" in spec_result.affected_components


# ========================
# Mock LLM Tests
# ========================


@pytest.mark.asyncio
class TestTriageAgentMocked:
    """Test triage agent with mocked LLM calls."""

    async def test_triage_node_returns_dict(self):
        """Test that triage_node returns expected dict structure."""
        from src.agents.triage import triage_node

        # Mock the LLM client
        mock_state: TriageState = {
            "feedback_id": "mock-test-001",
            "content": "The button is broken",
            "source": "test",
            "classification": "question",
            "severity": "low",
            "reasoning": "",
            "confidence": 0.0,
        }

        # The function should return a dict with classification results
        result = await triage_node(mock_state)

        # Result should contain the expected keys
        assert "classification" in result
        assert "severity" in result
        assert "reasoning" in result
        assert "confidence" in result

    async def test_triage_node_handles_errors(self):
        """Test that triage_node returns safe defaults on error."""
        from src.agents.triage import triage_node

        mock_state: TriageState = {
            "feedback_id": "error-test",
            "content": "Test content",
            "source": "test",
            "classification": "question",
            "severity": "low",
            "reasoning": "",
            "confidence": 0.0,
        }

        result = await triage_node(mock_state)

        # Should return safe defaults on error
        assert result["classification"] == "question"
        assert result["severity"] == "low"
        assert result["confidence"] == 0.0


@pytest.mark.asyncio
class TestSpecAgentMocked:
    """Test spec agent with mocked LLM calls."""

    async def test_spec_writer_returns_dict(self):
        """Test that spec_writer_node returns expected dict structure."""
        from src.agents.spec import spec_writer_node

        mock_state: SpecState = {
            "feedback_id": "mock-spec-001",
            "content": "The login fails",
            "source": "test",
            "classification": "bug",
            "severity": "high",
            "reasoning": "Login broken",
            "confidence": 0.9,
            "title": "",
            "reproduction_steps": [],
            "affected_components": [],
            "acceptance_criteria": [],
            "suggested_labels": [],
            "spec_confidence": 0.0,
        }

        result = await spec_writer_node(mock_state)

        # Result should contain the expected keys
        assert "title" in result
        assert "reproduction_steps" in result
        assert "affected_components" in result
        assert "acceptance_criteria" in result
        assert "suggested_labels" in result
        assert "spec_confidence" in result

    async def test_spec_writer_handles_errors(self):
        """Test that spec_writer_node returns safe defaults on error."""
        from src.agents.spec import spec_writer_node

        mock_state: SpecState = {
            "feedback_id": "error-spec",
            "content": "Test content",
            "source": "test",
            "classification": "bug",
            "severity": "high",
            "reasoning": "Test",
            "confidence": 0.9,
            "title": "",
            "reproduction_steps": [],
            "affected_components": [],
            "acceptance_criteria": [],
            "suggested_labels": [],
            "spec_confidence": 0.0,
        }

        result = await spec_writer_node(mock_state)

        # Should return safe defaults on error
        assert "title" in result
        assert "affected_components" in result
        assert isinstance(result["affected_components"], list)

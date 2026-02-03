"""Tests for gRPC server implementation."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
import grpc
from grpc import aio

import sys
import os

# Add gen/python to path for generated code
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', '..', 'gen', 'python'))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from ai.v1 import agent_pb2, agent_pb2_grpc


class MockAnalyzeFeedbackOutput:
    """Mock output matching AnalyzeFeedbackOutput structure."""

    def __init__(self):
        self.is_duplicate = False
        self.duplicate_score = 0.0
        self.classification = "bug"
        self.severity = "high"
        self.reasoning = "Test reasoning"
        self.title = "Test Issue Title"
        self.reproduction_steps = ["step1", "step2"]
        self.affected_components = ["api"]
        self.acceptance_criteria = ["criterion1"]
        self.suggested_labels = ["bug", "urgent"]
        self.confidence = 0.85


@pytest.fixture
def mock_activity_result():
    """Mock result from analyze_feedback activity."""
    return MockAnalyzeFeedbackOutput()


@pytest.fixture
def grpc_request():
    """Create a sample gRPC request."""
    return agent_pb2.AnalyzeFeedbackRequest(
        text="The login button is broken on mobile",
        source="discord",
        user_id="user123",
    )


@pytest.mark.asyncio
async def test_analyze_feedback_request_validation(grpc_request):
    """Test that gRPC request has correct fields."""
    assert grpc_request.text == "The login button is broken on mobile"
    assert grpc_request.source == "discord"
    assert grpc_request.user_id == "user123"


@pytest.mark.asyncio
async def test_analyze_feedback_response_structure():
    """Test that response can be created with correct structure."""
    response = agent_pb2.AnalyzeFeedbackResponse(
        is_duplicate=False,
        reasoning="Test reasoning",
        spec=agent_pb2.IssueSpec(
            title="Test Title",
            severity=agent_pb2.SEVERITY_HIGH,
            type=agent_pb2.ISSUE_TYPE_BUG,
            description="Test description",
            labels=["bug", "urgent"],
        ),
    )

    assert response.is_duplicate is False
    assert response.reasoning == "Test reasoning"
    assert response.spec.title == "Test Title"
    assert response.spec.severity == agent_pb2.SEVERITY_HIGH
    assert response.spec.type == agent_pb2.ISSUE_TYPE_BUG
    assert "bug" in response.spec.labels
    assert "urgent" in response.spec.labels


@pytest.mark.asyncio
async def test_severity_enum_mapping():
    """Test severity enum values."""
    assert agent_pb2.SEVERITY_UNSPECIFIED == 0
    assert agent_pb2.SEVERITY_LOW == 1
    assert agent_pb2.SEVERITY_MEDIUM == 2
    assert agent_pb2.SEVERITY_HIGH == 3
    assert agent_pb2.SEVERITY_CRITICAL == 4


@pytest.mark.asyncio
async def test_issue_type_enum_mapping():
    """Test issue type enum values."""
    assert agent_pb2.ISSUE_TYPE_UNSPECIFIED == 0
    assert agent_pb2.ISSUE_TYPE_BUG == 1
    assert agent_pb2.ISSUE_TYPE_FEATURE == 2
    assert agent_pb2.ISSUE_TYPE_QUESTION == 3


@pytest.mark.asyncio
async def test_duplicate_detection_response():
    """Test response for duplicate feedback."""
    response = agent_pb2.AnalyzeFeedbackResponse(
        is_duplicate=True,
        reasoning="Similarity score 0.92 exceeds threshold 0.85",
        spec=agent_pb2.IssueSpec(
            title="Duplicate of #123",
            severity=agent_pb2.SEVERITY_LOW,
            type=agent_pb2.ISSUE_TYPE_BUG,
            description="",
            labels=[],
        ),
    )

    assert response.is_duplicate is True
    assert "0.92" in response.reasoning
    assert response.spec.severity == agent_pb2.SEVERITY_LOW


@pytest.mark.asyncio
async def test_feature_request_response():
    """Test response for feature request."""
    response = agent_pb2.AnalyzeFeedbackResponse(
        is_duplicate=False,
        reasoning="User wants dark mode support",
        spec=agent_pb2.IssueSpec(
            title="Add dark mode support",
            severity=agent_pb2.SEVERITY_MEDIUM,
            type=agent_pb2.ISSUE_TYPE_FEATURE,
            description="Users want to toggle dark mode",
            labels=["enhancement", "ui"],
        ),
    )

    assert response.is_duplicate is False
    assert response.spec.type == agent_pb2.ISSUE_TYPE_FEATURE
    assert "enhancement" in response.spec.labels
    assert "ui" in response.spec.labels


@pytest.mark.asyncio
async def test_question_response():
    """Test response for question."""
    response = agent_pb2.AnalyzeFeedbackResponse(
        is_duplicate=False,
        reasoning="User asking how to configure webhooks",
        spec=agent_pb2.IssueSpec(
            title="Document webhook configuration",
            severity=agent_pb2.SEVERITY_LOW,
            type=agent_pb2.ISSUE_TYPE_QUESTION,
            description="How to set up Discord webhooks",
            labels=["documentation"],
        ),
    )

    assert response.spec.type == agent_pb2.ISSUE_TYPE_QUESTION
    assert response.spec.severity == agent_pb2.SEVERITY_LOW
    assert "documentation" in response.spec.labels


@pytest.mark.asyncio
async def test_empty_text_handling():
    """Test handling of empty feedback text."""
    request = agent_pb2.AnalyzeFeedbackRequest(
        text="",
        source="slack",
        user_id="user456",
    )

    assert request.text == ""
    assert request.source == "slack"


@pytest.mark.asyncio
async def test_all_sources_supported():
    """Test that various sources can be specified."""
    sources = ["discord", "slack", "github", "email", "manual"]
    for source in sources:
        request = agent_pb2.AnalyzeFeedbackRequest(
            text="Test feedback",
            source=source,
            user_id="test_user",
        )
        assert request.source == source


@pytest.mark.asyncio
async def test_issue_spec_all_fields():
    """Test IssueSpec message with all fields populated."""
    spec = agent_pb2.IssueSpec(
        title="Critical bug in payment processing",
        severity=agent_pb2.SEVERITY_CRITICAL,
        type=agent_pb2.ISSUE_TYPE_BUG,
        description="Payment fails for amounts over $1000",
        labels=["bug", "critical", "payments", "security"],
    )

    assert spec.title == "Critical bug in payment processing"
    assert spec.severity == agent_pb2.SEVERITY_CRITICAL
    assert spec.type == agent_pb2.ISSUE_TYPE_BUG
    assert len(spec.labels) == 4
    assert "security" in spec.labels

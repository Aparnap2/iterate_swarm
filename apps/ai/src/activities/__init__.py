"""Temporal Activities for the AI Worker.

These activities are called by the Go-defined Workflow to perform AI processing.
"""

import structlog
from temporalio import activity
from pydantic import BaseModel, Field

from src.agents.spec import write_spec
from src.agents.triage import classify_feedback
from src.services.qdrant import get_qdrant_service

logger = structlog.get_logger(__name__)


# ========================
# Activity Inputs/Outputs
# ========================


class AnalyzeFeedbackInput(BaseModel):
    """Input for the AnalyzeFeedback activity."""

    feedback_id: str = Field(..., description="Unique feedback identifier")
    content: str = Field(..., description="The feedback text to analyze")
    source: str = Field(default="discord", description="Source of feedback")


class AnalyzeFeedbackOutput(BaseModel):
    """Output from the AnalyzeFeedback activity."""

    is_duplicate: bool = Field(..., description="Whether this is a duplicate")
    duplicate_score: float = Field(..., description="Similarity score if duplicate")

    classification: str = Field(..., description="bug/feature/question")
    severity: str = Field(..., description="low/medium/high/critical")
    reasoning: str = Field(..., description="Explanation of classification")

    title: str = Field(..., description="GitHub Issue title")
    reproduction_steps: list[str] = Field(default_factory=list)
    affected_components: list[str] = Field(default_factory=list)
    acceptance_criteria: list[str] = Field(default_factory=list)
    suggested_labels: list[str] = Field(default_factory=list)

    confidence: float = Field(..., description="Overall confidence score")


# ========================
# Activities
# ========================


@activity.defn(name="AnalyzeFeedback")
async def analyze_feedback(input: AnalyzeFeedbackInput) -> AnalyzeFeedbackOutput:
    """Analyze feedback: check duplicates, classify, and write spec.

    This is the main AI activity called by the Temporal Workflow.
    It chains together:
    1. Duplicate detection (Qdrant vector search)
    2. Triage classification (LangGraph)
    3. Spec generation (LangGraph)

    Args:
        input: Feedback to analyze

    Returns:
        Complete analysis result with classification and spec
    """
    activity.logger.info(
        "Analyzing feedback",
        feedback_id=input.feedback_id,
        source=input.source,
    )

    try:
        # Step 1: Check for duplicates
        qdrant = await get_qdrant_service()
        is_duplicate, score = await qdrant.check_duplicate(input.content)

        if is_duplicate:
            activity.logger.info(
                "Duplicate detected",
                feedback_id=input.feedback_id,
                score=score,
            )
            return AnalyzeFeedbackOutput(
                is_duplicate=True,
                duplicate_score=score,
                classification="duplicate",
                severity="low",
                reasoning=f"Duplicate of existing feedback (similarity: {score:.2f})",
                title=f"[DUPLICATE] {input.content[:80]}",
                confidence=score,
            )

        # Step 2: Triage classification
        triage_result = await classify_feedback(
            feedback_id=input.feedback_id,
            content=input.content,
            source=input.source,
        )

        activity.logger.info(
            "Triage complete",
            feedback_id=input.feedback_id,
            classification=triage_result.classification,
            severity=triage_result.severity,
        )

        # Step 3: Write spec
        spec_result = await write_spec(
            feedback_id=input.feedback_id,
            content=input.content,
            source=input.source,
            classification=triage_result.classification,
            severity=triage_result.severity,
            reasoning=triage_result.reasoning,
            confidence=triage_result.confidence,
        )

        activity.logger.info(
            "Spec written",
            feedback_id=input.feedback_id,
            title=spec_result.title,
        )

        # Step 4: Index the feedback for future duplicate detection
        await qdrant.index_feedback(
            feedback_id=input.feedback_id,
            text=input.content,
            metadata={
                "classification": triage_result.classification,
                "severity": triage_result.severity,
            },
        )

        # Calculate overall confidence
        overall_confidence = (triage_result.confidence + spec_result.spec_confidence) / 2

        return AnalyzeFeedbackOutput(
            is_duplicate=False,
            duplicate_score=0.0,
            classification=triage_result.classification,
            severity=triage_result.severity,
            reasoning=triage_result.reasoning,
            title=spec_result.title,
            reproduction_steps=spec_result.reproduction_steps,
            affected_components=spec_result.affected_components,
            acceptance_criteria=spec_result.acceptance_criteria,
            suggested_labels=spec_result.suggested_labels,
            confidence=overall_confidence,
        )

    except Exception as e:
        activity.logger.error(
            "Analysis failed",
            feedback_id=input.feedback_id,
            error=str(e),
        )
        # Return safe defaults on error
        return AnalyzeFeedbackOutput(
            is_duplicate=False,
            duplicate_score=0.0,
            classification="question",
            severity="low",
            reasoning=f"Analysis failed: {str(e)}. Defaulting to question.",
            title=f"[MANUAL REVIEW] {input.content[:80]}",
            confidence=0.0,
        )

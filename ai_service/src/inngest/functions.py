"""Inngest workflow functions for feedback processing pipeline.

This module contains the workflow that processes feedback through:
1. Triage classification (no DB needed)
2. Duplicate check via vector search
3. Spec writing
4. Callback to web app to save draft issue
"""

import logging
from typing import Any, TypedDict

import structlog
from inngest import Context, Step

from src.agents.spec import spec_writer_node, SpecState
from src.agents.triage import triage_node, TriageState
from src.client.callback import get_callback_client
from src.core.config import settings
from src.inngest.client import (
    get_inngest_client,
    send_feedback_processed,
)
from src.services.github import get_github_service
from src.services.qdrant import get_vector_service

logger = structlog.get_logger(__name__)


# ========================
# Workflow State
# ========================


class WorkflowState(TypedDict):
    """State for the feedback processing workflow."""

    feedback_id: str
    content: str
    source: str
    timestamp: str

    # Triage results
    classification: str
    severity: str
    triage_reasoning: str
    triage_confidence: float

    # Duplicate check
    is_duplicate: bool
    duplicate_of: str | None

    # Spec results
    spec_title: str
    reproduction_steps: list[str]
    affected_components: list[str]
    acceptance_criteria: list[str]
    suggested_labels: list[str]
    spec_confidence: float

    # Final state
    github_issue_url: str | None
    processing_complete: bool


# ========================
# Workflow Function
# ========================


def create_process_feedback_workflow():
    """Create the process_feedback workflow function.

    Returns:
        Inngest workflow function configured with steps
    """
    from inngest import Function

    client = get_inngest_client()

    @client.create_function(
        fn_id="process_feedback",
        trigger={"event": "feedback/received"},
    )
    async def process_feedback(
        ctx: Context,
        input: dict[str, Any],
    ) -> dict[str, Any]:
        """Process incoming feedback through the full pipeline.

        Steps:
        1. Run triage classification (stateless)
        2. Check for duplicates via vector search
        3. Write spec (if not duplicate/question)
        4. Callback to web app to save draft issue

        Args:
            ctx: Inngest context with step execution
            input: Event data containing feedback

        Returns:
            Processing results
        """
        feedback_id = input.get("feedback_id", "")
        content = input.get("content", "")
        source = input.get("source", "unknown")
        timestamp = input.get("timestamp", "")

        logger.info(
            "Processing feedback workflow started",
            feedback_id=feedback_id,
            source=source,
        )

        # Step 1: Triage classification (stateless - no DB)
        triage_state: TriageState = {
            "feedback_id": feedback_id,
            "content": content,
            "source": source,
            "classification": "question",
            "severity": "low",
            "reasoning": "",
            "confidence": 0.0,
        }

        triage_result = await Step.run(
            ctx,
            "triage_classification",
            triage_node,
            triage_state,
        )

        classification = triage_result["classification"]
        severity = triage_result["severity"]
        triage_reasoning = triage_result["reasoning"]
        triage_confidence = triage_result["confidence"]

        logger.info(
            "Triage complete",
            feedback_id=feedback_id,
            classification=classification,
            severity=severity,
        )

        # Step 2: Check for duplicates (skip questions from deduplication)
        is_duplicate = False
        duplicate_of = None

        if classification != "question":
            is_duplicate, duplicate_of = await Step.run(
                ctx,
                "check_duplicates",
                _check_duplicates_wrapper,
                {"content": content, "threshold": 0.85},
            )

            if is_duplicate:
                logger.info(
                    "Duplicate detected",
                    feedback_id=feedback_id,
                    duplicate_of=duplicate_of,
                )

                # Send completion event (web app handles duplicate marking)
                await send_feedback_processed(
                    feedback_id=feedback_id,
                    classification=classification,
                    severity=severity,
                    is_duplicate=True,
                    duplicate_of=duplicate_of,
                    spec_written=False,
                    github_issue_url=None,
                )

                return {
                    "feedback_id": feedback_id,
                    "classification": classification,
                    "severity": severity,
                    "is_duplicate": True,
                    "duplicate_of": duplicate_of,
                    "spec_title": "",
                    "github_issue_url": None,
                    "processing_complete": True,
                }

        # Step 3: Write spec (skip for questions)
        spec_title = ""
        reproduction_steps = []
        affected_components = []
        acceptance_criteria = []
        suggested_labels = []
        spec_confidence = 0.0

        if classification != "question":
            spec_state: SpecState = {
                "feedback_id": feedback_id,
                "content": content,
                "source": source,
                "classification": classification,
                "severity": severity,
                "reasoning": triage_reasoning,
                "confidence": triage_confidence,
                "title": "",
                "reproduction_steps": [],
                "affected_components": [],
                "acceptance_criteria": [],
                "suggested_labels": [],
                "spec_confidence": 0.0,
            }

            spec_result = await Step.run(
                ctx,
                "write_spec",
                spec_writer_node,
                spec_state,
            )

            spec_title = spec_result["title"]
            reproduction_steps = spec_result["reproduction_steps"]
            affected_components = spec_result["affected_components"]
            acceptance_criteria = spec_result["acceptance_criteria"]
            suggested_labels = spec_result["suggested_labels"]
            spec_confidence = spec_result["spec_confidence"]

            logger.info(
                "Spec written",
                feedback_id=feedback_id,
                title=spec_title,
            )

            # Step 4: Callback to web app to save draft issue
            github_service = get_github_service()
            body = github_service.format_issue_body(
                content=content,
                source=source,
                feedback_id=feedback_id,
                reproduction_steps=reproduction_steps,
                acceptance_criteria=acceptance_criteria,
                affected_components=affected_components,
            )

            labels = suggested_labels + [classification, severity]

            await Step.run(
                ctx,
                "save_issue_to_webapp",
                _save_issue_wrapper,
                {
                    "feedback_id": feedback_id,
                    "content": content,
                    "title": spec_title,
                    "body": body,
                    "classification": classification,
                    "severity": severity,
                    "reasoning": triage_reasoning,
                    "confidence": triage_confidence,
                    "reproduction_steps": reproduction_steps,
                    "affected_components": affected_components,
                    "acceptance_criteria": acceptance_criteria,
                    "suggested_labels": labels,
                },
            )

            logger.info(
                "Saved issue draft to web app",
                feedback_id=feedback_id,
                title=spec_title,
            )

            # Step 5: Index in vector store for future duplicate detection
            vector_service = await get_vector_service()
            await Step.run(
                ctx,
                "index_feedback",
                _index_feedback_wrapper,
                {
                    "id": feedback_id,
                    "text": content,
                    "metadata": {
                        "classification": classification,
                        "severity": severity,
                        "source": source,
                    },
                },
            )

        # Step 6: Send completion event
        await send_feedback_processed(
            feedback_id=feedback_id,
            classification=classification,
            severity=severity,
            is_duplicate=is_duplicate,
            duplicate_of=duplicate_of,
            spec_written=bool(spec_title),
            github_issue_url=None,  # Not published yet, waiting for approval
        )

        return {
            "feedback_id": feedback_id,
            "classification": classification,
            "severity": severity,
            "is_duplicate": is_duplicate,
            "duplicate_of": duplicate_of,
            "spec_title": spec_title,
            "github_issue_url": None,
            "processing_complete": True,
        }

    return process_feedback


# ========================
# Step Wrappers for Inngest
# ========================


async def _check_duplicates_wrapper(data: dict[str, Any]) -> tuple[bool, str | None]:
    """Wrapper for duplicate check to work with Step.run."""
    vector_service = await get_vector_service()
    return await vector_service.search_similar(
        text=data["content"],
        threshold=data.get("threshold", 0.85),
    )


async def _save_issue_wrapper(data: dict[str, Any]) -> bool:
    """Wrapper for saving issue to web app via callback API."""
    callback_client = await get_callback_client()
    return await callback_client.save_issue(
        feedback_id=data["feedback_id"],
        content=data["content"],
        title=data["title"],
        body=data["body"],
        classification=data["classification"],
        severity=data["severity"],
        reasoning=data["reasoning"],
        confidence=data["confidence"],
        reproduction_steps=data.get("reproduction_steps", []),
        affected_components=data.get("affected_components", []),
        acceptance_criteria=data.get("acceptance_criteria", []),
        suggested_labels=data.get("suggested_labels", []),
    )


async def _index_feedback_wrapper(data: dict[str, Any]) -> bool:
    """Wrapper for indexing to work with Step.run."""
    vector_service = await get_vector_service()
    return await vector_service.index_item(
        id=data["id"],
        text=data["text"],
        metadata=data.get("metadata"),
    )


# ========================
# Workflow Registration
# ========================


def register_workflows():
    """Register all Inngest workflow functions.

    Call this at app startup to register workflows with Inngest.
    """
    process_feedback = create_process_feedback_workflow()

    return {
        "process_feedback": process_feedback,
    }

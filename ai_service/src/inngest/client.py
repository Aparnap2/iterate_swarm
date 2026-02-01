"""Inngest client and event types for workflow orchestration."""

import logging
from typing import Any

import structlog
from inngest import Event, Inngest

from src.core.config import settings

logger = structlog.get_logger(__name__)

# Inngest client singleton
_inngest_client: Inngest | None = None


def get_inngest_client() -> Inngest:
    """Get or create the Inngest client.

    Returns:
        Configured Inngest client for workflow orchestration
    """
    global _inngest_client

    if _inngest_client is None:
        _inngest_client = Inngest(
            app_id=settings.inngest_app_id,
            # v4 SDK: use event_key for sending events
            event_key=settings.inngest_api_key.get_secret_value() if settings.inngest_api_key else None,
            api_base_url=settings.inngest_api_url or "https://api.inngest.com",
            # Set is_production based on debug setting
            is_production=not settings.debug,
        )
        logger.info(
            "Inngest client initialized",
            app_id=settings.inngest_app_id,
        )

    return _inngest_client


# ========================
# Event Schemas
# ========================


class FeedbackReceivedEvent(Event):
    """Event triggered when new feedback is received."""

    name: str = "feedback/received"
    data: dict[str, Any]

    model_config = {
        "json_schema_extra": {
            "properties": {
                "data": {
                    "feedback_id": {"type": "string"},
                    "content": {"type": "string"},
                    "source": {"type": "string"},
                    "timestamp": {"type": "string"},
                }
            }
        }
    }


class FeedbackProcessedEvent(Event):
    """Event triggered when feedback processing is complete."""

    name: str = "feedback/processed"
    data: dict[str, Any]

    model_config = {
        "json_schema_extra": {
            "properties": {
                "data": {
                    "feedback_id": {"type": "string"},
                    "classification": {"type": "string"},
                    "severity": {"type": "string"},
                    "is_duplicate": {"type": "boolean"},
                    "duplicate_of": {"type": ["string", "null"]},
                    "spec_written": {"type": "boolean"},
                    "github_issue_url": {"type": ["string", "null"]},
                }
            }
        }
    }


# ========================
# Event Sending Helpers
# ========================


async def send_feedback_received(feedback_id: str, content: str, source: str) -> None:
    """Send a feedback received event to Inngest.

    Args:
        feedback_id: Unique identifier for the feedback
        content: The feedback text
        source: Where the feedback came from
    """
    client = get_inngest_client()
    await client.send(
        FeedbackReceivedEvent(
            data={
                "feedback_id": feedback_id,
                "content": content,
                "source": source,
            }
        )
    )
    logger.info(
        "Sent feedback/received event",
        feedback_id=feedback_id,
    )


async def send_feedback_processed(
    feedback_id: str,
    classification: str,
    severity: str,
    is_duplicate: bool,
    duplicate_of: str | None,
    spec_written: bool,
    github_issue_url: str | None,
) -> None:
    """Send a feedback processed event to Inngest.

    Args:
        feedback_id: Unique identifier for the feedback
        classification: Bug/feature/question
        severity: low/medium/high/critical
        is_duplicate: Whether this was a duplicate
        duplicate_of: ID of the original if duplicate
        spec_written: Whether a spec was written
        github_issue_url: URL to created GitHub issue
    """
    client = get_inngest_client()
    await client.send(
        FeedbackProcessedEvent(
            data={
                "feedback_id": feedback_id,
                "classification": classification,
                "severity": severity,
                "is_duplicate": is_duplicate,
                "duplicate_of": duplicate_of,
                "spec_written": spec_written,
                "github_issue_url": github_issue_url,
            }
        )
    )
    logger.info(
        "Sent feedback/processed event",
        feedback_id=feedback_id,
        classification=classification,
    )

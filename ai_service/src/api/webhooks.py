"""Webhook API routes for Discord and Slack ingestion.

These endpoints receive feedback from external sources and publish
to Kafka for downstream processing.
"""

import structlog
from typing import Annotated
from fastapi import APIRouter, Depends, HTTPException, Request, status

from src.schemas.ingestion import (
    DiscordWebhookPayload,
    FeedbackItem,
    QueuedResponse,
    SlackWebhookPayload,
)
from src.services.kafka import KafkaService, KafkaServiceError, get_kafka_service

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/webhooks", tags=["webhooks"])


@router.post(
    "/discord",
    response_model=QueuedResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Receive Discord webhook",
    description="Receives feedback from Discord webhooks and queues for processing.",
)
async def discord_webhook(
    request: Request,
    payload: DiscordWebhookPayload,
    kafka: Annotated[KafkaService, Depends(get_kafka_service)],
) -> QueuedResponse:
    """Handle incoming Discord webhook.

    Validates the payload, creates a FeedbackItem, and publishes to Kafka.

    Args:
        request: The raw HTTP request (for logging headers if needed)
        payload: Parsed Discord webhook payload
        kafka: Injected Kafka service

    Returns:
        QueuedResponse with the feedback ID

    Raises:
        HTTPException: If Kafka publishing fails
    """
    # Extract feedback text
    feedback_text = payload.extract_feedback_text()

    if not feedback_text:
        logger.warning(
            "Discord webhook received with no content",
            discord_message_id=payload.id,
            discord_channel_id=payload.channel_id,
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No extractable content in webhook payload",
        )

    # Create feedback item
    feedback = FeedbackItem.from_discord(payload)

    # Publish to Kafka
    try:
        await kafka.publish(
            topic="feedback.raw",
            data=feedback.to_kafka_message(),
            message_id=str(feedback.id),
        )
    except KafkaServiceError as e:
        logger.error(
            "Failed to publish Discord feedback to Kafka",
            feedback_id=str(feedback.id),
            error=str(e),
        )
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Failed to queue feedback: {e.message}",
        )

    logger.info(
        "Discord feedback queued",
        feedback_id=str(feedback.id),
        discord_channel_id=payload.channel_id,
        content_preview=feedback_text[:100],
    )

    return QueuedResponse(
        id=feedback.id,
        topic="feedback.raw",
    )


@router.post(
    "/slack",
    response_model=QueuedResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Receive Slack webhook",
    description="Receives feedback from Slack webhooks and queues for processing.",
)
async def slack_webhook(
    request: Request,
    payload: SlackWebhookPayload,
    kafka: Annotated[KafkaService, Depends(get_kafka_service)],
) -> QueuedResponse:
    """Handle incoming Slack webhook.

    Validates the payload, creates a FeedbackItem, and publishes to Kafka.

    Args:
        request: The raw HTTP request
        payload: Parsed Slack webhook payload
        kafka: Injected Kafka service

    Returns:
        QueuedResponse with the feedback ID

    Raises:
        HTTPException: If Kafka publishing fails
    """
    # Extract feedback text
    feedback_text = payload.extract_feedback_text()

    if not feedback_text:
        logger.warning(
            "Slack webhook received with no content",
            slack_channel=payload.channel,
            slack_user_id=payload.user,
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No extractable content in webhook payload",
        )

    # Create feedback item
    feedback = FeedbackItem.from_slack(payload)

    # Publish to Kafka
    try:
        await kafka.publish(
            topic="feedback.raw",
            data=feedback.to_kafka_message(),
            message_id=str(feedback.id),
        )
    except KafkaServiceError as e:
        logger.error(
            "Failed to publish Slack feedback to Kafka",
            feedback_id=str(feedback.id),
            error=str(e),
        )
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Failed to queue feedback: {e.message}",
        )

    logger.info(
        "Slack feedback queued",
        feedback_id=str(feedback.id),
        slack_channel=payload.channel,
        content_preview=feedback_text[:100],
    )

    return QueuedResponse(
        id=feedback.id,
        topic="feedback.raw",
    )


@router.get(
    "/health",
    summary="Webhook health check",
    description="Quick health check for the webhook endpoints.",
)
async def webhook_health() -> dict[str, str]:
    """Health check for webhook endpoints."""
    return {"status": "webhookshealthy"}

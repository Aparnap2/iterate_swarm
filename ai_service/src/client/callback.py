"""Callback client for AI Service to send results back to Web App."""

import logging
from typing import Any

import httpx
import structlog

from src.core.config import settings

logger = structlog.get_logger(__name__)


class CallbackClient:
    """Client for calling back to the Web App's internal API."""

    def __init__(self, base_url: str | None = None) -> None:
        """Initialize the callback client.

        Args:
            base_url: Base URL of the web app (defaults to settings)
        """
        self._base_url = base_url or settings.web_app_url
        self._api_key = settings.internal_api_key.get_secret_value() if settings.internal_api_key else None
        self._client: httpx.AsyncClient | None = None

    async def _get_client(self) -> httpx.AsyncClient:
        """Get or create httpx client."""
        if self._client is None:
            self._client = httpx.AsyncClient(
                timeout=30.0,
                http2=True,
            )
        return self._client

    async def close(self) -> None:
        """Close the httpx client."""
        if self._client is not None:
            await self._client.aclose()
            self._client = None

    async def save_issue(
        self,
        feedback_id: str,
        content: str,
        title: str,
        body: str,
        classification: str,
        severity: str,
        reasoning: str,
        confidence: float,
        reproduction_steps: list[str],
        affected_components: list[str],
        acceptance_criteria: list[str],
        suggested_labels: list[str],
    ) -> bool:
        """Save issue to web app via internal API.

        Args:
            feedback_id: UUID of the feedback item
            content: Original feedback content
            title: Generated issue title
            body: Generated issue body
            classification: bug/feature/question
            severity: low/medium/high/critical
            reasoning: Triage reasoning
            confidence: Confidence score
            reproduction_steps: List of reproduction steps
            affected_components: List of affected components
            acceptance_criteria: List of acceptance criteria
            suggested_labels: List of suggested labels

        Returns:
            True if successful
        """
        client = await self._get_client()
        url = f"{self._base_url}/api/internal/save-issue"

        payload = {
            "feedbackId": feedback_id,
            "content": content,
            "title": title,
            "body": body,
            "classification": classification,
            "severity": severity,
            "reasoning": reasoning,
            "confidence": confidence,
            "reproductionSteps": reproduction_steps,
            "affectedComponents": affected_components,
            "acceptanceCriteria": acceptance_criteria,
            "labels": suggested_labels,
        }

        try:
            response = await client.post(
                url,
                json=payload,
                headers={
                    "Authorization": f"Bearer {self._api_key}",
                    "Content-Type": "application/json",
                },
            )

            if response.status_code == 200:
                result = response.json()
                logger.info(
                    "Issue saved successfully",
                    feedback_id=feedback_id,
                    issue_id=result.get("issueId"),
                )
                return True
            else:
                logger.error(
                    "Failed to save issue",
                    feedback_id=feedback_id,
                    status_code=response.status_code,
                    response=response.text[:500],
                )
                return False

        except httpx.RequestError as e:
            logger.error(
                "Callback request failed",
                feedback_id=feedback_id,
                error=str(e),
            )
            return False
        except Exception as e:
            logger.error(
                "Unexpected error in callback",
                feedback_id=feedback_id,
                error=str(e),
            )
            return False

    async def __aenter__(self) -> "CallbackClient":
        return self

    async def __aexit__(self, *args: Any) -> None:
        await self.close()


# Singleton
_callback_client: CallbackClient | None = None


async def get_callback_client() -> CallbackClient:
    """Get or create the callback client."""
    global _callback_client
    if _callback_client is None:
        _callback_client = CallbackClient()
    return _callback_client

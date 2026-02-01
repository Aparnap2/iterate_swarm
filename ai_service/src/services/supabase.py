"""Supabase Service for persistence layer.

This service handles:
- Raw feedback storage and retrieval
- Issue draft management
- Status updates for the approval flow
"""

import logging
from datetime import datetime, timezone
from typing import Any
from uuid import UUID

import structlog
from supabase import AsyncClient, create_client
from supabase.lib.client_options import SyncClientOptions

from src.core.config import settings
from src.schemas.ingestion import FeedbackItem

logger = structlog.get_logger(__name__)


class SupabaseServiceError(Exception):
    """Base exception for Supabase service errors."""

    def __init__(self, message: str, details: dict[str, Any] | None = None) -> None:
        self.message = message
        self.details = details or {}
        super().__init__(self.message)


class SupabaseService:
    """Service for interacting with Supabase database."""

    def __init__(
        self,
        client: AsyncClient | None = None,
    ) -> None:
        """Initialize the Supabase service.

        Args:
            client: Optional Supabase client (for dependency injection in tests)
        """
        self._client = client
        self._supabase_url = settings.supabase_url
        self._supabase_key = settings.supabase_key.get_secret_value()

    async def _get_client(self) -> AsyncClient:
        """Get or create the Supabase client."""
        if self._client is None:
            options = SyncClientOptions()
            self._client = create_client(
                self._supabase_url,
                self._supabase_key,
                options=options,
            )
        return self._client

    async def close(self) -> None:
        """Close the Supabase client."""
        if self._client is not None:
            self._client = None

    async def __aenter__(self) -> "SupabaseService":
        return self

    async def __aexit__(self, *args: Any) -> None:
        await self.close()

    async def save_raw_feedback(
        self,
        feedback: FeedbackItem,
    ) -> str:
        """Save raw feedback to the database.

        Args:
            feedback: The feedback item to save

        Returns:
            The UUID of the saved feedback item
        """
        client = await self._get_client()

        try:
            data = {
                "id": str(feedback.id),
                "source": feedback.source.value if hasattr(feedback.source, "value") else feedback.source,
                "raw_content": feedback.raw_content,
                "processed_content": feedback.processed_content,
                "metadata": feedback.metadata or {},
                "status": "pending",
                "created_at": feedback.timestamp.isoformat(),
            }

            result = await client.table("feedback_items").insert(data).execute()

            if result.data:
                logger.info(
                    "Saved raw feedback",
                    feedback_id=str(feedback.id),
                )
                return str(feedback.id)
            else:
                raise SupabaseServiceError(
                    "Failed to save feedback",
                    {"response": result},
                )

        except Exception as e:
            logger.error(
                "Failed to save raw feedback",
                feedback_id=str(feedback.id),
                error=str(e),
            )
            raise SupabaseServiceError(f"Failed to save feedback: {e}") from e

    async def get_feedback_by_id(self, feedback_id: str) -> dict[str, Any] | None:
        """Get feedback item by ID.

        Args:
            feedback_id: UUID of the feedback item

        Returns:
            Feedback data or None if not found
        """
        client = await self._get_client()

        try:
            result = await client.table("feedback_items").select("*").eq("id", feedback_id).execute()

            if result.data:
                return result.data[0]
            return None

        except Exception as e:
            logger.error(
                "Failed to get feedback",
                feedback_id=feedback_id,
                error=str(e),
            )
            raise SupabaseServiceError(f"Failed to get feedback: {e}") from e

    async def mark_as_duplicate(
        self,
        feedback_id: str,
        existing_issue_id: str,
    ) -> bool:
        """Mark feedback as duplicate and link to existing issue.

        Args:
            feedback_id: UUID of the duplicate feedback
            existing_issue_id: UUID of the original issue

        Returns:
            True if successful
        """
        client = await self._get_client()

        try:
            data = {
                "is_duplicate": True,
                "duplicate_of": existing_issue_id,
                "status": "ignored",
                "processed_at": datetime.now(timezone.utc).isoformat(),
            }

            result = await client.table("feedback_items").update(data).eq("id", feedback_id).execute()

            logger.info(
                "Marked feedback as duplicate",
                feedback_id=feedback_id,
                original_issue_id=existing_issue_id,
            )
            return True

        except Exception as e:
            logger.error(
                "Failed to mark as duplicate",
                feedback_id=feedback_id,
                error=str(e),
            )
            raise SupabaseServiceError(f"Failed to mark as duplicate: {e}") from e

    async def save_issue_draft(
        self,
        feedback_id: str,
        title: str,
        body: str,
        triage_data: dict[str, Any],
        spec_data: dict[str, Any],
        labels: list[str],
    ) -> str:
        """Save an issue draft to the database.

        Args:
            feedback_id: UUID of the source feedback
            title: Issue title
            body: Issue body (Markdown)
            triage_data: Classification results
            spec_data: Spec generation results
            labels: Suggested GitHub labels

        Returns:
            The UUID of the created issue
        """
        client = await self._get_client()

        try:
            data = {
                "feedback_id": feedback_id,
                "title": title,
                "body": body,
                "status": "draft",
                "labels": labels,
                "triage_classification": triage_data.get("classification"),
                "triage_severity": triage_data.get("severity"),
                "triage_reasoning": triage_data.get("reasoning"),
                "triage_confidence": triage_data.get("confidence"),
                "spec_reproduction_steps": spec_data.get("reproduction_steps", []),
                "spec_affected_components": spec_data.get("affected_components", []),
                "spec_acceptance_criteria": spec_data.get("acceptance_criteria", []),
                "spec_confidence": spec_data.get("spec_confidence"),
            }

            result = await client.table("issues").insert(data).execute()

            if result.data:
                issue_id = result.data[0]["id"]
                logger.info(
                    "Saved issue draft",
                    issue_id=issue_id,
                    feedback_id=feedback_id,
                )
                return issue_id
            else:
                raise SupabaseServiceError(
                    "Failed to save issue draft",
                    {"response": result},
                )

        except Exception as e:
            logger.error(
                "Failed to save issue draft",
                feedback_id=feedback_id,
                error=str(e),
            )
            raise SupabaseServiceError(f"Failed to save issue draft: {e}") from e

    async def get_drafts(self) -> list[dict[str, Any]]:
        """Get all issue drafts.

        Returns:
            List of draft issues with feedback info
        """
        client = await self._get_client()

        try:
            result = (
                await client.table("issues")
                .select("*, feedback_items(source, raw_content, classification, severity)")
                .eq("status", "draft")
                .order("created_at", desc=True)
                .execute()
            )

            logger.debug(
                "Retrieved drafts",
                count=len(result.data or []),
            )
            return result.data or []

        except Exception as e:
            logger.error(
                "Failed to get drafts",
                error=str(e),
            )
            raise SupabaseServiceError(f"Failed to get drafts: {e}") from e

    async def get_issue_by_id(self, issue_id: str) -> dict[str, Any] | None:
        """Get issue by ID with feedback info.

        Args:
            issue_id: UUID of the issue

        Returns:
            Issue data with feedback info or None
        """
        client = await self._get_client()

        try:
            result = (
                await client.table("issues")
                .select("*, feedback_items(*)")
                .eq("id", issue_id)
                .execute()
            )

            if result.data:
                return result.data[0]
            return None

        except Exception as e:
            logger.error(
                "Failed to get issue",
                issue_id=issue_id,
                error=str(e),
            )
            raise SupabaseServiceError(f"Failed to get issue: {e}") from e

    async def publish_issue(
        self,
        issue_id: str,
        github_url: str,
    ) -> bool:
        """Mark issue as published after GitHub creation.

        Args:
            issue_id: UUID of the issue
            github_url: URL of the created GitHub issue

        Returns:
            True if successful
        """
        client = await self._get_client()

        try:
            data = {
                "status": "published",
                "github_url": github_url,
            }

            result = await client.table("issues").update(data).eq("id", issue_id).execute()

            logger.info(
                "Published issue",
                issue_id=issue_id,
                github_url=github_url,
            )
            return True

        except Exception as e:
            logger.error(
                "Failed to publish issue",
                issue_id=issue_id,
                error=str(e),
            )
            raise SupabaseServiceError(f"Failed to publish issue: {e}") from e

    async def reject_issue(self, issue_id: str, reason: str | None = None) -> bool:
        """Reject an issue draft.

        Args:
            issue_id: UUID of the issue
            reason: Optional rejection reason

        Returns:
            True if successful
        """
        client = await self._get_client()

        try:
            data: dict[str, Any] = {
                "status": "rejected",
            }
            if reason:
                # Add rejection metadata to body
                data["body"] = f"**Rejected**: {reason}\n\n---\n\n"

            result = await client.table("issues").update(data).eq("id", issue_id).execute()

            logger.info(
                "Rejected issue",
                issue_id=issue_id,
            )
            return True

        except Exception as e:
            logger.error(
                "Failed to reject issue",
                issue_id=issue_id,
                error=str(e),
            )
            raise SupabaseServiceError(f"Failed to reject issue: {e}") from e

    async def update_feedback_status(
        self,
        feedback_id: str,
        status: str,
        classification: str | None = None,
        severity: str | None = None,
    ) -> bool:
        """Update feedback processing status.

        Args:
            feedback_id: UUID of the feedback
            status: New status (processing, processed)
            classification: Optional classification
            severity: Optional severity

        Returns:
            True if successful
        """
        client = await self._get_client()

        try:
            data: dict[str, Any] = {
                "status": status,
                "processed_at": datetime.now(timezone.utc).isoformat(),
            }
            if classification:
                data["classification"] = classification
            if severity:
                data["severity"] = severity

            await client.table("feedback_items").update(data).eq("id", feedback_id).execute()

            logger.info(
                "Updated feedback status",
                feedback_id=feedback_id,
                status=status,
            )
            return True

        except Exception as e:
            logger.error(
                "Failed to update feedback status",
                feedback_id=feedback_id,
                error=str(e),
            )
            raise SupabaseServiceError(f"Failed to update feedback status: {e}") from e


# Singleton for dependency injection
_supabase_service: SupabaseService | None = None


async def get_supabase_service() -> SupabaseService:
    """Dependency injection for SupabaseService.

    Returns:
        Singleton SupabaseService instance
    """
    global _supabase_service
    if _supabase_service is None:
        _supabase_service = SupabaseService()
    return _supabase_service

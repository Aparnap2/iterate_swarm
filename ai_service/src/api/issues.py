"""Issue Management API for the frontend.

These endpoints allow the frontend to:
- List all draft issues
- Get issue details
- Approve and publish issues to GitHub
- Reject issues
"""

import logging
from typing import Any

import structlog
from fastapi import APIRouter, Depends, HTTPException, status

from src.services.github import get_github_service, GitHubService
from src.services.supabase import get_supabase_service, SupabaseService

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/issues", tags=["issues"])


# ========================
# Pydantic Models
# ========================


from pydantic import BaseModel, Field


class IssueListResponse(BaseModel):
    """Response for listing issues."""

    issues: list[dict[str, Any]]
    total: int = Field(description="Total number of issues")


class IssueDetailResponse(BaseModel):
    """Response for issue details."""

    issue: dict[str, Any]
    feedback: dict[str, Any] | None = None


class ApproveRequest(BaseModel):
    """Request body for approving an issue."""

    custom_title: str | None = None
    custom_labels: list[str] | None = None


class ApproveResponse(BaseModel):
    """Response for approved issue."""

    status: str = "published"
    url: str
    issue_id: str


class RejectRequest(BaseModel):
    """Request body for rejecting an issue."""

    reason: str | None = None


class RejectResponse(BaseModel):
    """Response for rejected issue."""

    status: str = "rejected"
    issue_id: str


class ErrorResponse(BaseModel):
    """Error response."""

    error: str
    details: dict[str, Any] | None = None


# ========================
# API Endpoints
# ========================


@router.get(
    "",
    response_model=IssueListResponse,
    summary="List Issues",
    description="Returns all issues with their current status.",
)
async def list_issues(
    status_filter: str | None = None,
    supabase: SupabaseService = Depends(get_supabase_service),
) -> IssueListResponse:
    """List all issues or filter by status.

    Args:
        status_filter: Optional status filter (draft, approved, rejected, published)
        supabase: Supabase service instance

    Returns:
        List of issues with count
    """
    try:
        if status_filter and status_filter != "draft":
            # Filter by specific status
            client = await supabase._get_client()
            result = (
                await client.table("issues")
                .select("*, feedback_items(source, raw_content, classification, severity)")
                .eq("status", status_filter)
                .order("created_at", desc=True)
                .execute()
            )
            issues = result.data or []
        else:
            # Default: return drafts
            issues = await supabase.get_drafts()

        return IssueListResponse(
            issues=issues,
            total=len(issues),
        )

    except Exception as e:
        logger.error(
            "Failed to list issues",
            error=str(e),
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e),
        )


@router.get(
    "/{issue_id}",
    response_model=IssueDetailResponse,
    summary="Get Issue Details",
    description="Returns detailed information about a specific issue.",
)
async def get_issue(
    issue_id: str,
    supabase: SupabaseService = Depends(get_supabase_service),
) -> IssueDetailResponse:
    """Get details for a specific issue.

    Args:
        issue_id: UUID of the issue
        supabase: Supabase service instance

    Returns:
        Issue details with feedback info
    """
    try:
        issue = await supabase.get_issue_by_id(issue_id)

        if not issue:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Issue not found: {issue_id}",
            )

        # Extract feedback info if available
        feedback = issue.pop("feedback_items", None)

        return IssueDetailResponse(
            issue=issue,
            feedback=feedback,
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            "Failed to get issue",
            issue_id=issue_id,
            error=str(e),
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e),
        )


@router.post(
    "/{issue_id}/approve",
    response_model=ApproveResponse,
    summary="Approve and Publish Issue",
    description="Approves an issue draft and publishes it to GitHub.",
)
async def approve_issue(
    issue_id: str,
    request: ApproveRequest | None = None,
    supabase: SupabaseService = Depends(get_supabase_service),
    github: GitHubService = Depends(get_github_service),
) -> ApproveResponse:
    """Approve a draft issue and create it on GitHub.

    This endpoint:
    1. Fetches the issue details from Supabase
    2. Creates the issue on GitHub
    3. Updates the issue status to 'published' in Supabase

    Args:
        issue_id: UUID of the issue to approve
        request: Optional customization (title, labels)
        supabase: Supabase service instance
        github: GitHub service instance

    Returns:
        Published issue URL
    """
    request = request or ApproveRequest()

    try:
        # Step 1: Get issue from Supabase
        issue = await supabase.get_issue_by_id(issue_id)

        if not issue:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Issue not found: {issue_id}",
            )

        # Check if already published
        if issue["status"] == "published":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Issue is already published",
            )

        # Check if it's a draft
        if issue["status"] != "draft":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Cannot approve issue with status: {issue['status']}",
            )

        # Step 2: Create issue on GitHub
        # Use custom title if provided
        title = request.custom_title or issue["title"]

        # Merge custom labels with existing labels
        labels = issue.get("labels", [])
        if request.custom_labels:
            labels = list(set(labels + request.custom_labels))

        # Create on GitHub
        github_url = await github.create_issue(
            title=title,
            body=issue["body"],
            labels=labels if labels else None,
        )

        # Step 3: Update Supabase
        await supabase.publish_issue(
            issue_id=issue_id,
            github_url=github_url,
        )

        logger.info(
            "Issue approved and published",
            issue_id=issue_id,
            github_url=github_url,
        )

        return ApproveResponse(
            status="published",
            url=github_url,
            issue_id=issue_id,
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            "Failed to approve issue",
            issue_id=issue_id,
            error=str(e),
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e),
        )


@router.post(
    "/{issue_id}/reject",
    response_model=RejectResponse,
    summary="Reject Issue",
    description="Rejects a draft issue.",
)
async def reject_issue(
    issue_id: str,
    request: RejectRequest | None = None,
    supabase: SupabaseService = Depends(get_supabase_service),
) -> RejectResponse:
    """Reject a draft issue.

    This endpoint marks the issue as rejected in Supabase.

    Args:
        issue_id: UUID of the issue to reject
        request: Optional rejection reason
        supabase: Supabase service instance

    Returns:
        Rejection confirmation
    """
    request = request or RejectRequest()

    try:
        # Step 1: Get issue from Supabase
        issue = await supabase.get_issue_by_id(issue_id)

        if not issue:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Issue not found: {issue_id}",
            )

        # Check if already published
        if issue["status"] == "published":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot reject a published issue",
            )

        # Step 2: Reject in Supabase
        await supabase.reject_issue(
            issue_id=issue_id,
            reason=request.reason,
        )

        logger.info(
            "Issue rejected",
            issue_id=issue_id,
            reason=request.reason,
        )

        return RejectResponse(
            status="rejected",
            issue_id=issue_id,
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            "Failed to reject issue",
            issue_id=issue_id,
            error=str(e),
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e),
        )


@router.get(
    "/drafts/count",
    summary="Count Draft Issues",
    description="Returns the count of draft issues.",
)
async def count_drafts(
    supabase: SupabaseService = Depends(get_supabase_service),
) -> dict[str, int]:
    """Count draft issues for the frontend badge.

    Args:
        supabase: Supabase service instance

    Returns:
        Count of draft issues
    """
    try:
        drafts = await supabase.get_drafts()
        return {"count": len(drafts)}
    except Exception as e:
        logger.error(
            "Failed to count drafts",
            error=str(e),
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e),
        )

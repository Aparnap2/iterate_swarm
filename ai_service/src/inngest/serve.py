"""Inngest FastAPI integration for serving workflow handlers."""

import logging
from typing import Any

import structlog
from fastapi import APIRouter, Request, Response
from pydantic import BaseModel

from src.core.config import settings
from src.inngest.client import get_inngest_client

logger = structlog.get_logger(__name__)

# Inngest router for FastAPI
inngest_router = APIRouter()


# ========================
# Request/Response Models
# ========================


class InngestEventRequest(BaseModel):
    """Incoming Inngest event payload."""

    events: list[dict[str, Any]]


class InngestResponse(BaseModel):
    """Inngest API response."""

    ids: list[str]


# ========================
# Inngest API Endpoints
# ========================


@inngest_router.post("/inngest/api/{path:path}")
async def handle_inngest_request(request: Request, path: str) -> Response:
    """Handle all Inngest API requests.

    Supports:
    - POST /inngest/api/events - Send events
    - GET /inngest/api/fn - Get function info
    """
    client = get_inngest_client()

    try:
        # Read request body
        body = await request.body()

        # Route based on path
        if path == "events" or path.endswith("/events"):
            # Handle event sending
            from inngest.communication import SendEventsResponse

            inngest_response = await client._send_events(
                body=body,
                url=request.url,
                method=request.method,
                headers=dict(request.headers),
            )

            return Response(
                content=inngest_response.model_dump_json(),
                status_code=inngest_response.status,
                media_type="application/json",
            )

        elif path == "fn" or path.endswith("/fn"):
            # Handle function info
            from inngest.communication import GetFunctionResponse

            inngest_response = await client._get_function(
                body=body,
                url=request.url,
                method=request.method,
                headers=dict(request.headers),
            )

            return Response(
                content=inngest_response.model_dump_json(),
                status_code=inngest_response.status,
                media_type="application/json",
            )

        elif path == "runs" or path.endswith("/runs"):
            # Handle runs
            from inngest.communication import GetRunsResponse

            inngest_response = await client._get_runs(
                body=body,
                url=request.url,
                method=request.method,
                headers=dict(request.headers),
            )

            return Response(
                content=inngest_response.model_dump_json(),
                status_code=inngest_response.status,
                media_type="application/json",
            )

        else:
            return Response(
                content='{"error": "Not found"}',
                status_code=404,
                media_type="application/json",
            )

    except Exception as e:
        logger.error(
            "Inngest request handling error",
            path=path,
            error=str(e),
        )
        return Response(
            content=f'{{"error": "{str(e)}"}}',
            status_code=500,
            media_type="application/json",
        )


@inngest_router.get("/health")
async def health_check() -> dict[str, str]:
    """Health check endpoint."""
    return {"status": "healthy", "service": "iterate-swarm-ai"}

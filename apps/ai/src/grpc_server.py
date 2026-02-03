"""gRPC Server for AI Agent Service.

This module implements a gRPC server that exposes the AI analysis functionality
to the Go core service. It wraps the existing LangGraph-based analysis activities.
"""

import asyncio
import logging
import sys
from concurrent import futures
from typing import Optional

import grpc
from grpc import aio

# Add generated proto paths
sys.path.insert(0, '/home/aparna/Desktop/iterate_swarm/gen/python')

import ai.v1.agent_pb2 as pb2
import ai.v1.agent_pb2_grpc as pb2_grpc

from src.activities import AnalyzeFeedbackInput, AnalyzeFeedbackOutput
from src.agents.triage import classify_feedback
from src.services.qdrant import get_qdrant_service

logger = logging.getLogger(__name__)


class SeverityMapper:
    """Maps between string severities and proto enum values."""

    _MAP_TO_PROTO = {
        "low": pb2.SEVERITY_LOW,
        "medium": pb2.SEVERITY_MEDIUM,
        "high": pb2.SEVERITY_HIGH,
        "critical": pb2.SEVERITY_CRITICAL,
    }

    _MAP_FROM_PROTO = {
        pb2.SEVERITY_LOW: "low",
        pb2.SEVERITY_MEDIUM: "medium",
        pb2.SEVERITY_HIGH: "high",
        pb2.SEVERITY_CRITICAL: "critical",
    }

    @classmethod
    def to_proto(cls, severity: str) -> int:
        """Convert string severity to proto enum."""
        return cls._MAP_TO_PROTO.get(severity.lower(), pb2.SEVERITY_UNSPECIFIED)

    @classmethod
    def from_proto(cls, proto_value: int) -> str:
        """Convert proto enum to string severity."""
        return cls._MAP_FROM_PROTO.get(proto_value, "unspecified")


class IssueTypeMapper:
    """Maps between string types and proto enum values."""

    _MAP_TO_PROTO = {
        "bug": pb2.ISSUE_TYPE_BUG,
        "feature": pb2.ISSUE_TYPE_FEATURE,
        "question": pb2.ISSUE_TYPE_QUESTION,
    }

    _MAP_FROM_PROTO = {
        pb2.ISSUE_TYPE_BUG: "bug",
        pb2.ISSUE_TYPE_FEATURE: "feature",
        pb2.ISSUE_TYPE_QUESTION: "question",
    }

    @classmethod
    def to_proto(cls, issue_type: str) -> int:
        """Convert string type to proto enum."""
        return self._MAP_TO_PROTO.get(issue_type.lower(), pb2.ISSUE_TYPE_UNSPECIFIED)  # type: ignore

    @classmethod
    def from_proto(cls, proto_value: int) -> str:
        """Convert proto enum to string type."""
        return cls._MAP_FROM_PROTO.get(proto_value, "unspecified")


class AgentServicer(pb2_grpc.AgentServiceServicer):
    """gRPC servicer implementing the AgentService.

    This servicer wraps the existing LangGraph-based analysis activities
    and exposes them via gRPC for communication with the Go core service.
    """

    def __init__(self):
        """Initialize the servicer."""
        logger.info("Initializing AgentServicer")

    async def AnalyzeFeedback(
        self,
        request: pb2.AnalyzeFeedbackRequest,
        context: grpc.aio.ServicerContext,
    ) -> pb2.AnalyzeFeedbackResponse:
        """Analyze feedback and return structured issue spec.

        This method implements the AnalyzeFeedback RPC defined in agent.proto.
        It wraps the existing analyze_feedback activity but adapts the interface
        to use gRPC types instead of Temporal/Pydantic types.

        Args:
            request: gRPC request containing feedback text, source, and user_id
            context: gRPC context

        Returns:
            gRPC response containing IssueSpec, duplicate flag, and reasoning
        """
        logger.info(
            "AnalyzeFeedback called",
            text_preview=request.text[:50],
            source=request.source,
            user_id=request.user_id,
        )

        try:
            # Step 1: Check for duplicates using Qdrant
            qdrant = await get_qdrant_service()
            is_duplicate, score = await qdrant.check_duplicate(request.text)

            if is_duplicate:
                logger.info(
                    "Duplicate detected",
                    score=score,
                )
                return pb2.AnalyzeFeedbackResponse(
                    is_duplicate=True,
                    reasoning=f"Duplicate of existing feedback (similarity: {score:.2f})",
                    spec=pb2.IssueSpec(
                        title=f"[DUPLICATE] {request.text[:80]}",
                        severity=pb2.SEVERITY_LOW,
                        type=pb2.ISSUE_TYPE_BUG,
                        description="",
                        labels=["duplicate"],
                    ),
                )

            # Step 2: Triage classification using LangGraph
            triage_result = await classify_feedback(
                feedback_id=f"grpc-{request.user_id}",
                content=request.text,
                source=request.source,
            )

            # Step 3: Index the feedback for future duplicate detection
            await qdrant.index_feedback(
                feedback_id=f"grpc-{request.user_id}",
                text=request.text,
                metadata={
                    "classification": triage_result.classification,
                    "severity": triage_result.severity,
                },
            )

            # Build the response with mapped severity
            severity_proto = SeverityMapper.to_proto(triage_result.severity)
            issue_type_proto = IssueTypeMapper.to_proto(triage_result.classification)

            # Map suggested labels based on classification
            labels = [triage_result.classification]
            if triage_result.severity in ("high", "critical"):
                labels.append("urgent")

            response = pb2.AnalyzeFeedbackResponse(
                is_duplicate=False,
                reasoning=triage_result.reasoning,
                spec=pb2.IssueSpec(
                    title=f"[{triage_result.classification.upper()}] {request.text[:80]}",
                    severity=severity_proto,
                    type=issue_type_proto,
                    description=f"Analysis by {request.source} user {request.user_id}",
                    labels=labels,
                ),
            )

            logger.info(
                "Analysis complete",
                classification=triage_result.classification,
                severity=triage_result.severity,
                confidence=triage_result.confidence,
            )

            return response

        except Exception as e:
            logger.error(
                "Analysis failed",
                error=str(e),
            )
            # Return error response
            context.set_code(grpc.StatusCode.INTERNAL)
            context.set_details(f"Analysis failed: {str(e)}")
            return pb2.AnalyzeFeedbackResponse(
                is_duplicate=False,
                reasoning=f"Analysis failed: {str(e)}",
                spec=pb2.IssueSpec(
                    title=f"[ERROR] {request.text[:80]}",
                    severity=pb2.SEVERITY_LOW,
                    type=pb2.ISSUE_TYPE_QUESTION,
                    description="",
                    labels=["error"],
                ),
            )


async def serve(port: str = "[::]:50051") -> grpc.aio.Server:
    """Create and start the gRPC server.

    Args:
        port: gRPC server address to listen on

    Returns:
        The running gRPC server instance
    """
    server = grpc.aio.server(futures.ThreadPoolExecutor(max_workers=10))
    pb2_grpc.add_AgentServiceServicer_to_server(AgentServicer(), server)
    server.add_insecure_port(port)

    logger.info(f"Starting gRPC server on {port}")
    await server.start()
    logger.info("gRPC server started successfully")

    return server


async def run_server():
    """Run the gRPC server with proper shutdown handling."""
    server = await serve()

    # Graceful shutdown
    def signal_handler():
        logger.info("Received shutdown signal")
        return server.stop(grace=5)

    try:
        await server.wait_for_termination()
    except KeyboardInterrupt:
        logger.info("Shutting down gRPC server...")
        await server.stop(grace=5)


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )
    asyncio.run(run_server())

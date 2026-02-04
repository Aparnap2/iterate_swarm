"""Main entry point for the AI service.

This module supports running:
1. Temporal worker (default) - listens to AI_TASK_QUEUE
2. gRPC server - serves gRPC requests from Go core
3. Both services concurrently
"""

import asyncio
import logging
import signal
import sys
from concurrent import futures
from typing import Optional

import structlog
import grpc
from temporalio.client import Client
from temporalio.worker import Worker

from src.activities import analyze_feedback
from src.config import get_config
from src.grpc_server import serve as start_grpc_server, AgentServicer

# Import generated proto
import os
_PROTO_PATH = os.path.join(os.path.dirname(__file__), '..', '..', '..', 'gen', 'python')
sys.path.insert(0, _PROTO_PATH)
import ai.v1.agent_pb2_grpc as pb2_grpc

logger = structlog.get_logger(__name__)


async def run_temporal_worker():
    """Run the Temporal worker for AI activities."""
    config = get_config()

    logger.info(
        "Starting Temporal Worker",
        address=config.temporal.address,
        task_queue=config.temporal.task_queue,
        namespace=config.temporal.namespace,
    )

    # Connect to Temporal server
    client = await Client.connect(
        target=config.temporal.address,
        namespace=config.temporal.namespace,
    )

    # Create worker
    worker = Worker(
        client,
        task_queue=config.temporal.task_queue,
        activities=[analyze_feedback],
    )

    logger.info("Temporal Worker started, waiting for tasks...")
    await worker.run()


async def run_grpc_server(port: str = "[::]:50051"):
    """Run the gRPC server."""
    logger.info(f"Starting gRPC server on {port}")
    server = grpc.aio.server(futures.ThreadPoolExecutor(max_workers=10))
    pb2_grpc.add_AgentServiceServicer_to_server(AgentServicer(), server)
    server.add_insecure_port(port)
    await server.start()
    logger.info("gRPC server started successfully")
    await server.wait_for_termination()


async def run_both(grpc_port: str = "[::]:50051"):
    """Run both Temporal worker and gRPC server concurrently."""
    logger.info("Starting both Temporal Worker and gRPC server")

    # Run both concurrently
    await asyncio.gather(
        run_temporal_worker(),
        run_grpc_server(grpc_port),
    )


def parse_args():
    """Parse command line arguments."""
    import argparse

    parser = argparse.ArgumentParser(description="IterateSwarm AI Service")
    parser.add_argument(
        "--mode",
        choices=["temporal", "grpc", "both"],
        default="both",
        help="Which service to run (default: both)",
    )
    parser.add_argument(
        "--grpc-port",
        default="[::]:50051",
        help="gRPC server port (default: [::]:50051)",
    )

    return parser.parse_args()


def main():
    """Main entry point."""
    args = parse_args()

    # Configure structured logging
    structlog.configure()
    log = structlog.get_logger()

    log.info(
        "Starting IterateSwarm AI Service",
        mode=args.mode,
        grpc_port=args.grpc_port,
    )

    try:
        if args.mode == "temporal":
            asyncio.run(run_temporal_worker())
        elif args.mode == "grpc":
            asyncio.run(run_grpc_server(args.grpc_port))
        else:  # both
            asyncio.run(run_both(args.grpc_port))
    except KeyboardInterrupt:
        log.info("Service shutting down...")
    except Exception as e:
        log.error("Service error", error=str(e))
        raise


if __name__ == "__main__":
    main()

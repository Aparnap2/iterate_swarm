"""Temporal Worker for the AI Task Queue.

This worker listens to AI_TASK_QUEUE and executes AI activities
(AnalyzeFeedback) that are called from the Go-defined Workflow.
"""

import asyncio
import structlog
from temporalio.client import Client
from temporalio.worker import Worker

from src.activities import analyze_feedback
from src.config import get_config

logger = structlog.get_logger(__name__)


async def run_worker():
    """Run the Temporal worker for AI activities."""
    config = get_config()

    logger.info(
        "Starting AI Worker",
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
        activities=[
            analyze_feedback,
        ],
    )

    logger.info("AI Worker started, waiting for tasks...")

    # Run the worker
    await worker.run()


def main():
    """Entry point for the AI worker."""
    # Configure structured logging
    structlog.configure(
        wrapper_class=structlog.make_prevent_logging_config,
    )
    log = structlog.get_logger()

    try:
        log.info("Initializing AI Worker...")
        asyncio.run(run_worker())
    except KeyboardInterrupt:
        log.info("AI Worker shutting down...")
    except Exception as e:
        log.error("Worker error", error=str(e))
        raise


if __name__ == "__main__":
    main()

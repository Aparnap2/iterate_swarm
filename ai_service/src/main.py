"""IterateSwarm AI Service - Main Application Entry Point.

This FastAPI application handles:
- Webhook ingestion from Discord/Slack
- Event publishing to Upstash Kafka
- Workflow orchestration via Inngest
- LLM-powered agent processing
"""

from typing import Any

import structlog
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from src.api.webhooks import router as webhooks_router
from src.api.issues import router as issues_router
from src.core.config import settings
from src.inngest.serve import inngest_router
from src.inngest.functions import create_process_feedback_workflow
from src.services.kafka import get_kafka_service

# Configure structured logging
structlog.configure(
    wrapper_class=structlog.make_filtering_bound_logger(
        getattr(settings, "log_level", "INFO")
    ),
    processors=[
        structlog.stdlib.filter_by_level,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.stdlib.PositionalArgumentsFormatter(),
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        structlog.processors.UnicodeDecoder(),
        structlog.dev.ConsoleRenderer(),
    ],
    logger_factory=structlog.stdlib.LoggerFactory(),
    cache_logger_on_first_use=True,
)

logger = structlog.get_logger(__name__)

app = FastAPI(
    title=settings.app_name,
    version="0.1.0",
    description="IterateSwarm - AI Agent Swarm for Feedback Processing",
    debug=settings.debug,
)

# Include routers
app.include_router(webhooks_router)
app.include_router(issues_router)
app.include_router(inngest_router, prefix="")

# CORS Configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure appropriately for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
async def startup_event() -> None:
    """Validate configuration and register workflows."""
    logger.info(
        "Starting IterateSwarm AI Service",
        host=settings.app_host,
        port=settings.app_port,
        debug=settings.debug,
    )

    # Register Inngest workflows
    try:
        process_feedback = create_process_feedback_workflow()
        logger.info(
            "Inngest workflows registered",
            app_id=settings.inngest_app_id,
        )
    except Exception as e:
        logger.warning(
            "Failed to register Inngest workflows",
            error=str(e),
        )


@app.on_event("shutdown")
async def shutdown_event() -> None:
    """Cleanup on shutdown."""
    logger.info("Shutting down IterateSwarm AI Service")
    # Close Kafka client
    from src.services.kafka import _kafka_service
    if _kafka_service is not None:
        await _kafka_service.close()


@app.get("/health")
async def health_check() -> dict[str, str]:
    """Health check endpoint for load balancers and monitoring."""
    return {"status": "healthy", "service": settings.app_name}


@app.get("/")
async def root() -> dict[str, Any]:
    """Root endpoint with service information."""
    return {
        "service": settings.app_name,
        "version": "0.1.0",
        "status": "running",
    }

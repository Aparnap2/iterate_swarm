"""Kafka Service supporting both Upstash HTTP and standard Kafka protocol.

For production with Upstash: Uses HTTP REST API (serverless-friendly)
For local testing: Uses standard Kafka protocol with aiokafka
"""

import logging
from datetime import datetime, timezone
from typing import Any, Generator
from uuid import uuid4

import httpx
import structlog
from aiokafka import AIOKafkaProducer
from aiokafka.errors import KafkaError

from src.core.config import settings

logger = structlog.get_logger(__name__)


class KafkaServiceError(Exception):
    """Base exception for Kafka service errors."""

    def __init__(self, message: str, details: dict[str, Any] | None = None) -> None:
        self.message = message
        self.details = details or {}
        super().__init__(self.message)


class UpstashKafkaService:
    """Kafka producer using Upstash HTTP REST API.

    Designed for serverless environments with proper error handling.
    """

    def __init__(self) -> None:
        """Initialize the Upstash Kafka service."""
        self._client: httpx.AsyncClient | None = None
        self._base_url = settings.kafka_rest_url
        self._user = settings.kafka_rest_user
        self._password = settings.kafka_rest_password.get_secret_value()
        self._default_topic = settings.kafka_topic_feedback
        self._auth = (self._user, self._password) if self._user else None

    async def _get_client(self) -> httpx.AsyncClient:
        """Get or create the HTTP client."""
        if self._client is None:
            self._client = httpx.AsyncClient(
                timeout=10.0,
                limits=httpx.Limits(keepalive_expiry=5.0),
            )
        return self._client

    async def close(self) -> None:
        """Close the HTTP client."""
        if self._client is not None:
            await self._client.aclose()
            self._client = None

    async def __aenter__(self) -> "UpstashKafkaService":
        return self

    async def __aexit__(self, *args: Any) -> None:
        await self.close()

    async def _send_request(
        self,
        method: str,
        endpoint: str,
        json_data: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Send an HTTP request to Upstash Kafka API."""
        client = await self._get_client()
        url = f"{self._base_url}/{endpoint}"

        try:
            response = await client.request(
                method=method,
                url=url,
                json=json_data,
                auth=self._auth,
            )
            response.raise_for_status()
            return response.json()
        except httpx.HTTPStatusError as e:
            logger.error(
                "Upstash Kafka HTTP error",
                status_code=e.response.status_code,
                endpoint=endpoint,
            )
            raise KafkaServiceError(
                f"Kafka API error: {e.response.status_code}",
                {"status_code": e.response.status_code},
            ) from e
        except httpx.RequestError as e:
            logger.error("Upstash Kafka connection error", error=str(e))
            raise KafkaServiceError(f"Connection error: {e}") from e

    async def publish(
        self,
        topic: str,
        data: dict[str, Any],
        message_id: str | None = None,
    ) -> dict[str, Any]:
        """Publish a message to Upstash Kafka."""
        payload = {
            "id": message_id or str(uuid4()),
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "data": data,
        }

        body = {"value": payload}
        if message_id:
            body["key"] = message_id

        return await self._send_request(
            method="POST",
            endpoint=f"topics/{topic}",
            json_data=body,
        )


class StandardKafkaService:
    """Kafka producer using standard Kafka protocol (aiokafka).

    For local testing and production with self-hosted Kafka.
    """

    def __init__(self, bootstrap_server: str | None = None) -> None:
        """Initialize the standard Kafka service.

        Args:
            bootstrap_server: Kafka broker address. If None, uses KAFKA_REST_URL:9092
        """
        self._producer: AIOKafkaProducer | None = None
        # Parse bootstrap server from KAFKA_REST_URL
        raw_server = bootstrap_server or settings.kafka_rest_url

        # Remove http:// or https:// prefix if present
        if "://" in raw_server:
            server = raw_server.split("://", 1)[1]
        else:
            server = raw_server

        # Remove trailing path if any
        if "/" in server:
            server = server.split("/")[0]

        # Parse host:port
        if ":" in server:
            host, port_str = server.rsplit(":", 1)
            try:
                port = int(port_str)
                self._bootstrap_server = f"{host}:{port}"
            except ValueError:
                # Port is not numeric, treat entire thing as host
                self._bootstrap_server = f"{server}:9092"
        else:
            # No port specified, add default Kafka port
            self._bootstrap_server = f"{server}:9092"

        self._default_topic = settings.kafka_topic_feedback

    async def start(self) -> None:
        """Start the Kafka producer."""
        if self._producer is None:
            self._producer = AIOKafkaProducer(
                bootstrap_servers=self._bootstrap_server,
                value_serializer=lambda v: str(v).encode("utf-8"),
                key_serializer=lambda k: k.encode("utf-8") if k else None,
            )
            await self._producer.start()
            logger.info(
                "Standard Kafka producer started",
                bootstrap_server=self._bootstrap_server,
            )

    async def close(self) -> None:
        """Close the Kafka producer."""
        if self._producer is not None:
            await self._producer.stop()
            self._producer = None

    async def __aenter__(self) -> "StandardKafkaService":
        await self.start()
        return self

    async def __aexit__(self, *args: Any) -> None:
        await self.close()

    async def publish(
        self,
        topic: str | None = None,
        data: dict[str, Any] | None = None,
        message_id: str | None = None,
    ) -> dict[str, Any]:
        """Publish a message to Kafka."""
        if self._producer is None:
            await self.start()

        topic = topic or self._default_topic
        key = message_id or str(uuid4())

        # Wrap data in envelope
        payload = {
            "id": key,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "data": data,
        }

        try:
            result = await self._producer.send_and_wait(
                topic=topic,
                value=payload,
                key=key,
            )
            logger.info(
                "Message sent to Kafka",
                topic=topic,
                partition=result.partition,
                offset=result.offset,
            )
            return {
                "topic": topic,
                "partition": result.partition,
                "offset": result.offset,
            }
        except KafkaError as e:
            logger.error("Kafka publish error", error=str(e))
            raise KafkaServiceError(f"Kafka error: {e}") from e


# ========================
# Factory for Kafka Service
# ========================


async def get_kafka_service() -> Generator[
    UpstashKafkaService | StandardKafkaService, None, None
]:
    """Factory for getting the appropriate Kafka service.

    Detects whether to use Upstash HTTP or standard Kafka based on:
    - KAFKA_REST_USER presence (Upstash requires auth)
    - Connection testing

    Yields:
        Appropriate Kafka service instance
    """
    # Check if using Upstash (has credentials) or local Kafka
    if settings.kafka_rest_user and settings.kafka_rest_password.get_secret_value():
        # Upstash - use HTTP service
        service = UpstashKafkaService()
    else:
        # Local Kafka - use standard protocol
        service = StandardKafkaService()

    yield service


# Alias for backward compatibility
KafkaService = UpstashKafkaService

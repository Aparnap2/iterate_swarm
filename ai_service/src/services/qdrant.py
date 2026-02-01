"""Vector Memory Service using Qdrant for semantic deduplication.

This service handles:
- Collection management for feedback embeddings
- Semantic search to detect duplicate feedback
- Indexing new feedback items
"""

import logging
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

import structlog
from langfuse import observe
from qdrant_client import AsyncQdrantClient
from qdrant_client.models import Distance, VectorParams

from src.core.config import settings

logger = structlog.get_logger(__name__)

# Vector size for OpenAI text-embedding-3-small
EMBEDDING_SIZE = 1536


class VectorService:
    """Service for managing vector embeddings and semantic search in Qdrant."""

    def __init__(
        self,
        client: AsyncQdrantClient | None = None,
        collection_name: str = "feedback_items",
    ) -> None:
        """Initialize the Vector Service.

        Args:
            client: Optional Qdrant client (for dependency injection in tests)
            collection_name: Name of the collection to use
        """
        self._client = client
        self._collection_name = collection_name
        self._qdrant_url = settings.qdrant_url
        self._qdrant_api_key = settings.qdrant_api_key

    async def _get_client(self) -> AsyncQdrantClient:
        """Get or create the Qdrant client."""
        if self._client is None:
            self._client = AsyncQdrantClient(
                url=self._qdrant_url,
                api_key=self._qdrant_api_key.get_secret_value() if self._qdrant_api_key else None,
            )
        return self._client

    async def close(self) -> None:
        """Close the Qdrant client."""
        if self._client is not None:
            await self._client.aclose()
            self._client = None

    async def __aenter__(self) -> "VectorService":
        return self

    async def __aexit__(self, *args: Any) -> None:
        await self.close()

    @observe(name="vector_service.ensure_collection")
    async def ensure_collection(self) -> bool:
        """Ensure the feedback collection exists with proper configuration.

        Returns:
            True if collection exists or was created successfully
        """
        client = await self._get_client()

        try:
            # Check if collection exists
            collections = await client.get_collections()
            collection_names = [c.name for c in collections.collections]

            if self._collection_name in collection_names:
                logger.info(
                    "Collection already exists",
                    collection=self._collection_name,
                )
                return True

            # Create collection with OpenAI-compatible vectors
            logger.info(
                "Creating collection",
                collection=self._collection_name,
                vector_size=EMBEDDING_SIZE,
            )

            await client.create_collection(
                collection_name=self._collection_name,
                vectors_config=VectorParams(
                    size=EMBEDDING_SIZE,
                    distance=Distance.COSINE,
                ),
            )

            logger.info(
                "Collection created successfully",
                collection=self._collection_name,
            )
            return True

        except Exception as e:
            logger.error(
                "Failed to ensure collection",
                collection=self._collection_name,
                error=str(e),
            )
            raise

    @observe(name="vector_service.search_similar")
    async def search_similar(
        self,
        text: str,
        threshold: float = 0.85,
        limit: int = 5,
    ) -> tuple[bool, str | None]:
        """Search for semantically similar feedback.

        Args:
            text: The text to search for
            threshold: Minimum similarity score (0-1) to consider a match
            limit: Maximum number of results to return

        Returns:
            Tuple of (is_duplicate, existing_id)
            - is_duplicate: True if a similar item was found
            - existing_id: The ID of the matching item if found
        """
        client = await self._get_client()

        # First, ensure collection exists
        await self.ensure_collection()

        try:
            # Generate embedding using OpenAI-compatible API
            embedding = await self._get_embedding(text)

            # Search for similar vectors
            results = await client.search(
                collection_name=self._collection_name,
                query_vector=embedding,
                limit=limit,
                score_threshold=threshold,
            )

            if results and len(results) > 0:
                best_match = results[0]
                logger.info(
                    "Found similar feedback",
                    score=best_match.score,
                    id=best_match.id,
                )
                return True, str(best_match.id)

            logger.debug(
                "No similar feedback found",
                threshold=threshold,
            )
            return False, None

        except Exception as e:
            logger.error(
                "Search failed",
                error=str(e),
            )
            # Return False on error to allow processing to continue
            return False, None

    @observe(name="vector_service.index_item")
    async def index_item(
        self,
        id: str,
        text: str,
        metadata: dict[str, Any] | None = None,
    ) -> bool:
        """Index a feedback item for future similarity search.

        Args:
            id: Unique identifier for this feedback
            text: The feedback text to embed and store
            metadata: Optional metadata to store with the vector

        Returns:
            True if indexing was successful
        """
        client = await self._get_client()

        # Ensure collection exists
        await self.ensure_collection()

        try:
            # Generate embedding
            embedding = await self._get_embedding(text)

            # Prepare payload with metadata
            payload: dict[str, Any] = {
                "text": text,
                "indexed_at": datetime.now(timezone.utc).isoformat(),
            }
            if metadata:
                payload.update(metadata)

            # Upsert the point
            from qdrant_client.models import PointStruct

            await client.upsert(
                collection_name=self._collection_name,
                points=[
                    PointStruct(
                        id=id,
                        vector=embedding,
                        payload=payload,
                    )
                ],
            )

            logger.info(
                "Indexed feedback item",
                id=id,
                text_preview=text[:100],
            )
            return True

        except Exception as e:
            logger.error(
                "Failed to index item",
                id=id,
                error=str(e),
            )
            raise

    async def _get_embedding(self, text: str) -> list[float]:
        """Get embedding for text using OpenAI-compatible API.

        Uses Ollama with nomic-embed-text for embeddings.
        """
        import httpx

        # Ollama embedding endpoint
        embedding_url = "http://localhost:11434/api/embeddings"

        async with httpx.AsyncClient(timeout=60.0) as http_client:
            response = await http_client.post(
                embedding_url,
                json={
                    "model": "nomic-embed-text:latest",
                    "text": text,
                },
            )
            response.raise_for_status()
            data = response.json()
            return data["embedding"]


# Singleton for dependency injection
_vector_service: VectorService | None = None


async def get_vector_service() -> VectorService:
    """Dependency injection for VectorService.

    Returns:
        Singleton VectorService instance
    """
    global _vector_service
    if _vector_service is None:
        _vector_service = VectorService()
    return _vector_service

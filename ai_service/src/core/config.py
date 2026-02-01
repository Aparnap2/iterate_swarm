"""Application configuration using pydantic-settings.

This module provides centralized configuration management for the IterateSwarm AI service.
All environment variables are validated at startup with fail-fast semantics.
"""

from pathlib import Path
from typing import Annotated, Any

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables.

    All secrets are stored as SecretStr and masked in logs.
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    # Application
    app_name: str = "iterate-swarm"
    app_host: str = "0.0.0.0"
    app_port: int = 8000
    debug: bool = False

    # Web App (for callbacks)
    web_app_url: str = Field(
        default="http://localhost:3000",
        description="URL of the web application for callbacks",
    )
    internal_api_key: SecretStr | None = Field(
        default=None,
        description="API key for internal API authentication",
    )

    # Qdrant (Vector Database)
    qdrant_url: str = Field(default="http://localhost:6333", description="Qdrant server URL")
    qdrant_api_key: SecretStr | None = Field(default=None, description="Qdrant API key if required")

    # Kafka (Event Bus) - using Aiven or local Kafka
    kafka_brokers: str = Field(default="localhost:9092", description="Kafka brokers comma-separated")
    kafka_topic_feedback: str = "feedback-received"
    kafka_ssl: bool = Field(default=False, description="Enable SSL for Kafka")
    kafka_username: str = Field(default="", description="Kafka username for SASL")
    kafka_password: SecretStr | None = Field(default=None, description="Kafka password for SASL")

    # OpenAI (LLM Provider)
    openai_api_key: SecretStr = Field(default=None, description="OpenAI API key (optional if using local LLM)")
    openai_model: str = Field(default="gpt-4o", description="OpenAI model to use")
    openai_embedding_model: str = Field(default="text-embedding-3-small", description="Embedding model")

    # Local LLM (Ollama) - for development
    local_llm_url: str = Field(default="http://localhost:11434/v1", description="Local LLM base URL")
    local_llm_model: str = Field(default="qwen2.5-coder:3b", description="Local LLM model name")

    # Langfuse (Observability)
    langfuse_public_key: str | None = Field(default=None, description="Langfuse public key")
    langfuse_secret_key: SecretStr | None = Field(default=None, description="Langfuse secret key")
    langfuse_host: str = Field(default="https://cloud.langfuse.com", description="Langfuse host")

    # Inngest (Workflow Orchestration)
    inngest_app_id: str = "iterate-swarm"
    inngest_api_key: SecretStr | None = Field(default=None, description="Inngest API key")
    inngest_api_url: str = "https://api.inngest.com"

    # GitHub Integration
    github_token: SecretStr = Field(default=None, description="GitHub PAT or app token")
    github_repo: str = Field(default="", description="GitHub repo in 'owner/repo' format")

    # Logging
    log_level: str = Field(default="INFO", description="Logging level")


settings = Settings()
"""Global settings instance. Validated at import time."""

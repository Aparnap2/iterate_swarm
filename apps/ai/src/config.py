"""Configuration management for AI Worker."""

import os
from pathlib import Path
from typing import Optional

import structlog
import yaml
from pydantic import BaseModel

logger = structlog.get_logger(__name__)


class TemporalConfig(BaseModel):
    """Temporal server configuration."""

    host: str = "localhost"
    port: int = 7233
    namespace: str = "default"
    task_queue: str = "AI_TASK_QUEUE"

    @property
    def address(self) -> str:
        return f"{self.host}:{self.port}"


class OllamaConfig(BaseModel):
    """Ollama LLM configuration (OpenAI-compatible)."""

    base_url: str = "http://localhost:11434/v1"
    api_key: str = "ollama"
    model: str = "qwen2.5-coder:3b"
    embedding_model: str = "nomic-embed-text"


class QdrantConfig(BaseModel):
    """Qdrant vector database configuration."""

    url: str = "http://localhost:6333"
    collection: str = "feedback_items"
    similarity_threshold: float = 0.85


class LoggingConfig(BaseModel):
    """Logging configuration."""

    level: str = "INFO"
    format: str = "json"


class AppConfig(BaseModel):
    """Application configuration."""

    name: str = "iterateswarm-ai"
    environment: str = "development"


class Config(BaseModel):
    """Main configuration container."""

    temporal: TemporalConfig = TemporalConfig()
    ollama: OllamaConfig = OllamaConfig()
    qdrant: QdrantConfig = QdrantConfig()
    logging: LoggingConfig = LoggingConfig()
    app: AppConfig = AppConfig()


def load_config(config_path: Optional[str] = None) -> Config:
    """Load configuration from YAML file.

    Args:
        config_path: Path to config.yaml. If None, looks in current directory.

    Returns:
        Config object with all settings.
    """
    if config_path is None:
        # Look for config.yaml in common locations
        search_paths = [
            Path.cwd() / "config.yaml",
            Path(__file__).parent.parent / "config.yaml",
            Path(__file__).parent.parent.parent / "config.yaml",
        ]
        for path in search_paths:
            if path.exists():
                config_path = str(path)
                break

    if config_path and Path(config_path).exists():
        logger.info("Loading configuration", path=config_path)
        with open(config_path) as f:
            config_dict = yaml.safe_load(f)
            return Config(**config_dict)

    logger.info("Using default configuration")
    return Config()


# Global config instance
_config: Optional[Config] = None


def get_config() -> Config:
    """Get the global configuration instance."""
    global _config
    if _config is None:
        _config = load_config()
    return _config

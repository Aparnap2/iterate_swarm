"""Pydantic schemas for webhook ingestion.

Defines strict validation models for Discord and Slack webhook payloads,
plus the unified FeedbackItem structure for Kafka.
"""

from datetime import datetime, timezone
from enum import Enum
from typing import Any
from uuid import UUID, uuid4

from pydantic import BaseModel, Field, field_validator


class FeedbackSource(str, Enum):
    """Enum for supported feedback sources."""

    DISCORD = "discord"
    SLACK = "slack"
    MANUAL = "manual"


# ========================
# Discord Schemas
# ========================


class DiscordEmbed(BaseModel):
    """Discord message embed structure."""

    title: str | None = None
    description: str | None = None
    type: str | None = Field(default="rich", alias="type")
    url: str | None = None
    timestamp: str | None = None
    color: int | None = None
    footer: dict[str, str] | None = None
    image: dict[str, str] | None = None
    thumbnail: dict[str, str] | None = None
    fields: list[dict[str, str]] | None = Field(default_factory=list, alias="fields")

    model_config = {"populate_by_name": True}


class DiscordAttachment(BaseModel):
    """Discord message attachment."""

    id: str
    filename: str | None = None
    content_type: str | None = Field(default=None, alias="contentType")
    size: int | None = None
    url: str | None = None
    proxy_url: str | None = Field(default=None, alias="proxyUrl")
    height: int | None = None
    width: int | None = None

    model_config = {"populate_by_name": True}


class DiscordAuthor(BaseModel):
    """Discord message author info."""

    id: str
    username: str
    avatar: str | None = None
    discriminator: str | None = None
    bot: bool | None = None

    model_config = {"populate_by_name": True}


class DiscordWebhookPayload(BaseModel):
    """Discord webhook payload structure.

    Supports both interaction callbacks and regular webhook messages.
    """

    id: str | None = None
    type: int | None = None
    guild_id: str | None = Field(default=None, alias="guildId")
    channel_id: str | None = Field(default=None, alias="channelId")
    author: DiscordAuthor | None = None
    content: str | None = None
    description: str | None = None
    timestamp: str | None = None
    edited_timestamp: str | None = Field(default=None, alias="editedTimestamp")
    tts: bool | None = None
    mention_everyone: bool | None = Field(default=None, alias="mentionEveryone")
    mentions: list[dict[str, Any]] | None = None
    attachments: list[DiscordAttachment] | None = None
    embeds: list[DiscordEmbed] | None = None
    reactions: list[dict[str, Any]] | None = None

    model_config = {"populate_by_name": True, "extra": "ignore"}

    @field_validator("content")
    @classmethod
    def validate_content(cls, v: str | None) -> str | None:
        """Ensure content is stripped and non-empty if present."""
        if v is not None:
            v = v.strip()
        return v if v else None

    def extract_feedback_text(self) -> str | None:
        """Extract the main feedback text from the payload.

        Returns the content or first embed description as the feedback.
        """
        if self.content and self.content.strip():
            return self.content.strip()

        if self.embeds and len(self.embeds) > 0:
            first_embed = self.embeds[0]
            if first_embed.description and first_embed.description.strip():
                return first_embed.description.strip()
            if first_embed.title and first_embed.title.strip():
                return first_embed.title.strip()

        return None


# ========================
# Slack Schemas
# ========================


class SlackAttachmentField(BaseModel):
    """Slack attachment field."""

    title: str | None = None
    value: str | None = None
    short: bool | None = None


class SlackAttachment(BaseModel):
    """Slack message attachment."""

    id: int | None = None
    fallback: str | None = None
    color: str | None = None
    pretext: str | None = Field(default=None, alias="pretext")
    author_name: str | None = Field(default=None, alias="authorName")
    author_link: str | None = Field(default=None, alias="authorLink")
    author_icon: str | None = Field(default=None, alias="authorIcon")
    title: str | None = None
    title_link: str | None = Field(default=None, alias="titleLink")
    text: str | None = None
    fields: list[SlackAttachmentField] | None = None
    footer: str | None = None
    footer_icon: str | None = Field(default=None, alias="footerIcon")
    ts: int | None = None

    model_config = {"populate_by_name": True}


class SlackBlockElement(BaseModel):
    """Slack block element."""

    type: str
    text: dict[str, Any] | None = None
    action_id: str | None = Field(default=None, alias="actionId")
    url: str | None = None
    value: str | None = None

    model_config = {"populate_by_name": True}


class SlackBlock(BaseModel):
    """Slack block structure."""

    id: str | None = None
    type: str
    text: dict[str, Any] | None = None
    elements: list[SlackBlockElement] | None = None
    accessory: dict[str, Any] | None = None

    model_config = {"populate_by_name": True}


class SlackWebhookPayload(BaseModel):
    """Slack webhook payload structure.

    Supports both block kit and legacy attachment formats.
    """

    # User info (for bot messages)
    user: str | None = None
    bot_id: str | None = Field(default=None, alias="botId")

    # Message content
    text: str | None = None
    blocks: list[SlackBlock] | None = None
    attachments: list[SlackAttachment] | None = None

    # Thread info
    thread_ts: str | None = Field(default=None, alias="threadTs")
    parent_user_id: str | None = Field(default=None, alias="parentUserId")

    # Channel info
    channel: str | None = None
    team: str | None = None

    # Metadata
    subtype: str | None = None
    ts: str | None = None

    model_config = {"populate_by_name": True, "extra": "ignore"}

    @field_validator("text")
    @classmethod
    def validate_text(cls, v: str | None) -> str | None:
        """Ensure text is stripped."""
        if v is not None:
            v = v.strip()
        return v if v else None

    def extract_feedback_text(self) -> str | None:
        """Extract the main feedback text from the payload.

        Priority:
        1. Block text elements
        2. Attachment text
        3. Main text field
        """
        # Check blocks first
        if self.blocks:
            for block in self.blocks:
                if block.text:
                    text_val = block.text.get("text", "")
                    if text_val.strip():
                        return text_val.strip()

        # Check attachments
        if self.attachments:
            for attachment in self.attachments:
                if attachment.text and attachment.text.strip():
                    return attachment.text.strip()

        # Fall back to main text
        if self.text and self.text.strip():
            return self.text.strip()

        return None


# ========================
# Unified Feedback Schema
# ========================


class FeedbackItem(BaseModel):
    """Unified feedback item for Kafka publishing.

    This is the canonical format we use internally after
    normalizing different webhook sources.
    """

    id: UUID = Field(default_factory=uuid4, description="Unique feedback ID")
    source: FeedbackSource = Field(..., description="Origin source")
    raw_content: str = Field(..., description="The actual feedback text")
    timestamp: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="When the feedback was received",
    )
    raw_payload: dict[str, Any] = Field(
        default_factory=dict,
        description="Original webhook payload for audit/debugging",
    )
    metadata: dict[str, Any] = Field(
        default_factory=dict,
        description="Additional context (channel, user, etc.)",
    )

    @classmethod
    def from_discord(
        cls,
        payload: DiscordWebhookPayload,
        feedback_id: UUID | None = None,
    ) -> "FeedbackItem":
        """Create a FeedbackItem from a Discord webhook payload."""
        content = payload.extract_feedback_text() or ""

        return cls(
            id=feedback_id or uuid4(),
            source=FeedbackSource.DISCORD,
            raw_content=content,
            raw_payload=payload.model_dump(exclude_none=True),
            metadata={
                "message_id": payload.id,
                "guild_id": payload.guild_id,
                "channel_id": payload.channel_id,
                "author": (
                    {
                        "id": payload.author.id,
                        "username": payload.author.username,
                    }
                    if payload.author
                    else None
                ),
                "has_embeds": len(payload.embeds or []) > 0,
                "attachment_count": len(payload.attachments or []),
            },
        )

    @classmethod
    def from_slack(
        cls,
        payload: SlackWebhookPayload,
        feedback_id: UUID | None = None,
    ) -> "FeedbackItem":
        """Create a FeedbackItem from a Slack webhook payload."""
        content = payload.extract_feedback_text() or ""

        return cls(
            id=feedback_id or uuid4(),
            source=FeedbackSource.SLACK,
            raw_content=content,
            raw_payload=payload.model_dump(exclude_none=True),
            metadata={
                "channel": payload.channel,
                "user_id": payload.user,
                "bot_id": payload.bot_id,
                "thread_ts": payload.thread_ts,
                "has_blocks": len(payload.blocks or []) > 0,
                "attachment_count": len(payload.attachments or []),
            },
        )

    def to_kafka_message(self) -> dict[str, Any]:
        """Convert to Kafka message format."""
        return {
            "id": str(self.id),
            "source": self.source.value,
            "raw_content": self.raw_content,
            "timestamp": self.timestamp.isoformat(),
            "metadata": self.metadata,
        }


class QueuedResponse(BaseModel):
    """Response returned when feedback is queued successfully."""

    status: str = Field(default="queued", description="Status of the request")
    id: UUID = Field(..., description="Unique ID assigned to this feedback")
    topic: str = Field(..., description="Kafka topic the message was sent to")
    timestamp: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="When the request was processed",
    )

    model_config = {
        "json_schema_extra": {
            "example": {
                "status": "queued",
                "id": "550e8400-e29b-41d4-a716-446655440000",
                "topic": "feedback.raw",
                "timestamp": "2024-01-15T10:30:00Z",
            }
        }
    }

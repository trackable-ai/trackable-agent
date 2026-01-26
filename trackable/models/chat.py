"""
OpenAI-compatible chat models.

These models follow the OpenAI Chat Completions API format:
https://platform.openai.com/docs/api-reference/chat
"""

import time
import uuid
from enum import Enum
from typing import Literal

from pydantic import BaseModel, Field


class MessageRole(str, Enum):
    """Role of a message in a conversation."""

    SYSTEM = "system"
    USER = "user"
    ASSISTANT = "assistant"


class ChatMessage(BaseModel):
    """A single message in a conversation."""

    role: MessageRole = Field(description="The role of the message author")
    content: str = Field(description="The content of the message")


class ChatCompletionRequest(BaseModel):
    """OpenAI-compatible chat completion request."""

    model: str = Field(
        default="gemini-2.5-flash",
        description="Model to use for completion (ignored, uses configured agent model)",
    )
    messages: list[ChatMessage] = Field(
        description="List of messages in the conversation",
        min_length=1,
    )
    stream: bool = Field(default=False, description="Whether to stream the response")
    temperature: float | None = Field(
        default=None,
        ge=0.0,
        le=2.0,
        description="Sampling temperature (0-2)",
    )
    max_tokens: int | None = Field(
        default=None,
        description="Maximum tokens to generate",
    )
    user: str | None = Field(
        default=None,
        description="User identifier for tracking",
    )


class ChatCompletionMessage(BaseModel):
    """Message in a chat completion response."""

    role: Literal["assistant"] = "assistant"
    content: str


class ChatCompletionChoice(BaseModel):
    """A single completion choice."""

    index: int = 0
    message: ChatCompletionMessage
    finish_reason: Literal["stop", "length", "content_filter"] | None = "stop"


class ChatCompletionUsage(BaseModel):
    """Token usage statistics."""

    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0


class ChatCompletionResponse(BaseModel):
    """OpenAI-compatible chat completion response."""

    id: str = Field(default_factory=lambda: f"chatcmpl-{uuid.uuid4().hex[:12]}")
    object: Literal["chat.completion"] = "chat.completion"
    created: int = Field(default_factory=lambda: int(time.time()))
    model: str = "gemini-2.5-flash"
    choices: list[ChatCompletionChoice]
    usage: ChatCompletionUsage = Field(default_factory=ChatCompletionUsage)


# Streaming response models


class ChatCompletionChunkDelta(BaseModel):
    """Delta content in a streaming chunk."""

    role: Literal["assistant"] | None = None
    content: str | None = None


class ChatCompletionChunkChoice(BaseModel):
    """A single choice in a streaming chunk."""

    index: int = 0
    delta: ChatCompletionChunkDelta
    finish_reason: Literal["stop", "length", "content_filter"] | None = None


class ChatCompletionChunk(BaseModel):
    """OpenAI-compatible streaming chunk."""

    id: str
    object: Literal["chat.completion.chunk"] = "chat.completion.chunk"
    created: int
    model: str = "gemini-2.5-flash"
    choices: list[ChatCompletionChunkChoice]

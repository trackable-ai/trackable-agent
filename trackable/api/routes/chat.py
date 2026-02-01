"""
OpenAI-compatible Chat Completions API.

Provides chat completion endpoints following the OpenAI API format:
https://platform.openai.com/docs/api-reference/chat
"""

import logging
import time
import uuid
from typing import AsyncIterator

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from google.adk.runners import InMemoryRunner
from google.genai.types import Content, Part

from trackable.agents.chatbot import chatbot_agent
from trackable.models.chat import (
    ChatCompletionChoice,
    ChatCompletionChunk,
    ChatCompletionChunkChoice,
    ChatCompletionChunkDelta,
    ChatCompletionMessage,
    ChatCompletionRequest,
    ChatCompletionResponse,
    ChatCompletionUsage,
    MessageRole,
)

logger = logging.getLogger(__name__)

router = APIRouter()

# Global runner instance
runner = InMemoryRunner(agent=chatbot_agent, app_name="trackable-chatbot")

# Session storage: user -> session_id
# In production, this should be persisted (Redis, database, etc.)
_user_sessions: dict[str, str] = {}


async def _get_or_create_session(user_id: str) -> str:
    """Get existing session or create a new one for the user."""
    if user_id in _user_sessions:
        return _user_sessions[user_id]

    session = await runner.session_service.create_session(
        app_name=runner.app_name,
        user_id=user_id,
    )
    _user_sessions[user_id] = session.id
    return session.id


def _build_prompt_from_messages(messages: list, user_id: str | None = None) -> str:
    """
    Build a prompt string from the messages list.

    For now, we concatenate messages. The ADK agent maintains its own
    conversation history via sessions, so we primarily use the last user message.
    Injects user_id context so the agent can pass it to database tools.
    """
    # Find the last user message
    prompt = ""
    for msg in reversed(messages):
        if msg.role == MessageRole.USER:
            prompt = msg.content
            break

    if not prompt:
        # Fallback: concatenate all messages
        parts = []
        for msg in messages:
            prefix = {"system": "System", "user": "User", "assistant": "Assistant"}.get(
                msg.role.value, "User"
            )
            parts.append(f"{prefix}: {msg.content}")
        prompt = "\n".join(parts)

    # Inject user_id context for tool calls
    if user_id:
        prompt = f"[Context: The current user_id is '{user_id}'. Use this for all tool calls that require user_id.]\n\n{prompt}"

    return prompt


async def _run_agent(user_id: str, prompt: str) -> str:
    """Run the agent and return the response text."""
    session_id = await _get_or_create_session(user_id)
    new_message = Content(parts=[Part(text=prompt)], role="user")

    response_text = ""
    async for event in runner.run_async(
        user_id=user_id,
        session_id=session_id,
        new_message=new_message,
    ):
        if event.content is None:
            continue
        if event.content.parts:
            for part in event.content.parts:
                if part.text:
                    response_text = part.text

    return response_text or "I apologize, but I couldn't generate a response."


async def _generate_stream(
    request_id: str,
    created: int,
    model: str,
    user_id: str,
    prompt: str,
) -> AsyncIterator[str]:
    """Generate OpenAI-compatible streaming response."""
    session_id = await _get_or_create_session(user_id)
    new_message = Content(parts=[Part(text=prompt)], role="user")

    logger.info(
        "User ID: %s, Session ID: %s, new msg: %s", user_id, session_id, new_message
    )

    # Send initial chunk with role
    initial_chunk = ChatCompletionChunk(
        id=request_id,
        created=created,
        model=model,
        choices=[
            ChatCompletionChunkChoice(
                delta=ChatCompletionChunkDelta(role="assistant"),
                finish_reason=None,
            )
        ],
    )
    yield f"data: {initial_chunk.model_dump_json()}\n\n"

    # Stream content
    response_text = ""
    async for event in runner.run_async(
        user_id=user_id,
        session_id=session_id,
        new_message=new_message,
    ):
        if event.content is None:
            continue
        if event.content.parts:
            for part in event.content.parts:
                if part.text and part.text != response_text:
                    delta = part.text[len(response_text) :]
                    response_text = part.text

                    chunk = ChatCompletionChunk(
                        id=request_id,
                        created=created,
                        model=model,
                        choices=[
                            ChatCompletionChunkChoice(
                                delta=ChatCompletionChunkDelta(content=delta),
                                finish_reason=None,
                            )
                        ],
                    )
                    yield f"data: {chunk.model_dump_json()}\n\n"

    # Send final chunk with finish_reason
    final_chunk = ChatCompletionChunk(
        id=request_id,
        created=created,
        model=model,
        choices=[
            ChatCompletionChunkChoice(
                delta=ChatCompletionChunkDelta(),
                finish_reason="stop",
            )
        ],
    )
    yield f"data: {final_chunk.model_dump_json()}\n\n"

    # Send [DONE] marker
    yield "data: [DONE]\n\n"


@router.post("/chat/completions")
async def chat_completions(request: ChatCompletionRequest):
    """
    OpenAI-compatible chat completions endpoint.

    Supports both streaming and non-streaming responses.

    Args:
        request: Chat completion request with messages

    Returns:
        ChatCompletionResponse or streaming response
    """
    try:
        user_id = request.user or "default_user"
        prompt = _build_prompt_from_messages(request.messages, user_id=user_id)
        request_id = f"chatcmpl-{uuid.uuid4().hex[:12]}"
        created = int(time.time())
        model = request.model

        if request.stream:
            return StreamingResponse(
                _generate_stream(request_id, created, model, user_id, prompt),
                media_type="text/event-stream",
                headers={
                    "Cache-Control": "no-cache",
                    "Connection": "keep-alive",
                    "X-Accel-Buffering": "no",
                },
            )

        # Non-streaming response
        response_text = await _run_agent(user_id, prompt)

        return ChatCompletionResponse(
            id=request_id,
            created=created,
            model=model,
            choices=[
                ChatCompletionChoice(
                    message=ChatCompletionMessage(content=response_text),
                    finish_reason="stop",
                )
            ],
            usage=ChatCompletionUsage(
                prompt_tokens=len(prompt.split()),
                completion_tokens=len(response_text.split()),
                total_tokens=len(prompt.split()) + len(response_text.split()),
            ),
        )

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Chat completion failed: {str(e)}",
        )


@router.delete("/chat/sessions")
async def clear_session(user: str = "default_user"):
    """
    Clear the chat session for a user, resetting conversation history.

    Args:
        user: User identifier (defaults to "default_user")

    Returns:
        Confirmation message with session status
    """
    if user in _user_sessions:
        del _user_sessions[user]
        return {"message": "Session cleared", "user": user}
    return {"message": "No session found", "user": user}

"""
OpenAI-compatible Chat Completions API.

Provides chat completion endpoints following the OpenAI API format:
https://platform.openai.com/docs/api-reference/chat

Extended with Trackable-specific fields (suggestions) for richer UI.
"""

import json
import logging
import time
import uuid
import base64
from typing import AsyncIterator

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from google.adk.runners import InMemoryRunner
from google.genai.types import Content, Part

from trackable.agents.chatbot import chatbot_agent
from trackable.models.chat import (
    ChatbotOutput,
    ChatCompletionChoice,
    ChatCompletionChunk,
    ChatCompletionChunkChoice,
    ChatCompletionChunkDelta,
    ChatCompletionMessage,
    ChatCompletionRequest,
    ChatCompletionResponse,
    ChatCompletionUsage,
    MessageRole,
    Suggestion,
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


def _extract_last_user_content(messages: list, user_id: str | None = None) -> Content | None:
    """
    Extract the content from the last user message.
    Handles both text-only (string) and multimodal (list) content.
    """
    for msg in reversed(messages):
        if msg.role == MessageRole.USER:
            parts = []
            
            # Inject user_id context if needed (handled in caller for now or appended to text)
            # For now, we just return the raw content as GenAI parts
            
            if isinstance(msg.content, str):
                text_content = msg.content
                if user_id:
                    text_content = f"[Context: The current user_id is '{user_id}'. Use this for all tool calls that require user_id.]\n\n{text_content}"
                parts.append(Part(text=text_content))
            elif isinstance(msg.content, list):
                # Process multimodal content
                has_text = False
                for item in msg.content:
                    if item.get("type") == "text":
                        text_val = item["text"]
                        if user_id and not has_text:
                            text_val = f"[Context: The current user_id is '{user_id}'. Use this for all tool calls that require user_id.]\n\n{text_val}"
                            has_text = True
                        parts.append(Part(text=text_val))
                    elif item.get("type") == "image_url":
                        # OpenAI format: {"type": "image_url", "image_url": {"url": "data:image/jpeg;base64,..."}}
                        image_url = item["image_url"]["url"]
                        if image_url.startswith("data:"):
                            # Parse data URL
                            try:
                                header, data = image_url.split(",", 1)
                                mime_type = header.split(":")[1].split(";")[0]
                                decoded_data = base64.b64decode(data)
                                parts.append(Part.from_bytes(data=decoded_data, mime_type=mime_type))
                            except Exception as e:
                                logger.error(f"Failed to parse data URL: {e}")
                        else:
                            # Handle public URLs if needed - skipping for now as frontend sends data URLs
                            pass 
                
                # If no text part was found but we have user_id, add a text part with context
                if user_id and not has_text:
                     parts.insert(0, Part(text=f"[Context: The current user_id is '{user_id}'. Use this for all tool calls that require user_id.]"))

            return Content(parts=parts, role="user")
    
    return None

def _parse_chatbot_output(response_text: str) -> ChatbotOutput:
    """Parse the agent's JSON response into a ChatbotOutput.

    With output_schema set, the agent returns JSON matching ChatbotOutput.
    Falls back gracefully if parsing fails.
    """
    try:
        data = json.loads(response_text)
        return ChatbotOutput(**data)
    except ValueError:
        logger.warning("Failed to parse agent output as ChatbotOutput, using raw text")
        return ChatbotOutput(content=response_text, suggestions=[])


async def _run_agent(user_id: str, new_message: Content) -> ChatbotOutput:
    """Run the agent and return the structured output."""
    session_id = await _get_or_create_session(user_id)
    # new_message is already a Content object

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

    if not response_text:
        return ChatbotOutput(
            content="I apologize, but I couldn't generate a response.",
            suggestions=[
                Suggestion(label="Show my orders", prompt="Show me all my orders"),
                Suggestion(
                    label="Check return windows",
                    prompt="Check my return windows",
                ),
                Suggestion(label="Help", prompt="What can you help me with?"),
            ],
        )

    return _parse_chatbot_output(response_text)


async def _generate_stream(
    request_id: str,
    created: int,
    model: str,
    user_id: str,
    new_message: Content,
) -> AsyncIterator[str]:
    """Generate streaming response with structured output.

    Since the agent returns JSON (due to output_schema), we collect the full
    response, parse it, then stream the markdown content and emit suggestions
    as a final metadata event.
    """
    session_id = await _get_or_create_session(user_id)
    
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

    # Collect the full response (agent returns JSON with output_schema)
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

    # Parse the structured output
    output = _parse_chatbot_output(response_text)

    # Send content as a single chunk
    if output.content:
        content_chunk = ChatCompletionChunk(
            id=request_id,
            created=created,
            model=model,
            choices=[
                ChatCompletionChunkChoice(
                    delta=ChatCompletionChunkDelta(content=output.content),
                    finish_reason=None,
                )
            ],
        )
        yield f"data: {content_chunk.model_dump_json()}\n\n"

    # Send final chunk with finish_reason and suggestions
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
        suggestions=output.suggestions or None,
    )
    yield f"data: {final_chunk.model_dump_json()}\n\n"

    # Send [DONE] marker
    yield "data: [DONE]\n\n"


@router.post(
    "/chat/completions",
    operation_id="createChatCompletion",
    response_model=ChatCompletionResponse,
)
async def chat_completions(request: ChatCompletionRequest):
    """
    OpenAI-compatible chat completions endpoint.

    Supports both streaming and non-streaming responses.
    Response includes `suggestions` — a list of next-step actions
    that the frontend renders as clickable buttons.

    Args:
        request: Chat completion request with messages

    Returns:
        ChatCompletionResponse or streaming response
    """
    try:
        user_id = request.user or "default_user"
        
        # Extract content from last user message (multimodal aware)
        new_message = _extract_last_user_content(request.messages, user_id=user_id)
        
        if not new_message:
             raise HTTPException(status_code=400, detail="No user message found")

        request_id = f"chatcmpl-{uuid.uuid4().hex[:12]}"
        created = int(time.time())
        model = request.model

        if request.stream:
            return StreamingResponse(
                _generate_stream(request_id, created, model, user_id, new_message),
                media_type="text/event-stream",
                headers={
                    "Cache-Control": "no-cache",
                    "Connection": "keep-alive",
                    "X-Accel-Buffering": "no",
                },
            )

        # Non-streaming response
        output = await _run_agent(user_id, new_message)

        return ChatCompletionResponse(
            id=request_id,
            created=created,
            model=model,
            choices=[
                ChatCompletionChoice(
                    message=ChatCompletionMessage(content=output.content),
                    finish_reason="stop",
                )
            ],
            usage=ChatCompletionUsage(
                prompt_tokens=0, # Calculation complex with images
                completion_tokens=len(output.content.split()),
                total_tokens=len(output.content.split()),
            ),
            suggestions=output.suggestions,
        )

    except Exception as e:
        logger.error(f"Chat completion failed: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Chat completion failed: {str(e)}",
        )


@router.delete("/chat/sessions", operation_id="clearChatSession")
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

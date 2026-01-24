"""
Chat API endpoint for the Trackable chatbot.

Provides conversational interface using the vanilla ADK agent.
"""

import json
from typing import AsyncIterator, Optional

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from google.adk.runners import InMemoryRunner
from google.genai.types import Content, Part
from pydantic import BaseModel, Field

from trackable.agents.chatbot import chatbot_agent

# Create router
router = APIRouter()

# Global runner instance
# InMemoryRunner is lightweight and can handle multiple sessions
runner = InMemoryRunner(agent=chatbot_agent, app_name="trackable-chatbot")


class ChatRequest(BaseModel):
    """Request model for chat endpoint"""

    message: str = Field(description="User message to send to the chatbot")
    session_id: Optional[str] = Field(
        default=None,
        description="Optional session ID for conversation continuity. If not provided, a new session will be created.",
    )
    user_id: str = Field(
        default="default_user",
        description="User identifier (will be linked to authenticated user in production)",
    )


class ChatResponse(BaseModel):
    """Response model for chat endpoint"""

    response: str = Field(description="Chatbot's response message")
    session_id: str = Field(description="Session ID for this conversation")
    user_id: str = Field(description="User identifier")


@router.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest) -> ChatResponse:
    """
    Send a message to the chatbot and get a response.

    This endpoint provides conversational AI capabilities using Google ADK and Gemini models.
    Sessions are managed automatically to maintain conversation context.

    Args:
        request: Chat request with user message and optional session info

    Returns:
        ChatResponse: Agent's response with session information

    Raises:
        HTTPException: If agent execution fails
    """
    try:
        # Get or create session
        if request.session_id:
            # Use existing session
            session_id = request.session_id
            # Verify session exists (runner maintains sessions in memory)
        else:
            # Create new session
            session = await runner.session_service.create_session(
                app_name=runner.app_name,
                user_id=request.user_id,
            )
            session_id = session.id

        # Create content from user message
        content = Content(parts=[Part(text=request.message)])

        # Run agent and collect response
        response_text = ""
        async for event in runner.run_async(
            user_id=request.user_id,
            session_id=session_id,
            new_message=content,
        ):
            # Extract text from agent response
            if event.content is None:
                continue

            if event.content.parts is not None and len(event.content.parts) > 0:
                part = event.content.parts[0]
                if part.text is not None:
                    response_text = part.text

        if not response_text:
            response_text = (
                "I apologize, but I couldn't generate a response. Please try again."
            )

        return ChatResponse(
            response=response_text,
            session_id=session_id,
            user_id=request.user_id,
        )

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Chat processing failed: {str(e)}",
        )


async def generate_chat_stream(
    user_id: str, session_id: str, message: str
) -> AsyncIterator[str]:
    """
    Generate streaming chat responses using Server-Sent Events (SSE) format.

    Args:
        user_id: User identifier
        session_id: Session ID for conversation context
        message: User message

    Yields:
        str: SSE-formatted events with chat response chunks
    """
    try:
        # Send initial metadata
        yield f"data: {json.dumps({'type': 'session', 'session_id': session_id, 'user_id': user_id})}\n\n"

        # Create content from user message
        content = Content(parts=[Part(text=message)])

        # Stream agent responses
        response_text = ""
        async for event in runner.run_async(
            user_id=user_id,
            session_id=session_id,
            new_message=content,
        ):
            # Extract text from agent response
            if event.content is None:
                continue

            if event.content.parts is not None and len(event.content.parts) > 0:
                part = event.content.parts[0]
                if part.text is not None:
                    # Send incremental updates (delta from previous)
                    new_text = part.text
                    if new_text != response_text:
                        delta = new_text[len(response_text) :]
                        response_text = new_text

                        # Send delta as SSE event
                        yield f"data: {json.dumps({'type': 'delta', 'content': delta})}\n\n"

        # Send completion event
        yield f"data: {json.dumps({'type': 'done', 'full_response': response_text})}\n\n"

    except Exception as e:
        # Send error event
        yield f"data: {json.dumps({'type': 'error', 'message': str(e)})}\n\n"


@router.post("/chat/stream")
async def chat_stream(request: ChatRequest):
    """
    Send a message to the chatbot and get a streaming response.

    This endpoint provides real-time streaming of the chatbot's response using
    Server-Sent Events (SSE). This allows the frontend to display responses
    as they are generated, providing better UX.

    Args:
        request: Chat request with user message and optional session info

    Returns:
        StreamingResponse: SSE stream with chat response chunks

    Event Types:
        - session: Initial event with session_id and user_id
        - delta: Incremental text chunks as they're generated
        - done: Final event with the complete response
        - error: Error event if processing fails
    """
    try:
        # Get or create session
        if request.session_id:
            session_id = request.session_id
        else:
            session = await runner.session_service.create_session(
                app_name=runner.app_name,
                user_id=request.user_id,
            )
            session_id = session.id

        # Return streaming response
        return StreamingResponse(
            generate_chat_stream(request.user_id, session_id, request.message),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no",  # Disable buffering in nginx
            },
        )

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Chat streaming failed: {str(e)}",
        )


@router.delete("/chat/session/{session_id}")
async def delete_session(session_id: str, user_id: str = "default_user"):
    """
    Delete a chat session.

    Args:
        session_id: Session ID to delete
        user_id: User identifier

    Returns:
        dict: Confirmation message
    """
    try:
        # InMemoryRunner sessions are automatically cleaned up
        # This is a placeholder for future persistent session management
        return {
            "message": f"Session {session_id} deleted",
            "session_id": session_id,
        }
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Session deletion failed: {str(e)}",
        )

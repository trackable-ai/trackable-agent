"""
Tests for the OpenAI-compatible chat completions API.
"""

import json

import dotenv
import pytest
from fastapi.testclient import TestClient

from trackable.api.main import app
from trackable.config import DEFAULT_MODEL

pytest_plugins = ("pytest_asyncio",)


@pytest.fixture(scope="session", autouse=True)
def load_env():
    dotenv.load_dotenv()


@pytest.fixture
def client() -> TestClient:
    """Create test client for FastAPI app"""
    return TestClient(app)


class TestHealthEndpoints:
    """Test health check and root endpoints"""

    def test_root_endpoint(self, client: TestClient):
        """Test root endpoint returns API information"""
        response = client.get("/")
        assert response.status_code == 200
        data = response.json()
        assert data["service"] == "Trackable Ingress API"
        assert data["version"] == "0.1.0"
        assert data["status"] == "operational"

    def test_health_endpoint(self, client: TestClient):
        """Test health check endpoint"""
        response = client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert data["service"] == "trackable-ingress"


@pytest.mark.manual
class TestChatCompletions:
    """Test OpenAI-compatible chat completions endpoint"""

    def test_chat_completions_basic(self, client: TestClient):
        """Test basic chat completion request"""
        response = client.post(
            "/api/v1/chat/completions",
            json={
                "model": DEFAULT_MODEL,
                "messages": [{"role": "user", "content": "Hello! What is Trackable?"}],
                "user": "test_user",
            },
        )

        assert response.status_code == 200
        data = response.json()

        # Verify OpenAI response structure
        assert "id" in data
        assert data["id"].startswith("chatcmpl-")
        assert data["object"] == "chat.completion"
        assert "created" in data
        assert "model" in data
        assert "choices" in data
        assert "usage" in data

        # Verify choices
        assert len(data["choices"]) == 1
        choice = data["choices"][0]
        assert choice["index"] == 0
        assert "message" in choice
        assert choice["message"]["role"] == "assistant"
        assert len(choice["message"]["content"]) > 0
        assert choice["finish_reason"] == "stop"

        # Verify usage
        assert "prompt_tokens" in data["usage"]
        assert "completion_tokens" in data["usage"]
        assert "total_tokens" in data["usage"]

    def test_chat_completions_with_system_message(self, client: TestClient):
        """Test chat completion with system message"""
        response = client.post(
            "/api/v1/chat/completions",
            json={
                "model": DEFAULT_MODEL,
                "messages": [
                    {
                        "role": "system",
                        "content": "You are a helpful shopping assistant.",
                    },
                    {"role": "user", "content": "Hi there!"},
                ],
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert data["choices"][0]["message"]["role"] == "assistant"
        assert len(data["choices"][0]["message"]["content"]) > 0

    def test_chat_completions_conversation(self, client: TestClient):
        """Test multi-turn conversation"""
        # First turn
        response1 = client.post(
            "/api/v1/chat/completions",
            json={
                "model": DEFAULT_MODEL,
                "messages": [{"role": "user", "content": "My name is Alice."}],
                "user": "test_user_conv",
            },
        )
        assert response1.status_code == 200

        # Second turn - agent should remember the name via session
        response2 = client.post(
            "/api/v1/chat/completions",
            json={
                "model": DEFAULT_MODEL,
                "messages": [{"role": "user", "content": "What is my name?"}],
                "user": "test_user_conv",
            },
        )
        assert response2.status_code == 200
        data2 = response2.json()
        assert len(data2["choices"][0]["message"]["content"]) > 0


@pytest.mark.manual
class TestChatCompletionsStreaming:
    """Test streaming chat completions"""

    def test_chat_completions_stream(self, client: TestClient):
        """Test streaming chat completion"""
        with client.stream(
            "POST",
            "/api/v1/chat/completions",
            json={
                "model": DEFAULT_MODEL,
                "messages": [{"role": "user", "content": "Say hello in one word."}],
                "stream": True,
                "user": "test_user",
            },
        ) as response:
            assert response.status_code == 200
            assert "text/event-stream" in response.headers["content-type"]

            chunks = []
            for line in response.iter_lines():
                if line.startswith("data: "):
                    data_str = line[6:]
                    if data_str == "[DONE]":
                        break
                    chunks.append(json.loads(data_str))

            # Verify we received chunks
            assert len(chunks) > 0

            # First chunk should have role
            first_chunk = chunks[0]
            assert first_chunk["object"] == "chat.completion.chunk"
            assert "id" in first_chunk
            assert first_chunk["id"].startswith("chatcmpl-")
            assert first_chunk["choices"][0]["delta"].get("role") == "assistant"

            # Last chunk should have finish_reason
            last_chunk = chunks[-1]
            assert last_chunk["choices"][0]["finish_reason"] == "stop"

            # Middle chunks should have content
            content_chunks = [
                c for c in chunks if c["choices"][0]["delta"].get("content")
            ]
            assert len(content_chunks) > 0

    def test_chat_completions_stream_collects_full_response(self, client: TestClient):
        """Test that streaming chunks form a complete response"""
        with client.stream(
            "POST",
            "/api/v1/chat/completions",
            json={
                "model": DEFAULT_MODEL,
                "messages": [{"role": "user", "content": "Count from 1 to 3."}],
                "stream": True,
            },
        ) as response:
            full_content = ""
            for line in response.iter_lines():
                if line.startswith("data: "):
                    data_str = line[6:]
                    if data_str == "[DONE]":
                        break
                    chunk = json.loads(data_str)
                    delta_content = chunk["choices"][0]["delta"].get("content", "")
                    full_content += delta_content

            # Should have collected some content
            assert len(full_content) > 0


class TestUserIdInjection:
    """Test that user_id is injected into prompts for tool access."""

    def test_prompt_includes_user_id(self):
        from trackable.api.routes.chat import _build_prompt_from_messages
        from trackable.models.chat import ChatMessage, MessageRole

        messages = [ChatMessage(role=MessageRole.USER, content="Show my orders")]
        result = _build_prompt_from_messages(messages, user_id="usr-abc-123")

        assert "usr-abc-123" in result

    def test_prompt_without_user_id(self):
        from trackable.api.routes.chat import _build_prompt_from_messages
        from trackable.models.chat import ChatMessage, MessageRole

        messages = [ChatMessage(role=MessageRole.USER, content="Hello")]
        result = _build_prompt_from_messages(messages, user_id=None)

        # Should still work, just without user_id context
        assert "Hello" in result


class TestChatCompletionsValidation:
    """Test request validation"""

    def test_empty_messages_fails(self, client: TestClient):
        """Test that empty messages list fails"""
        response = client.post(
            "/api/v1/chat/completions",
            json={
                "model": DEFAULT_MODEL,
                "messages": [],
            },
        )
        # FastAPI should return 422 for validation error
        assert response.status_code == 422

    def test_missing_messages_fails(self, client: TestClient):
        """Test that missing messages field fails"""
        response = client.post(
            "/api/v1/chat/completions",
            json={
                "model": DEFAULT_MODEL,
            },
        )
        assert response.status_code == 422

    def test_invalid_role_fails(self, client: TestClient):
        """Test that invalid role fails"""
        response = client.post(
            "/api/v1/chat/completions",
            json={
                "model": DEFAULT_MODEL,
                "messages": [{"role": "invalid_role", "content": "Hello"}],
            },
        )
        assert response.status_code == 422

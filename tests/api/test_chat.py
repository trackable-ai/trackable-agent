"""
Tests for the chat API endpoints.
"""

import json

import dotenv
import pytest
from fastapi.testclient import TestClient

from trackable.api.main import app

pytest_plugins = ("pytest_asyncio",)
pytestmark = pytest.mark.manual


@pytest.fixture(scope="session", autouse=True)
def load_env():
    dotenv.load_dotenv()


@pytest.fixture
def client():
    """Create test client for FastAPI app"""
    return TestClient(app)


class TestHealthEndpoints:
    """Test health check and root endpoints"""

    def test_root_endpoint(self, client):
        """Test root endpoint returns API information"""
        response = client.get("/")
        assert response.status_code == 200
        data = response.json()
        assert data["service"] == "Trackable Ingress API"
        assert data["version"] == "0.1.0"
        assert data["status"] == "operational"

    def test_health_endpoint(self, client):
        """Test health check endpoint"""
        response = client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert data["service"] == "trackable-ingress"


class TestChatEndpoint:
    """Test standard chat endpoint"""

    def test_chat_basic(self, client):
        """Test basic chat interaction"""
        response = client.post(
            "/api/chat",
            json={
                "message": "Hello! What is Trackable?",
                "user_id": "test_user",
            },
        )

        assert response.status_code == 200
        data = response.json()

        # Verify response structure
        assert "response" in data
        assert "session_id" in data
        assert "user_id" in data
        assert data["user_id"] == "test_user"

        # Verify response is not empty
        assert len(data["response"]) > 0
        assert isinstance(data["session_id"], str)

    def test_chat_with_session_continuity(self, client):
        """Test chat with session continuity"""
        # First message
        response1 = client.post(
            "/api/chat",
            json={
                "message": "My name is Alice",
                "user_id": "test_user",
            },
        )

        assert response1.status_code == 200
        data1 = response1.json()
        session_id = data1["session_id"]

        # Second message using same session
        response2 = client.post(
            "/api/chat",
            json={
                "message": "What is my name?",
                "user_id": "test_user",
                "session_id": session_id,
            },
        )

        assert response2.status_code == 200
        data2 = response2.json()

        # Verify same session
        assert data2["session_id"] == session_id

        # Response should reference the name (though this depends on agent memory)
        # This is a basic check that the session continued
        assert len(data2["response"]) > 0


class TestChatStreamEndpoint:
    """Test streaming chat endpoint"""

    def test_chat_stream_basic(self, client):
        """Test basic streaming chat interaction"""
        with client.stream(
            "POST",
            "/api/chat/stream",
            json={
                "message": "Hi! Tell me about Trackable in one sentence.",
                "user_id": "test_user",
            },
        ) as response:
            assert response.status_code == 200
            assert "text/event-stream" in response.headers["content-type"]

            # Collect all events
            events = []
            for line in response.iter_lines():
                if line.startswith("data: "):
                    data = json.loads(line[6:])
                    events.append(data)

            # Verify we received events
            assert len(events) > 0

            # First event should be session info
            assert events[0]["type"] == "session"
            assert "session_id" in events[0]
            assert events[0]["user_id"] == "test_user"

            # Last event should be done
            assert events[-1]["type"] == "done"
            assert "full_response" in events[-1]
            assert len(events[-1]["full_response"]) > 0

            # Should have at least one delta event
            delta_events = [e for e in events if e["type"] == "delta"]
            assert len(delta_events) > 0

    def test_chat_stream_with_existing_session(self, client):
        """Test streaming with existing session"""
        # Create session with first request
        with client.stream(
            "POST",
            "/api/chat/stream",
            json={
                "message": "Hello",
                "user_id": "test_user",
            },
        ) as response:
            # Get session from first event
            first_line = next(response.iter_lines())
            session_data = json.loads(first_line[6:])
            session_id = session_data["session_id"]

        # Use session in second request
        with client.stream(
            "POST",
            "/api/chat/stream",
            json={
                "message": "Follow up message",
                "user_id": "test_user",
                "session_id": session_id,
            },
        ) as response:
            first_line = next(response.iter_lines())
            session_data = json.loads(first_line[6:])

            # Verify same session
            assert session_data["session_id"] == session_id


class TestSessionManagement:
    """Test session management endpoints"""

    def test_delete_session(self, client):
        """Test session deletion"""
        # Create a session first
        response = client.post(
            "/api/chat",
            json={
                "message": "Hello",
                "user_id": "test_user",
            },
        )
        session_id = response.json()["session_id"]

        # Delete the session
        delete_response = client.delete(
            f"/api/chat/session/{session_id}?user_id=test_user"
        )

        assert delete_response.status_code == 200
        data = delete_response.json()
        assert data["session_id"] == session_id
        assert "deleted" in data["message"].lower()

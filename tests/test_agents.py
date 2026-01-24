import textwrap

import dotenv
import pytest
from google.adk.runners import InMemoryRunner
from google.genai.types import Content, Part

from trackable.agents import chatbot_agent

pytest_plugins = ("pytest_asyncio",)
pytestmark = pytest.mark.manual


@pytest.fixture(scope="session", autouse=True)
def load_env():
    dotenv.load_dotenv()


@pytest.mark.asyncio
async def test_happy_path():
    """Runs the agent on a simple input and expects a normal response."""
    user_input = textwrap.dedent("""
        Double check this:
        Question: who are you
        Answer: Hello! I am an AI Research Assistant.
    """).strip()

    app_name = "trackable"

    runner = InMemoryRunner(agent=chatbot_agent, app_name=app_name)
    session = await runner.session_service.create_session(
        app_name=runner.app_name, user_id="test_user"
    )
    content: Content = Content(parts=[Part(text=user_input)])
    response = ""
    async for event in runner.run_async(
        user_id=session.user_id,
        session_id=session.id,
        new_message=content,
    ):
        if event.content is None:
            continue

        print(event)
        if event.content.parts is not None and event.content.parts[0].text is not None:
            response = event.content.parts[0].text
    assert len(response) > 0

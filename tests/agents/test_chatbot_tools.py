"""Tests that chatbot agent has the correct tools wired up."""


def test_chatbot_has_order_tools():
    """Verify chatbot agent includes order query tools."""
    from trackable.agents.chatbot import chatbot_agent

    tool_names = set()
    for tool in chatbot_agent.tools:
        if hasattr(tool, "name"):
            tool_names.add(tool.name)
        elif callable(tool):
            tool_names.add(tool.__name__)

    assert "get_user_orders" in tool_names
    assert "get_order_details" in tool_names
    assert "check_return_windows" in tool_names
    assert "get_merchant_info" in tool_names
    assert "search_order_by_number" in tool_names
    assert "search_orders" in tool_names


def test_chatbot_retains_google_search():
    """Verify chatbot still has google_search tool."""
    from trackable.agents.chatbot import chatbot_agent

    tool_names = set()
    for tool in chatbot_agent.tools:
        if hasattr(tool, "name"):
            tool_names.add(tool.name)
        elif callable(tool):
            tool_names.add(tool.__name__)

    assert "google_search" in tool_names

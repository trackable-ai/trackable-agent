"""Tests for chatbot agent tool registration."""

from trackable.agents.chatbot import chatbot_agent


def test_chatbot_has_order_tools():
    """Verify chatbot agent includes order query tools."""
    tool_names = set()
    for tool in chatbot_agent.tools:
        if hasattr(tool, "name"):
            tool_names.add(tool.name)
        elif callable(tool):
            tool_names.add(tool.__name__)

    assert "get_user_orders" in tool_names
    assert "get_order_details" in tool_names
    assert "search_order_by_number" in tool_names
    assert "search_orders" in tool_names
    assert "check_return_windows" in tool_names


def test_chatbot_has_merchant_tools():
    """Verify chatbot agent includes merchant query tools."""
    tool_names = set()
    for tool in chatbot_agent.tools:
        if hasattr(tool, "name"):
            tool_names.add(tool.name)
        elif callable(tool):
            tool_names.add(tool.__name__)

    assert "get_merchant_info" in tool_names


def test_chatbot_has_policy_tools():
    """Verify chatbot agent includes policy query tools."""
    tool_names = set()
    for tool in chatbot_agent.tools:
        if hasattr(tool, "name"):
            tool_names.add(tool.name)
        elif callable(tool):
            tool_names.add(tool.__name__)

    assert "get_return_policy" in tool_names
    assert "get_exchange_policy" in tool_names
    assert "get_policy_for_order" in tool_names


def test_chatbot_tool_count():
    """Verify expected number of tools are registered."""
    # Should have:
    # - 5 order tools (get_user_orders, get_order_details, search_order_by_number,
    #                  search_orders, check_return_windows)
    # - 1 merchant tool (get_merchant_info)
    # - 3 policy tools (get_return_policy, get_exchange_policy, get_policy_for_order)
    # Total: 9 tools
    assert len(chatbot_agent.tools) == 9

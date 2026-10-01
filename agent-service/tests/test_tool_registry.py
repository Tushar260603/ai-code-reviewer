"""
test_tool_registry.py
=====================
Tests for the central tool registry.
"""

import pytest
from langchain_core.tools import BaseTool
from langgraph.prebuilt import ToolNode

from app.tools.tool_registry import TOOLS, get_tool_names, get_tools


class TestToolRegistry:
    def test_get_tools_returns_list(self):
        tools = get_tools()
        assert isinstance(tools, list)
        assert len(tools) == 4  # read_file, search_codebase, run_tests, git_blame

    def test_all_tools_are_basetool_instances(self):
        for tool in get_tools():
            assert isinstance(tool, BaseTool), f"{tool} is not a BaseTool"

    def test_all_tools_have_name(self):
        for tool in get_tools():
            assert tool.name, f"Tool {tool} has no name"

    def test_all_tools_have_description(self):
        for tool in get_tools():
            assert tool.description, f"Tool {tool.name!r} has no description"

    def test_expected_tool_names_present(self):
        names = get_tool_names()
        for expected in ["read_file", "search_codebase", "run_tests", "git_blame"]:
            assert expected in names, f"Missing tool: {expected!r}"

    def test_get_tools_returns_new_list_each_time(self):
        """Mutating the returned list should not affect the registry."""
        a = get_tools()
        b = get_tools()
        a.clear()
        assert len(b) == 4

    def test_tools_compatible_with_tool_node(self):
        """ToolNode must accept the tool list without raising."""
        tn = ToolNode(get_tools())
        assert tn is not None

    def test_tools_list_matches_constants(self):
        assert get_tools() == TOOLS

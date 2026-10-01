"""
tool_registry.py
================
Central registry of all LangChain tools available to the code-review agents.

Usage
-----
Retrieve all tools::

    from app.tools.tool_registry import get_tools

    tools = get_tools()

Use with LangGraph's ToolNode::

    from langgraph.prebuilt import ToolNode
    tool_node = ToolNode(get_tools())

Use with a LangChain LLM::

    llm_with_tools = llm.bind_tools(get_tools())

Use with LangGraph's create_react_agent::

    from langgraph.prebuilt import create_react_agent
    agent = create_react_agent(llm, get_tools())

Individual tools are importable directly::

    from app.tools.tool_registry import read_file, search_codebase, run_tests, git_blame
"""

from __future__ import annotations

from langchain_core.tools import BaseTool

from .git_blame import git_blame
from .read_file import read_file
from .run_tests import run_tests
from .search_codebase import search_codebase

# ── Master list of all available tools ──────────────────────────────────────

TOOLS: list[BaseTool] = [
    read_file,
    search_codebase,
    run_tests,
    git_blame,
]


def get_tools() -> list[BaseTool]:
    """
    Return the list of all registered LangChain tools.

    Compatible with:

    * ``langgraph.prebuilt.ToolNode(get_tools())``
    * ``llm.bind_tools(get_tools())``
    * ``langgraph.prebuilt.create_react_agent(llm, get_tools())``

    Returns:
        A list of :class:`~langchain_core.tools.BaseTool` instances.
    """
    return list(TOOLS)


def get_tool_names() -> list[str]:
    """Return the names of all registered tools."""
    return [t.name for t in TOOLS]

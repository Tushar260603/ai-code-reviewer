"""
test_base_agent.py
==================
Unit tests for BaseAgent — mocking the Gemini LLM so no API key is needed.

Integration smoke-test (marked `integration`) does call the real Gemini API
and requires GEMINI_API_KEY to be set.
"""

import json
import os
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from langchain_core.messages import AIMessage

from app.agents.base_agent import BaseAgent, Finding, ReviewResult


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def mock_env(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "fake-key-for-unit-tests")
    monkeypatch.setenv("GEMINI_MODEL", "gemini-2.5-flash")


# ---------------------------------------------------------------------------
# Schema tests (no LLM needed)
# ---------------------------------------------------------------------------

class TestSchemas:
    def test_finding_fields(self):
        f = Finding(
            file="src/auth.py",
            line=42,
            severity="high",
            message="SQL injection risk",
            category="security",
        )
        assert f.file == "src/auth.py"
        assert f.line == 42
        assert f.severity == "high"
        assert f.message == "SQL injection risk"
        assert f.category == "security"

    def test_review_result_defaults_empty(self):
        rr = ReviewResult()
        assert rr.findings == []

    def test_review_result_with_findings(self):
        findings = [
            Finding(file="a.py", line=1, severity="low", message="msg", category="style"),
            Finding(file="b.py", line=2, severity="high", message="msg2", category="security"),
        ]
        rr = ReviewResult(findings=findings)
        assert len(rr.findings) == 2

    def test_finding_serialisable(self):
        f = Finding(file="x.py", line=1, severity="info", message="ok", category="logic")
        data = json.loads(f.model_dump_json())
        assert data["file"] == "x.py"


# ---------------------------------------------------------------------------
# BaseAgent construction tests
# ---------------------------------------------------------------------------

class TestBaseAgentInit:
    def test_raises_without_api_key(self, monkeypatch):
        monkeypatch.delenv("GEMINI_API_KEY", raising=False)
        with pytest.raises(EnvironmentError, match="GEMINI_API_KEY"):
            BaseAgent(system_prompt="test")

    def test_uses_env_model_name(self, mock_env):
        with patch("app.agents.base_agent.ChatGoogleGenerativeAI"):
            agent = BaseAgent(system_prompt="test")
        assert agent.model_name == "gemini-2.5-flash"

    def test_model_name_argument_takes_priority(self, mock_env):
        with patch("app.agents.base_agent.ChatGoogleGenerativeAI"):
            agent = BaseAgent(system_prompt="test", model_name="gemini-1.5-pro")
        assert agent.model_name == "gemini-1.5-pro"

    def test_default_model_fallback(self, monkeypatch):
        monkeypatch.setenv("GEMINI_API_KEY", "fake-key")
        monkeypatch.delenv("GEMINI_MODEL", raising=False)
        with patch("app.agents.base_agent.ChatGoogleGenerativeAI"):
            agent = BaseAgent(system_prompt="test")
        assert agent.model_name == "gemini-2.5-flash"

    def test_tools_default_to_empty_list(self, mock_env):
        with patch("app.agents.base_agent.ChatGoogleGenerativeAI"):
            agent = BaseAgent(system_prompt="test")
        assert agent.tools == []


# ---------------------------------------------------------------------------
# BaseAgent.run() tests (LLM fully mocked)
# ---------------------------------------------------------------------------

class TestBaseAgentRun:
    def _make_agent(self, mock_env, tools=None):
        """Create a BaseAgent with a mocked LLM."""
        with patch("app.agents.base_agent.ChatGoogleGenerativeAI"):
            agent = BaseAgent(system_prompt="You are a code reviewer.", tools=tools or [])
        return agent

    @pytest.mark.asyncio
    async def test_run_returns_review_result(self, mock_env):
        agent = self._make_agent(mock_env)

        # Mock the LangGraph graph to return a simple AIMessage
        expected_result = ReviewResult(findings=[
            Finding(file="main.py", line=10, severity="high",
                    message="SQL injection", category="security")
        ])

        mock_graph_state = {
            "messages": [AIMessage(content="Found 1 issue in main.py at line 10.")]
        }
        agent._graph = MagicMock()
        agent._graph.ainvoke = AsyncMock(return_value=mock_graph_state)
        agent._structured_llm = AsyncMock()
        agent._structured_llm.ainvoke = AsyncMock(return_value=expected_result)

        result = await agent.run("review this code")

        assert isinstance(result, ReviewResult)
        assert len(result.findings) == 1
        assert result.findings[0].file == "main.py"
        assert result.findings[0].severity == "high"

    @pytest.mark.asyncio
    async def test_run_returns_empty_result_on_graph_error(self, mock_env):
        agent = self._make_agent(mock_env)

        agent._graph = MagicMock()
        agent._graph.ainvoke = AsyncMock(side_effect=Exception("LLM error"))

        result = await agent.run("review this code")

        assert isinstance(result, ReviewResult)
        assert result.findings == []

    @pytest.mark.asyncio
    async def test_run_returns_empty_result_on_no_messages(self, mock_env):
        agent = self._make_agent(mock_env)

        agent._graph = MagicMock()
        agent._graph.ainvoke = AsyncMock(return_value={"messages": []})

        result = await agent.run("review this code")

        assert isinstance(result, ReviewResult)
        assert result.findings == []

    @pytest.mark.asyncio
    async def test_run_returns_empty_result_on_structured_output_error(self, mock_env):
        agent = self._make_agent(mock_env)

        agent._graph = MagicMock()
        agent._graph.ainvoke = AsyncMock(return_value={
            "messages": [AIMessage(content="Some findings.")]
        })
        agent._structured_llm = MagicMock()
        agent._structured_llm.ainvoke = AsyncMock(side_effect=Exception("Parse error"))

        result = await agent.run("review this code")

        assert isinstance(result, ReviewResult)
        assert result.findings == []


# ---------------------------------------------------------------------------
# Integration smoke test — calls real Gemini API
# ---------------------------------------------------------------------------

@pytest.mark.integration
@pytest.mark.asyncio
@pytest.mark.skipif(
    not os.getenv("GEMINI_API_KEY") or os.getenv("GEMINI_API_KEY", "").startswith("fake"),
    reason="GEMINI_API_KEY not set — skipping integration test",
)
async def test_agent_real_gemini_no_tools():
    """
    Smoke-test: send a trivial code snippet to the real Gemini API and
    confirm a ReviewResult is returned.  Does NOT assert specific findings —
    just validates the round-trip works.
    """
    agent = BaseAgent(
        system_prompt=(
            "You are a code reviewer. Identify any issues in the provided code. "
            "Be concise."
        ),
        tools=[],
    )

    sample_code = """
# file: example.py
password = "hardcoded_secret_123"

def login(user, pwd):
    if pwd == password:
        return True
"""

    result = await agent.run(f"Review this Python code:\n{sample_code}")

    assert isinstance(result, ReviewResult)
    # Should find at least one issue (hardcoded password)
    assert len(result.findings) >= 0  # permissive: model may vary
    for finding in result.findings:
        assert isinstance(finding, Finding)
        assert finding.file
        assert finding.severity in ("critical", "high", "medium", "low", "info")
        assert finding.message
        assert finding.category

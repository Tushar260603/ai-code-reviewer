"""
test_agents.py
==============
Unit tests for SecurityAgent, StyleAgent, LogicAgent, and ReviewSupervisor.
"""

from unittest.mock import AsyncMock, patch
import pytest

from app.agents import (
    Finding,
    LogicAgent,
    ReviewResult,
    ReviewSupervisor,
    SecurityAgent,
    StyleAgent,
    compute_verdict,
    deduplicate_findings,
)


@pytest.fixture
def mock_env(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "fake-key-for-unit-tests")
    monkeypatch.setenv("GEMINI_MODEL", "gemini-2.5-flash")


# ---------------------------------------------------------------------------
# Individual Agent Initialization & Tools Tests
# ---------------------------------------------------------------------------


class TestAgentsInit:
    def test_security_agent_tools(self, mock_env):
        with patch("app.agents.base_agent.ChatGoogleGenerativeAI"):
            agent = SecurityAgent()
        tool_names = [t.name for t in agent.tools]
        assert "read_file" in tool_names
        assert "search_codebase" in tool_names
        assert "git_blame" in tool_names
        assert "run_tests" not in tool_names
        assert "SQL Injection" in agent.system_prompt

    def test_style_agent_tools(self, mock_env):
        with patch("app.agents.base_agent.ChatGoogleGenerativeAI"):
            agent = StyleAgent()
        tool_names = [t.name for t in agent.tools]
        assert "read_file" in tool_names
        assert "search_codebase" in tool_names
        assert "git_blame" not in tool_names
        assert "run_tests" not in tool_names
        assert "Naming Conventions" in agent.system_prompt

    def test_logic_agent_tools(self, mock_env):
        with patch("app.agents.base_agent.ChatGoogleGenerativeAI"):
            agent = LogicAgent()
        tool_names = [t.name for t in agent.tools]
        assert "read_file" in tool_names
        assert "search_codebase" in tool_names
        assert "run_tests" in tool_names
        assert "git_blame" not in tool_names
        assert "Boundary Conditions" in agent.system_prompt


# ---------------------------------------------------------------------------
# Deduplication Tests
# ---------------------------------------------------------------------------


class TestDeduplication:
    def test_deduplicates_same_file_and_line_injection(self):
        f1 = Finding(
            file="src/db/user.py",
            line=25,
            severity="high",
            message="SQL injection vulnerability: user input directly interpolated in SQL query.",
            category="security",
        )
        f2 = Finding(
            file="src/db/user.py",
            line=25,
            severity="medium",
            message="User input is directly used in SQL query string concatenation without parametrization.",
            category="logic",
        )

        deduped = deduplicate_findings([f1, f2])
        assert len(deduped) == 1
        # Higher severity (high > medium) should be preserved
        assert deduped[0].severity == "high"
        assert deduped[0].file == "src/db/user.py"

    def test_preserves_different_files(self):
        f1 = Finding(
            file="src/db/user.py",
            line=25,
            severity="high",
            message="SQL injection vulnerability.",
            category="security",
        )
        f2 = Finding(
            file="src/db/order.py",
            line=25,
            severity="high",
            message="SQL injection vulnerability.",
            category="security",
        )
        deduped = deduplicate_findings([f1, f2])
        assert len(deduped) == 2

    def test_preserves_different_lines(self):
        f1 = Finding(
            file="src/db/user.py",
            line=10,
            severity="high",
            message="SQL injection vulnerability.",
            category="security",
        )
        f2 = Finding(
            file="src/db/user.py",
            line=90,
            severity="high",
            message="SQL injection vulnerability.",
            category="security",
        )
        deduped = deduplicate_findings([f1, f2])
        assert len(deduped) == 2

    def test_empty_findings(self):
        assert deduplicate_findings([]) == []


# ---------------------------------------------------------------------------
# PR Verdict Tests
# ---------------------------------------------------------------------------


class TestVerdictComputation:
    def test_verdict_request_changes_critical(self):
        findings = [
            Finding(file="a.py", line=1, severity="critical", message="RCE bug", category="security")
        ]
        assert compute_verdict(findings) == "request_changes"

    def test_verdict_request_changes_high(self):
        findings = [
            Finding(file="a.py", line=1, severity="high", message="Auth bypass", category="security"),
            Finding(file="b.py", line=2, severity="low", message="Variable naming", category="style"),
        ]
        assert compute_verdict(findings) == "request_changes"

    def test_verdict_comment_medium(self):
        findings = [
            Finding(file="a.py", line=1, severity="medium", message="Missing error check", category="logic"),
            Finding(file="b.py", line=2, severity="low", message="Docstring missing", category="style"),
            Finding(file="c.py", line=3, severity="info", message="Notice", category="style"),
        ]
        assert compute_verdict(findings) == "comment"

    def test_verdict_approve_low_info_only(self):
        findings = [
            Finding(file="b.py", line=2, severity="low", message="Docstring missing", category="style"),
            Finding(file="c.py", line=3, severity="info", message="Notice", category="style"),
        ]
        assert compute_verdict(findings) == "approve"

    def test_verdict_approve_empty(self):
        assert compute_verdict([]) == "approve"


# ---------------------------------------------------------------------------
# ReviewSupervisor Tests
# ---------------------------------------------------------------------------


class TestReviewSupervisor:
    @pytest.mark.asyncio
    async def test_supervisor_review_concurrent_success(self, mock_env):
        sec_agent = SecurityAgent()
        style_agent = StyleAgent()
        logic_agent = LogicAgent()

        sec_res = ReviewResult(findings=[
            Finding(file="src/auth.py", line=15, severity="high", message="Hardcoded secret key", category="security")
        ])
        style_res = ReviewResult(findings=[
            Finding(file="src/auth.py", line=20, severity="low", message="Use snake_case for variable", category="style")
        ])
        logic_res = ReviewResult(findings=[
            Finding(file="src/auth.py", line=35, severity="medium", message="Potential None dereference", category="logic")
        ])

        sec_agent.run = AsyncMock(return_value=sec_res)
        style_agent.run = AsyncMock(return_value=style_res)
        logic_agent.run = AsyncMock(return_value=logic_res)

        supervisor = ReviewSupervisor(
            security_agent=sec_agent,
            style_agent=style_agent,
            logic_agent=logic_agent,
        )

        result = await supervisor.review("diff --git a/src/auth.py b/src/auth.py...")

        assert isinstance(result, ReviewResult)
        assert len(result.findings) == 3
        # Has high severity -> request_changes
        assert result.verdict == "request_changes"
        assert result.errors is None

        # Verify all three agents were called
        sec_agent.run.assert_awaited_once()
        style_agent.run.assert_awaited_once()
        logic_agent.run.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_supervisor_handles_agent_failure_gracefully(self, mock_env):
        sec_agent = SecurityAgent()
        style_agent = StyleAgent()
        logic_agent = LogicAgent()

        sec_res = ReviewResult(findings=[
            Finding(file="src/auth.py", line=15, severity="low", message="Minor comment", category="security")
        ])
        style_res = ReviewResult(findings=[])

        sec_agent.run = AsyncMock(return_value=sec_res)
        style_agent.run = AsyncMock(return_value=style_res)
        # LogicAgent raises an unexpected error
        logic_agent.run = AsyncMock(side_effect=RuntimeError("Gemini quota exceeded"))

        supervisor = ReviewSupervisor(
            security_agent=sec_agent,
            style_agent=style_agent,
            logic_agent=logic_agent,
        )

        result = await supervisor.review("diff content")

        # The review did NOT crash
        assert isinstance(result, ReviewResult)
        assert len(result.findings) == 1
        assert result.verdict == "approve"  # only low finding
        assert result.errors is not None
        assert any("LogicAgent failed" in err for err in result.errors)

    def test_supervisor_create_workflow(self, mock_env):
        with patch("app.agents.base_agent.ChatGoogleGenerativeAI"):
            supervisor = ReviewSupervisor()
            compiled_graph = supervisor.create_workflow()
            assert compiled_graph is not None

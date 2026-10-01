"""
test_main.py
============
Tests for the FastAPI application endpoints in app/main.py.
"""

from unittest.mock import AsyncMock, patch
import pytest
from fastapi.testclient import TestClient

from app.agents import Finding, ReviewResult
from app.main import (
    FindingResponse,
    app,
    build_review_context,
    generate_summary,
    get_supervisor,
)

client = TestClient(app)


# ---------------------------------------------------------------------------
# Unit tests for helper functions
# ---------------------------------------------------------------------------


class TestHelpers:
    def test_generate_summary_empty(self):
        summary = generate_summary([])
        assert summary == "No significant issues were found in the pull request."

    def test_generate_summary_single_high(self):
        f = FindingResponse(
            file="a.py", line=1, severity="high", message="SQLi", category="security"
        )
        summary = generate_summary([f])
        assert summary == "1 issue found: 1 high severity."

    def test_generate_summary_multiple(self):
        findings = [
            FindingResponse(file="a.py", line=1, severity="high", message="SQLi", category="security"),
            FindingResponse(file="b.py", line=2, severity="medium", message="None risk", category="logic"),
            FindingResponse(file="c.py", line=3, severity="low", message="Naming", category="style"),
        ]
        summary = generate_summary(findings)
        assert summary == "3 issues found: 1 high, 1 medium, and 1 low severity."

    def test_generate_summary_two_severities(self):
        findings = [
            FindingResponse(file="a.py", line=1, severity="critical", message="RCE", category="security"),
            FindingResponse(file="b.py", line=2, severity="medium", message="Bug", category="logic"),
        ]
        summary = generate_summary(findings)
        assert summary == "2 issues found: 1 critical and 1 medium severity."

    def test_build_review_context(self):
        from app.main import ReviewRequest
        req = ReviewRequest(
            repo_url="https://github.com/example/repo",
            pr_number=42,
            diff="diff --git a/file.py b/file.py",
            changed_files=["src/auth.py", "src/db.py"],
            base_sha="abc1234",
            head_sha="def5678",
        )
        context = build_review_context(req)
        assert "Pull Request #42" in context
        assert "https://github.com/example/repo" in context
        assert "abc1234" in context
        assert "def5678" in context
        assert "- src/auth.py" in context
        assert "diff --git a/file.py" in context


# ---------------------------------------------------------------------------
# GET /health Tests
# ---------------------------------------------------------------------------


class TestHealthEndpoint:
    def test_health_returns_200(self):
        response = client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert data["service"] == "ai-code-reviewer"


# ---------------------------------------------------------------------------
# POST /review Validation Tests (HTTP 400)
# ---------------------------------------------------------------------------


class TestReviewValidation:
    def test_missing_required_fields(self):
        response = client.post("/review", json={})
        assert response.status_code == 400
        data = response.json()
        assert data["error"] == "Validation error"
        assert len(data["detail"]) > 0

    def test_invalid_pr_number_zero(self):
        payload = {
            "repo_url": "https://github.com/example/repo",
            "pr_number": 0,  # invalid (must be > 0)
            "diff": "diff content",
            "changed_files": ["a.py"],
            "base_sha": "abc",
            "head_sha": "def",
        }
        response = client.post("/review", json=payload)
        assert response.status_code == 400
        assert any("pr_number" in d for d in response.json()["detail"])

    def test_empty_string_fields(self):
        payload = {
            "repo_url": "   ",  # whitespace only
            "pr_number": 1,
            "diff": "",
            "changed_files": ["a.py"],
            "base_sha": "",
            "head_sha": "",
        }
        response = client.post("/review", json=payload)
        assert response.status_code == 400
        assert len(response.json()["detail"]) > 0


# ---------------------------------------------------------------------------
# POST /review Success & Pipeline Failure Tests
# ---------------------------------------------------------------------------


class TestReviewEndpoint:
    def test_successful_review_request_changes(self):
        mock_result = ReviewResult(
            findings=[
                Finding(
                    file="src/db/user.py",
                    line=25,
                    severity="high",
                    message="Potential SQL injection vulnerability.",
                    category="security",
                )
            ],
            verdict="request_changes",
            agent_breakdown={"security": 1, "style": 0, "logic": 0},
        )

        mock_supervisor = AsyncMock()
        mock_supervisor.review = AsyncMock(return_value=mock_result)

        # Override dependency
        app.dependency_overrides[get_supervisor] = lambda: mock_supervisor

        try:
            payload = {
                "repo_url": "https://github.com/example/repository",
                "pr_number": 123,
                "diff": "diff --git a/src/db/user.py b/src/db/user.py\n+ query = f'SELECT * FROM users WHERE id = {user_id}'",
                "changed_files": ["src/db/user.py"],
                "base_sha": "abc1234",
                "head_sha": "def5678",
            }
            response = client.post("/review", json=payload)
            assert response.status_code == 200

            data = response.json()
            assert data["verdict"] == "request_changes"
            assert len(data["findings"]) == 1
            assert data["findings"][0]["file"] == "src/db/user.py"
            assert data["findings"][0]["severity"] == "high"
            assert data["agent_breakdown"] == {"security": 1, "style": 0, "logic": 0}
            assert "1 high severity" in data["summary"]

            # Confirm supervisor was called with constructed context
            mock_supervisor.review.assert_awaited_once()
            called_context = mock_supervisor.review.call_args[0][0]
            assert "Pull Request #123" in called_context
            assert "src/db/user.py" in called_context

        finally:
            app.dependency_overrides.clear()

    def test_successful_review_approve(self):
        mock_result = ReviewResult(
            findings=[],
            verdict="approve",
            agent_breakdown={"security": 0, "style": 0, "logic": 0},
        )

        mock_supervisor = AsyncMock()
        mock_supervisor.review = AsyncMock(return_value=mock_result)

        app.dependency_overrides[get_supervisor] = lambda: mock_supervisor

        try:
            payload = {
                "repo_url": "https://github.com/example/repository",
                "pr_number": 456,
                "diff": "diff --git a/readme.md b/readme.md\n+ # Updates",
                "changed_files": ["readme.md"],
                "base_sha": "abc1234",
                "head_sha": "def5678",
            }
            response = client.post("/review", json=payload)
            assert response.status_code == 200
            data = response.json()
            assert data["verdict"] == "approve"
            assert data["findings"] == []
            assert "No significant issues" in data["summary"]
            assert data["agent_breakdown"] == {"security": 0, "style": 0, "logic": 0}

        finally:
            app.dependency_overrides.clear()

    def test_pipeline_failure_returns_500_with_safe_response(self):
        mock_supervisor = AsyncMock()
        mock_supervisor.review = AsyncMock(side_effect=RuntimeError("Secret API key connection dropped"))

        app.dependency_overrides[get_supervisor] = lambda: mock_supervisor

        try:
            payload = {
                "repo_url": "https://github.com/example/repository",
                "pr_number": 789,
                "diff": "some diff",
                "changed_files": ["main.py"],
                "base_sha": "abc",
                "head_sha": "def",
            }
            response = client.post("/review", json=payload)
            assert response.status_code == 500

            data = response.json()
            assert data["error"] == "Review pipeline failed"
            assert data["detail"] == "Unable to complete code review"
            # Ensure sensitive info / stack trace was NOT leaked to client
            raw_text = response.text
            assert "Secret API key" not in raw_text
            assert "Traceback" not in raw_text

        finally:
            app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# CORS Preflight Tests
# ---------------------------------------------------------------------------


class TestCORS:
    def test_cors_headers_present(self):
        headers = {
            "Origin": "http://localhost:8000",
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "Content-Type",
        }
        response = client.options("/review", headers=headers)
        assert response.status_code == 200
        assert response.headers.get("access-control-allow-origin") == "http://localhost:8000"

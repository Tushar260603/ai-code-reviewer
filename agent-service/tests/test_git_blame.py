"""
test_git_blame.py
=================
Unit tests for the git_blame LangChain tool.

Tests that need a real git repo initialise a minimal one in tmp_path.
"""

import json
import subprocess
import pytest
from pathlib import Path


def invoke(file: str, start_line: int, end_line: int) -> dict:
    from app.tools.git_blame import git_blame
    return json.loads(git_blame.invoke({"file": file, "start_line": start_line, "end_line": end_line}))


def init_git_repo(path: Path):
    """Initialise a git repo with one commit so blame works."""
    subprocess.run(["git", "init"], cwd=path, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.email", "test@test.com"], cwd=path, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.name", "Test User"], cwd=path, check=True, capture_output=True)
    # Write a sample file
    sample = path / "sample.py"
    sample.write_text("line_one\nline_two\nline_three\n")
    subprocess.run(["git", "add", "."], cwd=path, check=True, capture_output=True)
    subprocess.run(["git", "commit", "-m", "initial"], cwd=path, check=True, capture_output=True)


# ---------------------------------------------------------------------------
# Git-available tests (skipped if git is not installed)
# ---------------------------------------------------------------------------

git_available = pytest.mark.skipif(
    subprocess.run(["git", "--version"], capture_output=True).returncode != 0,
    reason="git not available on this system",
)


@git_available
class TestGitBlameSuccess:
    def test_blames_single_line(self, set_repo_root):
        tmp = set_repo_root
        init_git_repo(tmp)

        result = invoke("sample.py", 1, 1)

        assert result["success"] is True
        assert len(result["blame"]) == 1
        assert result["blame"][0]["line"] == 1
        assert result["blame"][0]["content"] == "line_one"
        assert result["blame"][0]["author"] == "Test User"
        assert "commit" in result["blame"][0]
        assert "date" in result["blame"][0]

    def test_blames_range(self, set_repo_root):
        tmp = set_repo_root
        init_git_repo(tmp)

        result = invoke("sample.py", 1, 3)

        assert result["success"] is True
        assert len(result["blame"]) == 3
        lines = [b["line"] for b in result["blame"]]
        assert lines == [1, 2, 3]

    def test_returns_correct_content(self, set_repo_root):
        tmp = set_repo_root
        init_git_repo(tmp)

        result = invoke("sample.py", 2, 2)

        assert result["success"] is True
        assert result["blame"][0]["content"] == "line_two"


# ---------------------------------------------------------------------------
# Error-path tests (no git repo needed)
# ---------------------------------------------------------------------------

class TestGitBlameErrors:
    def test_missing_file_returns_error(self, set_repo_root):
        result = invoke("nonexistent.py", 1, 5)

        assert result["success"] is False
        assert "not found" in result["error"].lower()

    def test_path_traversal_blocked(self, set_repo_root):
        result = invoke("../../etc/passwd", 1, 1)

        assert result["success"] is False
        assert "traversal" in result["error"].lower() or "denied" in result["error"].lower()

    def test_end_before_start_returns_error(self, set_repo_root):
        tmp = set_repo_root
        (tmp / "f.py").write_text("x\n")

        result = invoke("f.py", 10, 5)

        assert result["success"] is False
        assert "end_line" in result["error"]

    def test_start_line_zero_returns_error(self, set_repo_root):
        tmp = set_repo_root
        (tmp / "f.py").write_text("x\n")

        result = invoke("f.py", 0, 5)

        assert result["success"] is False
        assert "start_line" in result["error"]

    def test_range_too_large_returns_error(self, set_repo_root):
        tmp = set_repo_root
        (tmp / "f.py").write_text("x\n")

        result = invoke("f.py", 1, 600)

        assert result["success"] is False
        assert "maximum" in result["error"].lower() or "range" in result["error"].lower()

    def test_no_repo_root(self, monkeypatch):
        monkeypatch.delenv("REPO_ROOT", raising=False)

        result = invoke("any.py", 1, 5)

        assert result["success"] is False
        assert "REPO_ROOT" in result["error"]

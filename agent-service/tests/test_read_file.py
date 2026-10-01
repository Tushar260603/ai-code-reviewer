"""
test_read_file.py
=================
Unit tests for the read_file LangChain tool.

All tests use a temporary directory as REPO_ROOT (injected by conftest.py).
No real files from the project are needed.
"""

import json
import pytest


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def invoke(path: str) -> dict:
    """Call the tool and parse the JSON result."""
    from app.tools.read_file import read_file
    return json.loads(read_file.invoke({"path": path}))


# ---------------------------------------------------------------------------
# Happy-path tests
# ---------------------------------------------------------------------------

class TestReadFileSuccess:
    def test_reads_simple_file(self, set_repo_root):
        tmp = set_repo_root
        (tmp / "hello.py").write_text("def hello():\n    return 'world'\n")

        result = invoke("hello.py")

        assert result["success"] is True
        assert result["path"] == "hello.py"
        assert result["total_lines"] == 2
        assert "1: def hello():" in result["content"]
        assert "2:     return 'world'" in result["content"]

    def test_reads_nested_file(self, set_repo_root):
        tmp = set_repo_root
        (tmp / "src").mkdir()
        (tmp / "src" / "util.py").write_text("x = 1\n")

        result = invoke("src/util.py")

        assert result["success"] is True
        assert result["path"] == "src/util.py"
        assert result["total_lines"] == 1

    def test_line_numbers_are_correct(self, set_repo_root):
        tmp = set_repo_root
        lines = ["line_one", "line_two", "line_three"]
        (tmp / "multi.txt").write_text("\n".join(lines))

        result = invoke("multi.txt")

        assert result["success"] is True
        for i, line in enumerate(lines, start=1):
            assert f"{i}: {line}" in result["content"]

    def test_strips_leading_slash(self, set_repo_root):
        tmp = set_repo_root
        (tmp / "readme.md").write_text("# Hello")

        result = invoke("/readme.md")  # leading slash should be stripped

        assert result["success"] is True
        assert result["path"] == "readme.md"


# ---------------------------------------------------------------------------
# Error-path tests
# ---------------------------------------------------------------------------

class TestReadFileErrors:
    def test_missing_file_returns_error(self, set_repo_root):
        result = invoke("does_not_exist.py")

        assert result["success"] is False
        assert "not found" in result["error"].lower()

    def test_directory_returns_error(self, set_repo_root):
        tmp = set_repo_root
        (tmp / "mydir").mkdir()

        result = invoke("mydir")

        assert result["success"] is False
        assert "directory" in result["error"].lower()

    def test_path_traversal_blocked(self, set_repo_root):
        result = invoke("../../etc/passwd")

        assert result["success"] is False
        assert "traversal" in result["error"].lower() or "denied" in result["error"].lower()

    def test_empty_path_returns_error(self, set_repo_root):
        result = invoke("")

        assert result["success"] is False

    def test_no_repo_root(self, monkeypatch):
        monkeypatch.delenv("REPO_ROOT", raising=False)

        result = invoke("anything.py")

        assert result["success"] is False
        assert "REPO_ROOT" in result["error"]

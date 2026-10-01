"""
test_search_codebase.py
=======================
Unit tests for the search_codebase LangChain tool.
"""

import json
import pytest


def invoke(pattern: str, max_matches: int = 100) -> dict:
    from app.tools.search_codebase import search_codebase
    return json.loads(search_codebase.invoke({"pattern": pattern, "max_matches": max_matches}))


# ---------------------------------------------------------------------------
# Happy-path tests
# ---------------------------------------------------------------------------

class TestSearchCodebaseSuccess:
    def test_finds_simple_pattern(self, set_repo_root):
        tmp = set_repo_root
        (tmp / "main.py").write_text("def get_user(id):\n    return id\n")

        result = invoke("get_user")

        assert result["success"] is True
        assert result["total_matches"] >= 1
        assert any(m["file"] == "main.py" for m in result["matches"])

    def test_returns_correct_line_number(self, set_repo_root):
        tmp = set_repo_root
        (tmp / "file.py").write_text("line1\nline2\ntarget_line\nline4\n")

        result = invoke("target_line")

        assert result["success"] is True
        match = next(m for m in result["matches"] if m["file"] == "file.py")
        assert match["line"] == 3

    def test_searches_nested_directories(self, set_repo_root):
        tmp = set_repo_root
        (tmp / "pkg").mkdir()
        (tmp / "pkg" / "service.py").write_text("class AuthService:\n    pass\n")

        result = invoke("AuthService")

        assert result["success"] is True
        files = [m["file"] for m in result["matches"]]
        assert any("service.py" in f for f in files)

    def test_regex_pattern_works(self, set_repo_root):
        tmp = set_repo_root
        (tmp / "code.py").write_text("foo = 1\nbar = 2\nbaz = 3\n")

        result = invoke(r"ba[rz]")

        assert result["success"] is True
        assert result["total_matches"] == 2

    def test_max_matches_respected(self, set_repo_root):
        tmp = set_repo_root
        # Write a file with 20 matching lines
        (tmp / "big.py").write_text("\n".join(["MATCH"] * 20))

        result = invoke("MATCH", max_matches=5)

        assert result["success"] is True
        assert result["total_matches"] <= 5
        assert result["truncated"] is True

    def test_no_matches_returns_empty_list(self, set_repo_root):
        tmp = set_repo_root
        (tmp / "empty.py").write_text("nothing here\n")

        result = invoke("THIS_WILL_NOT_MATCH_XYZ")

        assert result["success"] is True
        assert result["total_matches"] == 0
        assert result["matches"] == []
        assert result["truncated"] is False

    def test_ignores_git_directory(self, set_repo_root):
        tmp = set_repo_root
        (tmp / ".git").mkdir()
        (tmp / ".git" / "config").write_text("SECRET_PATTERN\n")
        (tmp / "real.py").write_text("nothing\n")

        result = invoke("SECRET_PATTERN")

        assert result["success"] is True
        assert all(".git" not in m["file"] for m in result["matches"])

    def test_ignores_node_modules(self, set_repo_root):
        tmp = set_repo_root
        (tmp / "node_modules").mkdir()
        (tmp / "node_modules" / "lib.js").write_text("FIND_ME\n")

        result = invoke("FIND_ME")

        assert result["success"] is True
        assert all("node_modules" not in m["file"] for m in result["matches"])


# ---------------------------------------------------------------------------
# Error-path tests
# ---------------------------------------------------------------------------

class TestSearchCodebaseErrors:
    def test_invalid_regex_returns_error(self, set_repo_root):
        result = invoke("[invalid regex(")

        assert result["success"] is False
        assert "Invalid regular expression" in result["error"]

    def test_empty_pattern_returns_error(self, set_repo_root):
        result = invoke("")

        assert result["success"] is False

    def test_no_repo_root(self, monkeypatch):
        monkeypatch.delenv("REPO_ROOT", raising=False)

        result = invoke("anything")

        assert result["success"] is False
        assert "REPO_ROOT" in result["error"]

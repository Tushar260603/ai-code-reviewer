"""
test_github.py
==============
Unit tests for the GitHub integration layer:
- app/github/diff_parser.py
- app/github/comment_poster.py
"""

from unittest.mock import MagicMock, patch
import pytest
from github import GithubException

from app.github import (
    create_check_run,
    get_github_client,
    parse_diff,
    post_inline_comment,
    post_summary_comment,
    resolve_repository,
)


# ---------------------------------------------------------------------------
# diff_parser Tests
# ---------------------------------------------------------------------------


class TestDiffParser:
    def test_empty_diff_returns_empty_list(self):
        assert parse_diff("") == []
        assert parse_diff("   \n\n  ") == []

    def test_single_file_single_hunk(self):
        diff = """diff --git a/src/user.py b/src/user.py
--- a/src/user.py
+++ b/src/user.py
@@ -10,5 +10,7 @@
 def get_user(user_id):
-    query = "SELECT * FROM users"
+    query = f"SELECT * FROM users WHERE id = {user_id}"
+    result = db.execute(query)
     return result
"""
        result = parse_diff(diff)
        assert len(result) == 1
        entry = result[0]
        assert entry["file"] == "src/user.py"

        # Check added lines
        added = entry["added_lines"]
        assert len(added) == 2
        assert added[0]["line_number"] == 11
        assert added[0]["content"] == '    query = f"SELECT * FROM users WHERE id = {user_id}"'
        assert added[1]["line_number"] == 12
        assert added[1]["content"] == '    result = db.execute(query)'

        # Check removed lines
        removed = entry["removed_lines"]
        assert len(removed) == 1
        assert removed[0]["line_number"] == 11
        assert removed[0]["content"] == '    query = "SELECT * FROM users"'

    def test_multiple_hunks_in_single_file(self):
        diff = """diff --git a/app/main.py b/app/main.py
--- a/app/main.py
+++ b/app/main.py
@@ -5,3 +5,4 @@ import sys
+import os
 import logging
@@ -20,3 +21,4 @@ def run():
+    print("starting")
     return True
"""
        result = parse_diff(diff)
        assert len(result) == 1
        entry = result[0]
        assert entry["file"] == "app/main.py"
        assert len(entry["added_lines"]) == 2
        assert entry["added_lines"][0]["line_number"] == 5
        assert entry["added_lines"][0]["content"] == "import os"
        assert entry["added_lines"][1]["line_number"] == 21
        assert entry["added_lines"][1]["content"] == '    print("starting")'

    def test_multiple_files(self):
        diff = """diff --git a/file1.py b/file1.py
--- a/file1.py
+++ b/file1.py
@@ -1,2 +1,3 @@
+line1
 line2
diff --git a/file2.py b/file2.py
--- a/file2.py
+++ b/file2.py
@@ -1,2 +1,3 @@
 line_a
+line_b
"""
        result = parse_diff(diff)
        assert len(result) == 2
        assert result[0]["file"] == "file1.py"
        assert result[1]["file"] == "file2.py"
        assert len(result[0]["added_lines"]) == 1
        assert len(result[1]["added_lines"]) == 1

    def test_new_file(self):
        diff = """diff --git a/src/new.py b/src/new.py
new file mode 100644
--- /dev/null
+++ b/src/new.py
@@ -0,0 +1,2 @@
+def new_func():
+    pass
"""
        result = parse_diff(diff)
        assert len(result) == 1
        entry = result[0]
        assert entry["file"] == "src/new.py"
        assert len(entry["added_lines"]) == 2
        assert entry["added_lines"][0]["line_number"] == 1
        assert entry["added_lines"][1]["line_number"] == 2
        assert entry["removed_lines"] == []

    def test_deleted_file(self):
        diff = """diff --git a/src/old.py b/src/old.py
deleted file mode 100644
--- a/src/old.py
+++ /dev/null
@@ -1,2 +0,0 @@
-line 1
-line 2
"""
        result = parse_diff(diff)
        assert len(result) == 1
        entry = result[0]
        assert entry["file"] == "src/old.py"
        assert entry["added_lines"] == []
        assert len(entry["removed_lines"]) == 2
        assert entry["removed_lines"][0]["line_number"] == 1

    def test_renamed_file(self):
        diff = """diff --git a/old_name.py b/new_name.py
similarity index 98%
rename from old_name.py
rename to new_name.py
--- a/old_name.py
+++ b/new_name.py
@@ -1,2 +1,2 @@
-v1 = 1
+v1 = 2
"""
        result = parse_diff(diff)
        assert len(result) == 1
        assert result[0]["file"] == "new_name.py"
        assert result[0]["added_lines"][0]["line_number"] == 1

    def test_binary_file_handled_gracefully(self):
        diff = """diff --git a/logo.png b/logo.png
Binary files a/logo.png and b/logo.png differ
"""
        result = parse_diff(diff)
        assert len(result) == 1
        assert result[0]["file"] == "logo.png"
        assert result[0]["added_lines"] == []
        assert result[0]["removed_lines"] == []

    def test_no_newline_indicator(self):
        diff = r"""diff --git a/text.txt b/text.txt
--- a/text.txt
+++ b/text.txt
@@ -1,1 +1,1 @@
-old line
\ No newline at end of file
+new line
\ No newline at end of file
"""
        result = parse_diff(diff)
        assert len(result) == 1
        assert result[0]["added_lines"][0]["content"] == "new line"
        assert result[0]["removed_lines"][0]["content"] == "old line"


# ---------------------------------------------------------------------------
# comment_poster Tests
# ---------------------------------------------------------------------------


class TestCommentPoster:
    def test_get_github_client_raises_without_token(self, monkeypatch):
        monkeypatch.delenv("GITHUB_TOKEN", raising=False)
        with pytest.raises(ValueError, match="GITHUB_TOKEN is not set"):
            get_github_client()

    def test_get_github_client_with_token(self):
        client = get_github_client(token="fake_token_123")
        assert client is not None

    def test_resolve_repository_with_mock_client(self):
        mock_repo = MagicMock()
        mock_client = MagicMock()
        mock_client.get_repo.return_value = mock_repo

        repo = resolve_repository("owner/my-repo", github_client=mock_client)
        assert repo is mock_repo
        mock_client.get_repo.assert_called_once_with("owner/my-repo")

    def test_resolve_repository_with_existing_repo(self):
        from github.Repository import Repository
        mock_repo = MagicMock(spec=Repository)
        assert resolve_repository(mock_repo) is mock_repo

    def test_post_summary_comment_validation_errors(self):
        res1 = post_summary_comment("owner/repo", 0, "body")
        assert res1["success"] is False
        assert "positive integer" in res1["detail"]

        res2 = post_summary_comment("owner/repo", 1, "")
        assert res2["success"] is False
        assert "empty" in res2["detail"]

    def test_post_summary_comment_success(self):
        mock_repo = MagicMock()
        mock_pr = MagicMock()
        mock_comment = MagicMock()
        mock_comment.id = 999
        mock_comment.html_url = "https://github.com/owner/repo/pull/1#issuecomment-999"

        mock_repo.get_pull.return_value = mock_pr
        mock_pr.create_issue_comment.return_value = mock_comment

        result = post_summary_comment(mock_repo, 1, "Review Summary")
        assert result["success"] is True
        assert result["comment_id"] == 999
        assert result["url"] == "https://github.com/owner/repo/pull/1#issuecomment-999"
        mock_pr.create_issue_comment.assert_called_once_with("Review Summary")

    def test_post_summary_comment_api_error(self):
        mock_repo = MagicMock()
        mock_repo.get_pull.side_effect = RuntimeError("Connection timeout")

        result = post_summary_comment(mock_repo, 1, "Review Summary")
        assert result["success"] is False
        assert "Connection timeout" in result["detail"]

    def test_post_inline_comment_validation_errors(self):
        res1 = post_inline_comment("owner/repo", 1, "", 10, "message")
        assert res1["success"] is False
        assert "File path" in res1["detail"]

        res2 = post_inline_comment("owner/repo", 1, "a.py", 0, "message")
        assert res2["success"] is False
        assert "line must be an integer greater than 0" in res2["detail"]

        res3 = post_inline_comment("owner/repo", 1, "a.py", 10, "")
        assert res3["success"] is False
        assert "Comment body" in res3["detail"]

    def test_post_inline_comment_success(self):
        mock_repo = MagicMock()
        mock_pr = MagicMock()
        mock_pr.head.sha = "head_sha_123"
        mock_comment = MagicMock()
        mock_comment.id = 888
        mock_comment.html_url = "https://github.com/owner/repo/pull/1#discussion_r888"

        mock_repo.get_pull.return_value = mock_pr
        mock_pr.create_review_comment.return_value = mock_comment

        result = post_inline_comment(
            mock_repo,
            pr_number=1,
            file="src/auth.py",
            line=42,
            body="Potential SQL injection",
        )
        assert result["success"] is True
        assert result["comment_id"] == 888
        mock_pr.create_review_comment.assert_called_once_with(
            body="Potential SQL injection",
            commit="head_sha_123",
            path="src/auth.py",
            line=42,
            side="RIGHT",
        )

    def test_post_inline_comment_diff_rejection(self):
        mock_repo = MagicMock()
        mock_pr = MagicMock()
        mock_pr.head.sha = "head_sha_123"

        # Simulate GitHub 422 line not part of diff
        mock_pr.create_review_comment.side_effect = GithubException(
            status=422,
            data={"message": "line must be part of the diff"},
            headers={},
        )
        mock_repo.get_pull.return_value = mock_pr

        result = post_inline_comment(mock_repo, 1, "src/auth.py", 99, "Finding")
        assert result["success"] is False
        assert "not part of the diff" in result["detail"].lower()

    def test_create_check_run_validation_errors(self):
        res1 = create_check_run("owner/repo", "", "AI Review")
        assert res1["success"] is False
        assert "SHA" in res1["detail"]

        res2 = create_check_run("owner/repo", "sha1", "", status="completed", conclusion="success")
        assert res2["success"] is False
        assert "name" in res2["detail"]

        res3 = create_check_run("owner/repo", "sha1", "AI Review", status="invalid_status")
        assert res3["success"] is False
        assert "Status" in res3["detail"]

        res4 = create_check_run("owner/repo", "sha1", "AI Review", status="completed", conclusion="bad_conclusion")
        assert res4["success"] is False
        assert "Conclusion" in res4["detail"]

    def test_create_check_run_success_with_batching(self):
        mock_repo = MagicMock()
        mock_check_run = MagicMock()
        mock_check_run.id = 777
        mock_check_run.html_url = "https://github.com/owner/repo/runs/777"
        mock_repo.create_check_run.return_value = mock_check_run

        # Generate 75 annotations (should trigger 2 batches: 50 + 25)
        annotations = [
            {
                "path": f"src/file_{i}.py",
                "start_line": i,
                "end_line": i,
                "annotation_level": "failure",
                "message": f"Issue #{i}",
            }
            for i in range(1, 76)
        ]

        result = create_check_run(
            repo=mock_repo,
            sha="sha_abc123",
            name="AI Code Review",
            status="completed",
            conclusion="failure",
            annotations=annotations,
        )

        assert result["success"] is True
        assert result["check_run_id"] == 777

        # Check first batch of 50 was passed to create_check_run
        create_kwargs = mock_repo.create_check_run.call_args[1]
        first_batch = create_kwargs["output"]["annotations"]
        assert len(first_batch) == 50

        # Check second batch of 25 was passed to check_run.edit
        mock_check_run.edit.assert_called_once()
        edit_kwargs = mock_check_run.edit.call_args[1]
        second_batch = edit_kwargs["output"]["annotations"]
        assert len(second_batch) == 25

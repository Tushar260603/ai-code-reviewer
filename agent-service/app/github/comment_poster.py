"""
comment_poster.py
=================
GitHub API operations using PyGithub.

Functions
---------
* post_summary_comment: Posts an overall summary comment to a Pull Request.
* post_inline_comment: Posts an inline discussion comment attached to a changed line.
* create_check_run: Creates a GitHub Check Run with finding annotations.

Key design principles
---------------------
* Zero side-effects on import (no network calls, no client creation at import time).
* Accepts repository as either "owner/repo" string or PyGithub Repository instance.
* Returns only pure JSON-serializable Python data structures (dict, list, str, int, bool).
* Safe error handling: never leaks tokens, environment variables, or credentials.
"""

from __future__ import annotations

import logging
import os
from typing import Any, Dict, List, Optional, Union

from github import Auth, Github, GithubException
from github.Repository import Repository

logger = logging.getLogger("agent_service.github.comment_poster")

# GitHub limits check run annotations to 50 items per API call
MAX_CHECK_RUN_ANNOTATIONS = 50

VALID_STATUSES = frozenset({"queued", "in_progress", "completed"})
VALID_CONCLUSIONS = frozenset(
    {"action_required", "cancelled", "failure", "neutral", "success", "skipped", "timed_out"}
)
VALID_ANNOTATION_LEVELS = frozenset({"notice", "warning", "failure"})


def get_github_client(token: Optional[str] = None) -> Github:
    """
    Instantiate and return a PyGithub client.

    Args:
        token: Optional personal access token or GitHub App installation token.
               If omitted, reads from the GITHUB_TOKEN environment variable.

    Returns:
        Authenticated PyGithub Github client.

    Raises:
        ValueError: If no token is provided and GITHUB_TOKEN is not set.
    """
    auth_token = token or os.getenv("GITHUB_TOKEN")
    if not auth_token or not auth_token.strip():
        raise ValueError(
            "GITHUB_TOKEN is not set. Provide a valid token or set the GITHUB_TOKEN environment variable."
        )

    clean_token = auth_token.strip()
    return Github(auth=Auth.Token(clean_token))


def resolve_repository(
    repo: Union[str, Any],
    github_client: Optional[Github] = None,
) -> Any:
    """
    Resolve a repository parameter into a PyGithub Repository object.

    Args:
        repo: Repository identifier, either as "owner/name" string or an existing
              PyGithub Repository instance.
        github_client: Optional authenticated PyGithub client used when repo is a string.

    Returns:
        PyGithub Repository instance.
    """
    if isinstance(repo, str):
        clean_name = repo.strip()
        if not clean_name:
            raise ValueError("Repository name cannot be empty.")
        client = github_client or get_github_client()
        return client.get_repo(clean_name)

    if hasattr(repo, "get_pull") or hasattr(repo, "create_check_run") or isinstance(repo, Repository):
        return repo

    raise TypeError(f"Expected repo to be str or Repository, got {type(repo).__name__}.")


def _sanitize_error(exc: Exception) -> str:
    """Extract a user-facing error message without leaking sensitive credentials."""
    if isinstance(exc, GithubException):
        data = getattr(exc, "data", None)
        if isinstance(data, dict) and "message" in data:
            return f"GitHub API error ({exc.status}): {data['message']}"
        return f"GitHub API error ({exc.status}): {exc}"
    return str(exc)


def post_summary_comment(
    repo: Union[str, Repository],
    pr_number: int,
    body: str,
) -> Dict[str, Any]:
    """
    Post a general summary comment to a GitHub Pull Request.

    Args:
        repo: Repository as "owner/repo" string or PyGithub Repository object.
        pr_number: Pull Request number (positive integer).
        body: Markdown comment body text.

    Returns:
        JSON-serializable dict:
        {"success": True, "comment_id": 12345, "url": "..."}
        or
        {"success": False, "error": "...", "detail": "..."}
    """
    if not body or not body.strip():
        return {
            "success": False,
            "error": "Validation error",
            "detail": "Comment body must not be empty.",
        }

    if not isinstance(pr_number, int) or pr_number <= 0:
        return {
            "success": False,
            "error": "Validation error",
            "detail": "pr_number must be a positive integer.",
        }

    try:
        repository = resolve_repository(repo)
        pull_request = repository.get_pull(pr_number)
        comment = pull_request.create_issue_comment(body.strip())

        return {
            "success": True,
            "comment_id": comment.id,
            "url": comment.html_url,
        }
    except Exception as exc:
        logger.error("Failed to post summary comment to PR #%s: %s", pr_number, exc)
        return {
            "success": False,
            "error": "GitHub API request failed",
            "detail": _sanitize_error(exc),
        }


def post_inline_comment(
    repo: Union[str, Repository],
    pr_number: int,
    file: str,
    line: int,
    body: str,
) -> Dict[str, Any]:
    """
    Post an inline review comment on a specific line of a Pull Request.

    Args:
        repo: Repository as "owner/repo" string or PyGithub Repository object.
        pr_number: Pull Request number (positive integer).
        file: Repository-relative file path of the changed file.
        line: 1-based line number in the new version of the file.
        body: Markdown comment text.

    Returns:
        JSON-serializable dict:
        {"success": True, "comment_id": 12345, "url": "..."}
        or
        {"success": False, "error": "...", "detail": "..."}
    """
    clean_file = file.strip().lstrip("/").replace("\\", "/") if file else ""
    if not clean_file:
        return {
            "success": False,
            "error": "Validation error",
            "detail": "File path must not be empty.",
        }

    if not isinstance(line, int) or line <= 0:
        return {
            "success": False,
            "error": "Validation error",
            "detail": "line must be an integer greater than 0.",
        }

    if not body or not body.strip():
        return {
            "success": False,
            "error": "Validation error",
            "detail": "Comment body must not be empty.",
        }

    try:
        repository = resolve_repository(repo)
        pull_request = repository.get_pull(pr_number)
        head_commit_sha = pull_request.head.sha

        comment = pull_request.create_review_comment(
            body=body.strip(),
            commit=head_commit_sha,
            path=clean_file,
            line=line,
            side="RIGHT",
        )

        return {
            "success": True,
            "comment_id": comment.id,
            "url": comment.html_url,
        }
    except GithubException as exc:
        msg = _sanitize_error(exc)
        logger.warning(
            "GitHub rejected inline comment on PR #%d (%s:%d): %s",
            pr_number,
            clean_file,
            line,
            msg,
        )
        return {
            "success": False,
            "error": "Failed to create inline review comment",
            "detail": f"Line is not part of the diff or was rejected by GitHub: {msg}",
        }
    except Exception as exc:
        logger.error("Failed to post inline comment to PR #%s: %s", pr_number, exc)
        return {
            "success": False,
            "error": "GitHub API request failed",
            "detail": _sanitize_error(exc),
        }


def create_check_run(
    repo: Union[str, Repository],
    sha: str,
    name: str,
    status: str = "completed",
    conclusion: Optional[str] = None,
    annotations: Optional[List[Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    """
    Create a GitHub Check Run for a commit, batching annotations as needed.

    Args:
        repo: Repository as "owner/repo" string or PyGithub Repository object.
        sha: Commit SHA to associate the check run with.
        name: Name of the check run (e.g. "AI Code Review").
        status: Check run status: "queued", "in_progress", or "completed".
        conclusion: Required if status="completed". Values: "success", "failure", "neutral", etc.
        annotations: Optional list of check run annotations in GitHub format:
            [
                {
                    "path": "src/user.py",
                    "start_line": 25,
                    "end_line": 25,
                    "annotation_level": "failure", # "notice", "warning", "failure"
                    "message": "Potential SQL injection vulnerability."
                }
            ]

    Returns:
        JSON-serializable dict:
        {"success": True, "check_run_id": 12345, "url": "..."}
        or
        {"success": False, "error": "...", "detail": "..."}
    """
    clean_sha = sha.strip() if sha else ""
    if not clean_sha:
        return {
            "success": False,
            "error": "Validation error",
            "detail": "Commit SHA must not be empty.",
        }

    clean_name = name.strip() if name else ""
    if not clean_name:
        return {
            "success": False,
            "error": "Validation error",
            "detail": "Check run name must not be empty.",
        }

    if status not in VALID_STATUSES:
        return {
            "success": False,
            "error": "Validation error",
            "detail": f"Status '{status}' is invalid. Must be one of: {sorted(VALID_STATUSES)}",
        }

    if status == "completed" and conclusion not in VALID_CONCLUSIONS:
        return {
            "success": False,
            "error": "Validation error",
            "detail": f"Conclusion '{conclusion}' is invalid. Must be one of: {sorted(VALID_CONCLUSIONS)}",
        }

    # Validate annotations
    clean_annotations: List[Dict[str, Any]] = []
    if annotations:
        for ann in annotations:
            level = ann.get("annotation_level", "notice").lower()
            if level not in VALID_ANNOTATION_LEVELS:
                level = "notice"

            path = str(ann.get("path", "")).strip().replace("\\", "/")
            start_line = int(ann.get("start_line", 1))
            end_line = int(ann.get("end_line", start_line))
            msg = str(ann.get("message", "")).strip()

            clean_annotations.append(
                {
                    "path": path,
                    "start_line": start_line,
                    "end_line": end_line,
                    "annotation_level": level,
                    "message": msg,
                    "title": ann.get("title", clean_name),
                }
            )

    try:
        repository = resolve_repository(repo)

        # Batch annotations in chunks of 50 (GitHub API limit)
        batches = [
            clean_annotations[i : i + MAX_CHECK_RUN_ANNOTATIONS]
            for i in range(0, len(clean_annotations), MAX_CHECK_RUN_ANNOTATIONS)
        ]

        summary_text = (
            f"Review completed with {len(clean_annotations)} finding(s)."
            if clean_annotations
            else "No issues identified."
        )

        first_batch = batches[0] if batches else []
        output = {
            "title": clean_name,
            "summary": summary_text,
            "annotations": first_batch,
        }

        # Create check run with first batch
        check_run = repository.create_check_run(
            name=clean_name,
            head_sha=clean_sha,
            status=status,
            conclusion=conclusion,
            output=output,
        )

        # Update remaining batches if more than 50 annotations
        for next_batch in batches[1:]:
            check_run.edit(
                output={
                    "title": clean_name,
                    "summary": summary_text,
                    "annotations": next_batch,
                }
            )

        return {
            "success": True,
            "check_run_id": check_run.id,
            "url": check_run.html_url,
        }

    except Exception as exc:
        logger.error("Failed to create Check Run for SHA %s: %s", clean_sha[:7], exc)
        return {
            "success": False,
            "error": "GitHub Check Run creation failed",
            "detail": _sanitize_error(exc),
        }

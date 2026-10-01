"""
git_blame.py
============
LangChain tool that runs ``git blame`` for a specified line range in a
repository file and returns structured authorship information.

Security model
--------------
* File paths are always resolved relative to REPO_ROOT and verified to stay
  inside it — path traversal is prevented.
* Only ``git blame`` is ever executed; the LLM cannot inject other git
  sub-commands or shell operators.
* The command is run as a list (not a shell string).
"""

from __future__ import annotations

import json
import os
import re
import subprocess
from pathlib import Path
from typing import List

from langchain_core.tools import tool

GIT_TIMEOUT = 30  # seconds


def _get_repo_root() -> Path | None:
    root = os.getenv("REPO_ROOT")
    return Path(root).resolve() if root else None


def _safe_resolve(repo_root: Path, relative_path: str) -> Path | None:
    """
    Resolve *relative_path* against *repo_root* and verify it stays
    inside the root.  Returns None if the path escapes the root.
    """
    try:
        resolved = (repo_root / relative_path).resolve()
        resolved.relative_to(repo_root)
        return resolved
    except (ValueError, OSError):
        return None


# ── Blame-line parser ────────────────────────────────────────────────────────

# git blame --porcelain emits one header block per unique commit, then
# a tab-prefixed source line.  We use a simpler format:
# git blame -L <start>,<end> --line-porcelain <file>
#
# Each block looks like:
#   <commit-hash> <orig-line> <final-line> [<count>]
#   author <name>
#   author-time <unix-timestamp>
#   ...
#   \t<source line>

_COMMIT_RE = re.compile(r"^([0-9a-f]{40}) \d+ (\d+)")
_AUTHOR_RE = re.compile(r"^author (.+)")
_DATE_RE = re.compile(r"^author-time (\d+)")
_SOURCE_RE = re.compile(r"^\t(.*)$")


def _parse_porcelain(output: str) -> List[dict]:
    """Parse ``git blame --line-porcelain`` output into a list of blame records."""
    records: List[dict] = []
    current: dict = {}

    for raw_line in output.splitlines():
        m = _COMMIT_RE.match(raw_line)
        if m:
            current = {
                "commit": m.group(1)[:7],  # short hash
                "line": int(m.group(2)),
            }
            continue

        m = _AUTHOR_RE.match(raw_line)
        if m:
            current["author"] = m.group(1)
            continue

        m = _DATE_RE.match(raw_line)
        if m:
            import datetime

            ts = int(m.group(1))
            current["date"] = datetime.datetime.utcfromtimestamp(ts).strftime("%Y-%m-%d")
            continue

        m = _SOURCE_RE.match(raw_line)
        if m:
            current["content"] = m.group(1)
            records.append(dict(current))
            current = {}

    return records


@tool
def git_blame(file: str, start_line: int, end_line: int) -> str:
    """
    Run ``git blame`` for a line range in a repository file and return
    per-line authorship information.

    Use this tool to understand *who* introduced a specific piece of code
    and *when*, which is useful for understanding the context of a finding.

    Args:
        file: Repository-relative path to the file, e.g. ``"src/auth.py"``.
              Must not start with ``..`` or ``/``.
        start_line: First line of the range to blame (1-based, inclusive).
        end_line: Last line of the range to blame (1-based, inclusive).
                  Must be >= *start_line*.

    Returns:
        A JSON string with the following keys:

        * ``success`` (bool): Whether git blame ran successfully.
        * ``file`` (str): The repository-relative file path.
        * ``start_line`` (int): Start of the blamed range.
        * ``end_line`` (int): End of the blamed range.
        * ``blame`` (list): Each item contains:

          - ``line`` (int): Line number in the file.
          - ``commit`` (str): Short commit hash.
          - ``author`` (str): Commit author name.
          - ``date`` (str): Commit date in ``YYYY-MM-DD`` format.
          - ``content`` (str): Source code on that line.

        * ``error`` (str): Present only when ``success`` is ``false``.

    Example::

        git_blame("src/auth.py", 10, 15)
        # → {"success": true, "file": "src/auth.py", "start_line": 10,
        #     "end_line": 15,
        #     "blame": [{"line": 10, "commit": "a13f82c",
        #                "author": "Alice", "date": "2026-09-01",
        #                "content": "def login(user, pwd):"}]}
    """
    # ── Validate repo root ───────────────────────────────────────────────
    repo_root = _get_repo_root()
    if repo_root is None:
        return json.dumps(
            {
                "success": False,
                "file": file,
                "error": (
                    "REPO_ROOT environment variable is not set. "
                    "Configure it to point to the repository root."
                ),
            }
        )

    # ── Validate line range ──────────────────────────────────────────────
    try:
        start = int(start_line)
        end = int(end_line)
    except (TypeError, ValueError):
        return json.dumps(
            {
                "success": False,
                "file": file,
                "error": "start_line and end_line must be integers.",
            }
        )

    if start < 1:
        return json.dumps(
            {
                "success": False,
                "file": file,
                "error": "start_line must be >= 1.",
            }
        )

    if end < start:
        return json.dumps(
            {
                "success": False,
                "file": file,
                "error": f"end_line ({end}) must be >= start_line ({start}).",
            }
        )

    MAX_RANGE = 500
    if (end - start) > MAX_RANGE:
        return json.dumps(
            {
                "success": False,
                "file": file,
                "error": (
                    f"Requested range ({end - start + 1} lines) exceeds the "
                    f"maximum of {MAX_RANGE} lines. Use a narrower range."
                ),
            }
        )

    # ── Sanitise file path ───────────────────────────────────────────────
    clean_file = file.lstrip("/").lstrip("\\")
    if not clean_file:
        return json.dumps(
            {"success": False, "file": file, "error": "File path must not be empty."}
        )

    resolved = _safe_resolve(repo_root, clean_file)
    if resolved is None:
        return json.dumps(
            {
                "success": False,
                "file": file,
                "error": "Path traversal detected — access denied.",
            }
        )

    if not resolved.exists():
        return json.dumps(
            {
                "success": False,
                "file": file,
                "error": f"File not found: '{clean_file}'",
            }
        )

    # ── Run git blame ────────────────────────────────────────────────────
    cmd = [
        "git",
        "blame",
        f"-L{start},{end}",
        "--line-porcelain",
        "--",
        clean_file,
    ]

    try:
        proc = subprocess.run(
            cmd,
            cwd=str(repo_root),
            capture_output=True,
            text=True,
            timeout=GIT_TIMEOUT,
        )
    except subprocess.TimeoutExpired:
        return json.dumps(
            {
                "success": False,
                "file": file,
                "error": f"git blame timed out after {GIT_TIMEOUT} seconds.",
            }
        )
    except FileNotFoundError:
        return json.dumps(
            {
                "success": False,
                "file": file,
                "error": "git executable not found. Ensure git is installed and on PATH.",
            }
        )
    except OSError as exc:
        return json.dumps(
            {
                "success": False,
                "file": file,
                "error": f"Failed to run git blame: {exc}",
            }
        )

    if proc.returncode != 0:
        err_msg = (proc.stderr or "").strip() or "git blame returned a non-zero exit code."
        return json.dumps(
            {
                "success": False,
                "file": file,
                "error": err_msg,
            }
        )

    # ── Parse and return ─────────────────────────────────────────────────
    blame_records = _parse_porcelain(proc.stdout)

    return json.dumps(
        {
            "success": True,
            "file": clean_file,
            "start_line": start,
            "end_line": end,
            "blame": blame_records,
        }
    )

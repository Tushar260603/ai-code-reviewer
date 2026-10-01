"""
search_codebase.py
==================
LangChain tool that searches the repository for a text pattern, returning
matching file paths and line numbers.

Design choices
--------------
* Pure-Python ``re`` search — no external ``grep`` / ``ripgrep`` binary required.
* Binary files are skipped automatically.
* Common non-source directories are excluded from traversal.
* Match count is capped at MAX_MATCHES (default 100) to keep responses compact.
"""

from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import List

from langchain_core.tools import tool

# Directories that are never traversed
IGNORED_DIRS: frozenset[str] = frozenset(
    {
        ".git",
        ".hg",
        ".svn",
        "node_modules",
        "venv",
        ".venv",
        "env",
        ".env",
        "__pycache__",
        "dist",
        "build",
        ".mypy_cache",
        ".pytest_cache",
        ".ruff_cache",
        "coverage",
        ".next",
        ".nuxt",
        "target",       # Rust/Maven build output
        "vendor",       # Go vendor directory
    }
)

MAX_MATCHES = 100


def _get_repo_root() -> Path | None:
    root = os.getenv("REPO_ROOT")
    return Path(root).resolve() if root else None


def _is_binary(file_path: Path, sample_bytes: int = 8192) -> bool:
    """Return True if the file looks like a binary (non-text) file."""
    try:
        chunk = file_path.read_bytes()[:sample_bytes]
        # A file is considered binary if it contains a null byte
        return b"\x00" in chunk
    except OSError:
        return True


def _iter_text_files(root: Path):
    """Yield all non-binary, non-ignored text files under *root*."""
    for dirpath, dirnames, filenames in os.walk(root):
        # Prune ignored directories in-place so os.walk skips them
        dirnames[:] = [d for d in dirnames if d not in IGNORED_DIRS]
        for filename in filenames:
            file_path = Path(dirpath) / filename
            if not _is_binary(file_path):
                yield file_path


@tool
def search_codebase(pattern: str, max_matches: int = MAX_MATCHES) -> str:
    """
    Search the entire repository for lines matching a text pattern.

    Useful for finding usages of a function, class, variable, or any symbol
    across all source files.  Common build/dependency directories are
    automatically excluded.

    Args:
        pattern: A plain-text substring or Python regular expression to search
                 for.  The search is case-sensitive by default.
        max_matches: Maximum number of matches to return (default 100).
                     Increase only if you need more results; large values slow
                     down the search.

    Returns:
        A JSON string with the following keys:

        * ``success`` (bool): Whether the search completed without errors.
        * ``pattern`` (str): The pattern that was searched.
        * ``matches`` (list): Each item has ``file``, ``line``, ``content``.
        * ``total_matches`` (int): Number of matches returned (capped at
          *max_matches*).
        * ``truncated`` (bool): True if results were capped.
        * ``error`` (str): Present only when ``success`` is ``false``.

    Example::

        search_codebase("def get_user")
        # → {"success": true, "pattern": "def get_user",
        #     "matches": [{"file": "src/user.py", "line": 10,
        #                  "content": "def get_user(id):"}],
        #     "total_matches": 1, "truncated": false}
    """
    # ── Validate repo root ──────────────────────────────────────────────
    repo_root = _get_repo_root()
    if repo_root is None:
        return json.dumps(
            {
                "success": False,
                "pattern": pattern,
                "error": (
                    "REPO_ROOT environment variable is not set. "
                    "Configure it to point to the repository root."
                ),
            }
        )

    if not repo_root.is_dir():
        return json.dumps(
            {
                "success": False,
                "pattern": pattern,
                "error": f"REPO_ROOT '{repo_root}' does not exist or is not a directory.",
            }
        )

    # ── Validate pattern ────────────────────────────────────────────────
    if not pattern or not pattern.strip():
        return json.dumps(
            {"success": False, "pattern": pattern, "error": "Pattern must not be empty."}
        )

    try:
        regex = re.compile(pattern)
    except re.error as exc:
        return json.dumps(
            {
                "success": False,
                "pattern": pattern,
                "error": f"Invalid regular expression: {exc}",
            }
        )

    cap = max(1, min(int(max_matches), 500))  # hard cap at 500

    # ── Search ──────────────────────────────────────────────────────────
    matches: List[dict] = []
    truncated = False

    try:
        for file_path in _iter_text_files(repo_root):
            if len(matches) >= cap:
                truncated = True
                break

            try:
                text = file_path.read_text(encoding="utf-8", errors="replace")
            except OSError:
                continue

            for line_no, line in enumerate(text.splitlines(), start=1):
                if len(matches) >= cap:
                    truncated = True
                    break
                if regex.search(line):
                    rel_path = str(file_path.relative_to(repo_root)).replace("\\", "/")
                    matches.append(
                        {
                            "file": rel_path,
                            "line": line_no,
                            "content": line.rstrip(),
                        }
                    )
    except Exception as exc:  # noqa: BLE001
        return json.dumps(
            {
                "success": False,
                "pattern": pattern,
                "error": f"Search error: {exc}",
            }
        )

    return json.dumps(
        {
            "success": True,
            "pattern": pattern,
            "matches": matches,
            "total_matches": len(matches),
            "truncated": truncated,
        }
    )

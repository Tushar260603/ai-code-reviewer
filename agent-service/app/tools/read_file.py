"""
read_file.py
============
LangChain tool that reads a file from the configured repository root,
returning its contents with line numbers prepended.

Security
--------
* All paths are resolved relative to REPO_ROOT (from env) and checked
  against it to prevent directory traversal attacks.
* If REPO_ROOT is not set the tool returns an error instead of falling
  back to an arbitrary working directory.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

from langchain_core.tools import tool


def _get_repo_root() -> Path | None:
    """Return the configured repository root, or None if not set."""
    root = os.getenv("REPO_ROOT")
    return Path(root).resolve() if root else None


def _safe_resolve(repo_root: Path, relative_path: str) -> Path | None:
    """
    Resolve *relative_path* against *repo_root* and verify it stays
    inside the root.  Returns None if the path would escape the root.
    """
    try:
        resolved = (repo_root / relative_path).resolve()
        resolved.relative_to(repo_root)  # raises ValueError if outside
        return resolved
    except (ValueError, OSError):
        return None


@tool
def read_file(path: str) -> str:
    """
    Read a file from the repository and return its contents with line numbers.

    Use this tool to inspect source files, configuration files, or any
    text-based file in the repository being reviewed.

    Args:
        path: Repository-relative path to the file, e.g. ``"src/main.py"``
              or ``"package.json"``.  Must not start with ``..`` or ``/``.

    Returns:
        A JSON string with the following keys:

        * ``success`` (bool): Whether the read succeeded.
        * ``path`` (str): The repository-relative path that was read.
        * ``content`` (str): File contents with ``"<n>: "`` line prefixes.
        * ``total_lines`` (int): Total number of lines in the file.
        * ``error`` (str): Present only when ``success`` is ``false``.

    Example::

        read_file("src/services/user.py")
        # → {"success": true, "path": "src/services/user.py",
        #     "content": "1: def get_user(id):...", "total_lines": 25}
    """
    # ── Validate repo root ──────────────────────────────────────────────
    repo_root = _get_repo_root()
    if repo_root is None:
        return json.dumps(
            {
                "success": False,
                "path": path,
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
                "path": path,
                "error": f"REPO_ROOT '{repo_root}' does not exist or is not a directory.",
            }
        )

    # ── Sanitise the requested path ─────────────────────────────────────
    # Strip leading slashes/dots so the path is always relative
    clean_path = path.lstrip("/").lstrip("\\")
    if not clean_path:
        return json.dumps(
            {"success": False, "path": path, "error": "Path must not be empty."}
        )

    resolved = _safe_resolve(repo_root, clean_path)
    if resolved is None:
        return json.dumps(
            {
                "success": False,
                "path": path,
                "error": "Path traversal detected — access denied.",
            }
        )

    # ── Read the file ────────────────────────────────────────────────────
    if not resolved.exists():
        return json.dumps(
            {
                "success": False,
                "path": path,
                "error": f"File not found: '{clean_path}'",
            }
        )

    if not resolved.is_file():
        return json.dumps(
            {
                "success": False,
                "path": path,
                "error": f"'{clean_path}' is a directory, not a file.",
            }
        )

    try:
        raw = resolved.read_text(encoding="utf-8", errors="replace")
    except OSError as exc:
        return json.dumps(
            {
                "success": False,
                "path": path,
                "error": f"Could not read file: {exc}",
            }
        )

    lines = raw.splitlines()
    numbered = "\n".join(f"{i + 1}: {line}" for i, line in enumerate(lines))

    # Cap content at ~100 KB to keep tool responses manageable
    MAX_CHARS = 100_000
    truncated = False
    if len(numbered) > MAX_CHARS:
        numbered = numbered[:MAX_CHARS]
        truncated = True

    result: dict = {
        "success": True,
        "path": clean_path,
        "content": numbered,
        "total_lines": len(lines),
    }
    if truncated:
        result["warning"] = (
            f"Content was truncated at {MAX_CHARS} characters. "
            "Use start_line/end_line parameters or search for specific symbols."
        )

    return json.dumps(result)

"""
run_tests.py
============
LangChain tool that auto-detects the project's test framework (pytest or
Jest) and runs the test suite, returning a concise pass/fail summary.

Security model
--------------
* ONLY whitelisted, hard-coded commands are ever executed — the LLM cannot
  inject arbitrary shell commands.
* Commands are run as a list (not a shell string) so shell-injection is
  structurally impossible.
* A configurable timeout (default 120 s) prevents runaway test processes.
* The tool operates inside REPO_ROOT; it never ``cd`` to paths supplied by
  the model.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
from pathlib import Path

from langchain_core.tools import tool

# Maximum output characters returned to the LLM
MAX_OUTPUT_CHARS = 8_000
# Default subprocess timeout in seconds
DEFAULT_TIMEOUT = 120


def _get_repo_root() -> Path | None:
    root = os.getenv("REPO_ROOT")
    return Path(root).resolve() if root else None


# ── Framework detection helpers ──────────────────────────────────────────────


def _has_pytest(root: Path) -> bool:
    """Return True if the repo looks like a pytest project."""
    # Check config files
    for cfg in ("pytest.ini", "setup.cfg", "pyproject.toml", "tox.ini"):
        cfg_path = root / cfg
        if cfg_path.exists():
            try:
                text = cfg_path.read_text(encoding="utf-8", errors="replace")
                if "pytest" in text or "[tool.pytest" in text:
                    return True
            except OSError:
                pass

    # Check for test files
    for pattern in ("test_*.py", "*_test.py"):
        if any(root.rglob(pattern)):
            return True

    return False


def _has_jest(root: Path) -> bool:
    """Return True if the repo looks like a Jest project."""
    pkg = root / "package.json"
    if pkg.exists():
        try:
            text = pkg.read_text(encoding="utf-8", errors="replace")
            if "jest" in text.lower():
                return True
        except OSError:
            pass

    # Explicit jest config files
    for cfg in ("jest.config.js", "jest.config.ts", "jest.config.mjs", "jest.config.cjs"):
        if (root / cfg).exists():
            return True

    # Test files in JS/TS
    for pattern in ("*.test.js", "*.test.ts", "*.spec.js", "*.spec.ts"):
        if any(root.rglob(pattern)):
            return True

    return False


def _detect_framework(root: Path) -> str | None:
    """Return 'pytest', 'jest', or None."""
    if _has_pytest(root):
        return "pytest"
    if _has_jest(root):
        return "jest"
    return None


# ── Command definitions (whitelisted — never derived from LLM input) ─────────

_FRAMEWORK_COMMANDS: dict[str, list[str]] = {
    "pytest": ["pytest", "--tb=short", "-q"],
    "jest": ["npm", "test", "--", "--runInBand", "--forceExit"],
}

_FRAMEWORK_COMMAND_DISPLAY: dict[str, str] = {
    "pytest": "pytest --tb=short -q",
    "jest": "npm test -- --runInBand --forceExit",
}


# ── Result parsing ────────────────────────────────────────────────────────────


def _parse_pytest_summary(output: str) -> tuple[str, str]:
    """Return (status, summary) for a pytest run."""
    # Match the short summary line produced by pytest, e.g.:
    #   "5 passed in 1.23s"
    #   "2 failed, 3 passed in 0.8s"
    #   "1 error in 0.1s"
    match = re.search(
        r"((?:\d+ \w+(?:, )?)+in \d[\d.]*s)",
        output,
    )
    if match:
        summary = match.group(1).strip()
        status = "failed" if ("failed" in summary or "error" in summary) else "passed"
        return status, summary

    # Fallback: scan the whole output for keywords
    if "failed" in output or "error" in output:
        return "failed", "Some tests failed"
    if "passed" in output:
        return "passed", "All tests passed"
    if "no tests ran" in output.lower():
        return "no_tests", "No tests were collected"
    return "unknown", "Could not parse test summary"


def _parse_jest_summary(output: str) -> tuple[str, str]:
    """Return (status, summary) for a Jest run."""
    # Jest summary lines look like:
    # "Tests: 2 failed, 18 passed, 20 total"
    match = re.search(r"Tests:\s+(.+)", output)
    if match:
        summary = match.group(1).strip()
        status = "failed" if "failed" in summary else "passed"
        return status, summary

    if "PASS" in output and "FAIL" not in output:
        return "passed", "All test suites passed"
    if "FAIL" in output:
        return "failed", "Some test suites failed"
    return "unknown", "Could not parse test summary"


@tool
def run_tests(timeout: int = DEFAULT_TIMEOUT) -> str:
    """
    Auto-detect the test framework and run the project's test suite.

    Supports **pytest** (Python) and **Jest** (JavaScript/TypeScript).
    The framework is detected by inspecting project configuration files and
    the presence of test files — no framework name needs to be supplied by the
    caller.

    Args:
        timeout: Maximum seconds to wait for the test process (default 120).
                 Increase for large test suites; decrease for quick checks.

    Returns:
        A JSON string with the following keys:

        * ``success`` (bool): Whether the tool executed without an internal error.
        * ``framework`` (str): Detected framework (``"pytest"`` or ``"jest"``).
        * ``command`` (str): The exact command that was executed.
        * ``status`` (str): ``"passed"``, ``"failed"``, ``"timeout"``,
          ``"no_tests"``, or ``"unknown"``.
        * ``summary`` (str): Short human-readable summary of results.
        * ``output`` (str): Captured stdout + stderr (truncated if very long).
        * ``exit_code`` (int): Process exit code.
        * ``error`` (str): Present only when ``success`` is ``false``.

    Example::

        run_tests()
        # → {"success": true, "framework": "pytest", "command": "pytest ...",
        #     "status": "passed", "summary": "42 passed in 3.14s", ...}
    """
    # ── Resolve repo root ────────────────────────────────────────────────
    repo_root = _get_repo_root()
    if repo_root is None:
        return json.dumps(
            {
                "success": False,
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
                "error": f"REPO_ROOT '{repo_root}' does not exist or is not a directory.",
            }
        )

    # ── Detect framework ─────────────────────────────────────────────────
    framework = _detect_framework(repo_root)
    if framework is None:
        return json.dumps(
            {
                "success": False,
                "error": (
                    "No supported test framework detected. "
                    "Ensure the repository contains pytest or Jest configuration/test files."
                ),
            }
        )

    cmd = _FRAMEWORK_COMMANDS[framework]
    cmd_display = _FRAMEWORK_COMMAND_DISPLAY[framework]
    capped_timeout = max(10, min(int(timeout), 600))  # 10 s – 10 min

    # ── Run tests (whitelisted command only) ─────────────────────────────
    try:
        proc = subprocess.run(
            cmd,
            cwd=str(repo_root),
            capture_output=True,
            text=True,
            timeout=capped_timeout,
            env={**os.environ, "CI": "true"},  # suppress interactive prompts
        )
    except subprocess.TimeoutExpired:
        return json.dumps(
            {
                "success": True,
                "framework": framework,
                "command": cmd_display,
                "status": "timeout",
                "summary": f"Tests timed out after {capped_timeout} seconds.",
                "output": "",
                "exit_code": -1,
            }
        )
    except FileNotFoundError:
        return json.dumps(
            {
                "success": False,
                "framework": framework,
                "command": cmd_display,
                "error": (
                    f"Command not found: '{cmd[0]}'. "
                    "Ensure the test runner is installed and on PATH."
                ),
            }
        )
    except OSError as exc:
        return json.dumps(
            {
                "success": False,
                "framework": framework,
                "command": cmd_display,
                "error": f"Failed to launch test process: {exc}",
            }
        )

    # ── Parse output ─────────────────────────────────────────────────────
    raw_output = (proc.stdout or "") + (proc.stderr or "")

    if framework == "pytest":
        status, summary = _parse_pytest_summary(raw_output)
    else:
        status, summary = _parse_jest_summary(raw_output)

    # Truncate output so tool responses stay reasonable
    if len(raw_output) > MAX_OUTPUT_CHARS:
        raw_output = raw_output[-MAX_OUTPUT_CHARS:]  # keep the end (summary is there)
        raw_output = "[...truncated...]\n" + raw_output

    return json.dumps(
        {
            "success": True,
            "framework": framework,
            "command": cmd_display,
            "status": status,
            "summary": summary,
            "output": raw_output,
            "exit_code": proc.returncode,
        }
    )

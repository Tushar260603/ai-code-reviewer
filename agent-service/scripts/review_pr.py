"""
agent-service/scripts/review_pr.py
===================================
GitHub Actions CLI entrypoint for the local (Option B) AI code review mode.

Execution flow
--------------
1. Read PR metadata from $GITHUB_EVENT_PATH (provided by GitHub Actions runner).
2. Fetch the pull request diff text via PyGitHub (uses GITHUB_TOKEN).
3. Run the existing ReviewSupervisor → SecurityAgent + StyleAgent + LogicAgent (Gemini).
4. Write structured output to review-result.json.
5. Build a Markdown summary and write it to review-summary.md.
6. Post a PR summary comment using the gh CLI.
7. Create a GitHub Check Run with per-finding annotations via PyGitHub (comment_poster.py).

Environment variables (set by the GitHub Actions workflow)
----------------------------------------------------------
  GEMINI_API_KEY        Google Gemini API key (required)
  GEMINI_MODEL          Optional model override (e.g. gemini-2.0-flash-exp)
  GITHUB_TOKEN          GitHub token provided by github.token (read PR diff, create check run)
  GH_TOKEN              Same token, used by gh CLI for comment posting
  GITHUB_REPOSITORY     owner/repository string
  PR_NUMBER             Pull request number (integer)
  PR_HEAD_SHA           Head commit SHA
  GITHUB_RUN_ID         Actions run ID (used for deduplication)
  GITHUB_RUN_ATTEMPT    Actions run attempt number

This script intentionally does not duplicate or alter SecurityAgent, StyleAgent,
LogicAgent, ReviewSupervisor, or comment_poster — it only orchestrates them.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

# ── Bootstrap: make agent-service package importable from the repo root ──────
REPO_ROOT = Path(__file__).resolve().parents[2]
AGENT_SERVICE_ROOT = REPO_ROOT / "agent-service"
sys.path.insert(0, str(AGENT_SERVICE_ROOT))

# ── Standard library imports only before this point ─────────────────────────
# Project imports (require installed dependencies)
from dotenv import load_dotenv  # noqa: E402

load_dotenv(AGENT_SERVICE_ROOT / ".env", override=False)

from github import Github, Auth  # noqa: E402
from app.agents.base_agent import Finding, ReviewResult  # noqa: E402
from app.agents.supervisor import ReviewSupervisor  # noqa: E402
from app.github.comment_poster import create_check_run, post_summary_comment  # noqa: E402

# ── Logging ───────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%dT%H:%M:%S",
)
logger = logging.getLogger("review_pr")


# ---------------------------------------------------------------------------
# Environment helpers
# ---------------------------------------------------------------------------

def require_env(name: str) -> str:
    """Return the value of a required environment variable or exit with error."""
    value = os.environ.get(name, "").strip()
    if not value:
        logger.error(
            "Required environment variable %s is not set. "
            "Ensure it is configured in the GitHub Actions workflow.",
            name,
        )
        sys.exit(1)
    return value


def optional_env(name: str, default: str = "") -> str:
    """Return the value of an optional environment variable."""
    return os.environ.get(name, default).strip() or default


# ---------------------------------------------------------------------------
# PR metadata extraction
# ---------------------------------------------------------------------------

def load_github_event() -> Dict[str, Any]:
    """Load and parse the GitHub Actions event payload."""
    event_path = os.environ.get("GITHUB_EVENT_PATH", "")
    if not event_path or not Path(event_path).exists():
        # Fallback: construct minimal event from explicit env vars
        logger.warning(
            "GITHUB_EVENT_PATH not found; building minimal event from environment variables."
        )
        return {
            "action": "opened",
            "pull_request": {
                "number": int(require_env("PR_NUMBER")),
                "head": {"sha": require_env("PR_HEAD_SHA")},
                "base": {"sha": ""},
                "title": "",
                "html_url": "",
                "diff_url": "",
            },
            "repository": {
                "full_name": require_env("GITHUB_REPOSITORY"),
            },
            "sender": {"login": ""},
        }

    with open(event_path, "r", encoding="utf-8") as f:
        event = json.load(f)

    return event


def extract_pr_metadata(event: Dict[str, Any]) -> Dict[str, Any]:
    """Extract the fields the reviewer needs from the GitHub event payload."""
    pr = event.get("pull_request", {})
    repo = event.get("repository", {})

    pr_number_raw = pr.get("number") or os.environ.get("PR_NUMBER")
    head_sha_raw = (pr.get("head") or {}).get("sha") or os.environ.get("PR_HEAD_SHA")

    if not pr_number_raw:
        logger.error("Could not determine PR number from event payload or environment.")
        sys.exit(1)
    if not head_sha_raw:
        logger.error("Could not determine head SHA from event payload or environment.")
        sys.exit(1)

    return {
        "pr_number": int(pr_number_raw),
        "head_sha": str(head_sha_raw).strip(),
        "base_sha": (pr.get("base") or {}).get("sha", ""),
        "title": pr.get("title", ""),
        "html_url": pr.get("html_url", ""),
        "repo_full_name": repo.get("full_name") or require_env("GITHUB_REPOSITORY"),
        "author": (event.get("sender") or {}).get("login", ""),
        "action": event.get("action", "opened"),
    }


# ---------------------------------------------------------------------------
# Diff fetching via PyGitHub
# ---------------------------------------------------------------------------

def fetch_pr_diff(repo_full_name: str, pr_number: int, token: str) -> str:
    """
    Fetch the unified diff text for a pull request using PyGitHub.

    Falls back to an empty string with a warning if diff retrieval fails.
    The review proceeds with limited context rather than aborting.
    """
    try:
        g = Github(auth=Auth.Token(token))
        repo = g.get_repo(repo_full_name)
        pull = repo.get_pull(pr_number)

        # PyGitHub exposes diff via the diff_url / raw diff headers
        import urllib.request
        req = urllib.request.Request(
            pull.diff_url,
            headers={
                "Authorization": f"token {token}",
                "Accept": "application/vnd.github.v3.diff",
            },
        )
        with urllib.request.urlopen(req) as resp:
            diff_text = resp.read().decode("utf-8", errors="replace")

        if not diff_text.strip():
            logger.warning("PR #%d diff is empty.", pr_number)

        return diff_text

    except Exception as exc:
        logger.warning(
            "Could not fetch diff for PR #%d (%s): %s — proceeding without diff.",
            pr_number,
            repo_full_name,
            exc,
        )
        return ""


# ---------------------------------------------------------------------------
# Verdict → Check Run conclusion mapping
# ---------------------------------------------------------------------------

VERDICT_TO_CONCLUSION = {
    "approve": "success",
    "comment": "neutral",
    "request_changes": "failure",
}


def verdict_to_conclusion(verdict: str) -> str:
    """Map reviewer verdict to a GitHub Check Run conclusion string."""
    return VERDICT_TO_CONCLUSION.get(verdict.lower(), "neutral")


# ---------------------------------------------------------------------------
# Severity → annotation level mapping
# ---------------------------------------------------------------------------

def severity_to_annotation_level(severity: str) -> str:
    """Map finding severity to a GitHub annotation level."""
    sev = severity.lower()
    if sev in ("critical", "high"):
        return "failure"
    if sev == "medium":
        return "warning"
    return "notice"


# ---------------------------------------------------------------------------
# Markdown review summary builder
# ---------------------------------------------------------------------------

def build_review_summary_markdown(
    result: ReviewResult,
    meta: Dict[str, Any],
) -> str:
    """
    Build a clean Markdown PR comment summarising the AI review.
    Groups findings by agent category: Security, Style, Logic.
    Does not include raw AI prompts or confidential tool output.
    """
    verdict = result.verdict
    findings = result.findings or []
    summary = getattr(result, "summary", None) or ""

    # Count by agent category
    by_category: Dict[str, List[Finding]] = {"security": [], "style": [], "logic": []}
    other: List[Finding] = []
    for f in findings:
        cat = str(getattr(f, "category", "") or "").lower()
        if cat in by_category:
            by_category[cat].append(f)
        else:
            other.append(f)

    total = len(findings)

    # Verdict badge
    verdict_badges = {
        "approve": "✅ **Approved**",
        "comment": "💬 **Commented**",
        "request_changes": "🔴 **Changes Requested**",
    }
    verdict_label = verdict_badges.get(verdict.lower(), f"**{verdict}**")

    lines: List[str] = [
        "## 🤖 AI Code Review",
        "",
        f"**Verdict:** {verdict_label}",
        "",
    ]

    if summary:
        lines += [f"> {summary}", ""]

    lines += [
        f"**Total findings:** {total} "
        f"(Security: {len(by_category['security'])}, "
        f"Style: {len(by_category['style'])}, "
        f"Logic: {len(by_category['logic'])})",
        "",
    ]

    # Per-category sections — only rendered if there are findings in that category
    for cat_key, cat_label, emoji in [
        ("security", "Security", "🔐"),
        ("style", "Style", "✏️"),
        ("logic", "Logic", "🧠"),
    ]:
        cat_findings = by_category[cat_key]
        if not cat_findings:
            continue

        lines += [
            f"### {emoji} {cat_label} Findings ({len(cat_findings)})",
            "",
        ]

        for finding in cat_findings:
            sev = (finding.severity or "").upper()
            msg = finding.message or ""
            file_ref = f"`{finding.file}:{finding.line}`" if finding.file else ""
            lines += [
                f"- **[{sev}]** {msg}  ",
                f"  {file_ref}",
                "",
            ]

    # Other/uncategorised findings
    if other:
        lines += ["### Other Findings", ""]
        for finding in other:
            sev = (finding.severity or "").upper()
            msg = finding.message or ""
            file_ref = f"`{finding.file}:{finding.line}`" if finding.file else ""
            lines += [f"- **[{sev}]** {msg}  ", f"  {file_ref}", ""]

    if total == 0:
        lines += [
            "_No issues found. The code passed all security, style, and logic checks._",
            "",
        ]

    lines += [
        "---",
        f"_Reviewed by AI Code Reviewer (run `{os.environ.get('GITHUB_RUN_ID', 'N/A')}`)_",
    ]

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Check Run annotation builder
# ---------------------------------------------------------------------------

def build_annotations(findings: List[Finding]) -> List[Dict[str, Any]]:
    """Build GitHub Check Run annotation dicts from a list of findings."""
    annotations: List[Dict[str, Any]] = []
    for finding in findings:
        if not finding.file or not finding.line:
            continue
        annotations.append(
            {
                "path": finding.file.replace("\\", "/"),
                "start_line": int(finding.line),
                "end_line": int(finding.line),
                "annotation_level": severity_to_annotation_level(finding.severity),
                "message": finding.message,
                "title": f"[{(finding.severity or 'info').upper()}] {(getattr(finding, 'category', '') or '').capitalize()}",
            }
        )
    return annotations


# ---------------------------------------------------------------------------
# Main entrypoint
# ---------------------------------------------------------------------------

async def main() -> None:
    logger.info("=== AI Code Reviewer — Local Mode ===")

    # ── 1. Collect environment config ────────────────────────────────────────
    github_token = require_env("GITHUB_TOKEN")
    gemini_api_key = require_env("GEMINI_API_KEY")  # noqa — used via os.environ
    gemini_model = optional_env("GEMINI_MODEL", "")

    # Ensure Gemini credentials are available for agent instantiation
    os.environ.setdefault("GEMINI_API_KEY", gemini_api_key)
    if gemini_model:
        os.environ.setdefault("GEMINI_MODEL", gemini_model)

    # ── 2. Load PR metadata from GitHub Actions event ────────────────────────
    event = load_github_event()
    meta = extract_pr_metadata(event)

    logger.info(
        "Reviewing PR #%d (%s) — head SHA %s",
        meta["pr_number"],
        meta["repo_full_name"],
        meta["head_sha"][:7],
    )

    # ── 3. Fetch unified diff ─────────────────────────────────────────────────
    logger.info("Fetching PR diff from GitHub...")
    diff_text = fetch_pr_diff(meta["repo_full_name"], meta["pr_number"], github_token)

    if not diff_text:
        logger.warning("Empty diff — review may have limited findings.")

    # ── 4. Run the existing multi-agent ReviewSupervisor ─────────────────────
    logger.info("Starting multi-agent review (Security + Style + Logic)...")
    model_name = gemini_model if gemini_model else None
    supervisor = ReviewSupervisor(model_name=model_name)

    result: ReviewResult = await supervisor.review(diff_text)

    logger.info(
        "Review complete — verdict: %s, findings: %d",
        result.verdict,
        len(result.findings or []),
    )

    # ── 5. Write structured review output ────────────────────────────────────
    output_dir = Path(os.environ.get("GITHUB_WORKSPACE", "."))
    result_path = output_dir / "review-result.json"
    result_data = {
        "verdict": result.verdict,
        "findings": [f.model_dump() for f in (result.findings or [])],
        "agent_breakdown": getattr(result, "agent_breakdown", {}),
        "errors": result.errors or [],
        "pr_number": meta["pr_number"],
        "repo": meta["repo_full_name"],
        "head_sha": meta["head_sha"],
        "run_id": os.environ.get("GITHUB_RUN_ID", ""),
    }

    result_path.write_text(json.dumps(result_data, indent=2), encoding="utf-8")
    logger.info("Review result written to: %s", result_path)

    # ── 6. Build and write Markdown summary ──────────────────────────────────
    summary_md = build_review_summary_markdown(result, meta)
    summary_path = output_dir / "review-summary.md"
    summary_path.write_text(summary_md, encoding="utf-8")
    logger.info("Review summary written to: %s", summary_path)

    # ── 7. Post PR summary comment using gh CLI ───────────────────────────────
    logger.info("Posting PR summary comment via gh CLI...")
    try:
        gh_result = subprocess.run(
            [
                "gh",
                "pr",
                "comment",
                str(meta["pr_number"]),
                "--body-file",
                str(summary_path),
                "--repo",
                meta["repo_full_name"],
            ],
            capture_output=True,
            text=True,
            timeout=60,
        )
        if gh_result.returncode == 0:
            logger.info("PR summary comment posted successfully.")
        else:
            logger.warning(
                "gh pr comment returned non-zero exit: %s — %s",
                gh_result.returncode,
                gh_result.stderr.strip(),
            )
    except FileNotFoundError:
        logger.warning("gh CLI not found. Falling back to PyGitHub for summary comment.")
        post_result = post_summary_comment(
            repo=meta["repo_full_name"],
            pr_number=meta["pr_number"],
            body=summary_md,
        )
        if post_result.get("success"):
            logger.info("Summary comment posted (comment_id=%s).", post_result.get("comment_id"))
        else:
            logger.error("Failed to post summary comment: %s", post_result.get("detail"))
    except subprocess.TimeoutExpired:
        logger.error("gh CLI timed out posting summary comment.")

    # ── 8. Create GitHub Check Run with per-finding annotations ──────────────
    logger.info("Creating GitHub Check Run...")
    conclusion = verdict_to_conclusion(result.verdict)
    annotations = build_annotations(result.findings or [])

    check_result = create_check_run(
        repo=meta["repo_full_name"],
        sha=meta["head_sha"],
        name="AI Code Review",
        status="completed",
        conclusion=conclusion,
        annotations=annotations,
    )

    if check_result.get("success"):
        logger.info(
            "Check Run created (id=%s, url=%s)",
            check_result.get("check_run_id"),
            check_result.get("url"),
        )
    else:
        logger.error(
            "Failed to create Check Run: %s — %s",
            check_result.get("error"),
            check_result.get("detail"),
        )

    # ── 9. Surface findings in workflow log for traceability ─────────────────
    finding_count = len(result.findings or [])
    if result.verdict == "request_changes":
        logger.warning(
            "Review verdict: %s (%d finding(s)). See PR comment for details.",
            result.verdict,
            finding_count,
        )
    else:
        logger.info(
            "Review verdict: %s (%d finding(s)).",
            result.verdict,
            finding_count,
        )

    logger.info("=== AI Code Reviewer — Complete ===")


if __name__ == "__main__":
    asyncio.run(main())

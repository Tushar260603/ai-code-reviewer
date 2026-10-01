"""
supervisor.py
=============
ReviewSupervisor coordinates multi-agent Pull Request reviews.

Workflow
--------
                         ReviewSupervisor.review(pr_diff)
                                        │
                               asyncio.gather(...)
                                        │
               ┌────────────────────────┼────────────────────────┐
               ▼                        ▼                        ▼
        SecurityAgent               StyleAgent               LogicAgent
        (vulns, auth,             (conventions,             (bugs, perf,
         injection)                 cleanliness)             tests, edges)
               │                        │                        │
               └────────────────────────┼────────────────────────┘
                                        ▼
                            Aggregate All Findings
                                        │
                                        ▼
                               Deduplicate Findings
                                        │
                                        ▼
                            Calculate PR Verdict
                      ('approve' / 'comment' / 'request_changes')
                                        │
                                        ▼
                                   ReviewResult
"""

from __future__ import annotations

import asyncio
from difflib import SequenceMatcher
import logging
import re
from typing import Dict, List, Literal, Optional, Set, TypedDict

from app.agents.base_agent import Finding, ReviewResult, VerdictType
from app.agents.logic_agent import LogicAgent
from app.agents.security_agent import SecurityAgent
from app.agents.style_agent import StyleAgent

logger = logging.getLogger(__name__)

# Severity hierarchy for ranking and deduplication tie-breaking
SEVERITY_WEIGHTS: Dict[str, int] = {
    "critical": 5,
    "high": 4,
    "medium": 3,
    "low": 2,
    "info": 1,
}


def _normalize_path(path: str) -> str:
    """Normalize file path for consistent cross-agent comparison."""
    clean = path.replace("\\", "/").strip().lstrip("./")
    return clean


def _normalize_tokens(text: str) -> Set[str]:
    """Extract lowercased alphanumeric word tokens from message text."""
    return set(re.findall(r"\b[a-zA-Z0-9_]{3,}\b", text.lower()))


def _message_similarity(msg1: str, msg2: str) -> float:
    """
    Calculate text similarity between two finding descriptions using
    token Jaccard index combined with character SequenceMatcher.
    """
    tokens1 = _normalize_tokens(msg1)
    tokens2 = _normalize_tokens(msg2)

    jaccard = 0.0
    if tokens1 or tokens2:
        jaccard = len(tokens1 & tokens2) / len(tokens1 | tokens2)

    seq_ratio = SequenceMatcher(None, msg1.lower(), msg2.lower()).ratio()
    return max(jaccard, seq_ratio)


def _are_findings_duplicates(f1: Finding, f2: Finding) -> bool:
    """
    Determine whether two findings refer to the same underlying issue.

    Conditions:
    1. Must target the exact same file (normalized).
    2. Must be on the exact same line, or within 1 adjacent line.
    3. If on the same line:
       - If they share similar keywords, or have similarity >= 0.25,
         or share related categories/keywords (e.g. injection, auth, validation),
         they are considered duplicate representations of the same flaw.
    4. If within 1 adjacent line:
       - Require higher similarity (>= 0.45) to avoid false merges.
    """
    if _normalize_path(f1.file) != _normalize_path(f2.file):
        return False

    line_diff = abs(f1.line - f2.line)
    if line_diff > 1:
        return False

    # Calculate message similarity
    sim = _message_similarity(f1.message, f2.message)

    # Common cross-category vulnerability & bug indicators
    security_logic_overlap_keywords = {
        "sql", "injection", "query", "sanitize", "input", "validation",
        "secret", "password", "token", "auth", "permission", "overflow",
        "boundary", "null", "none", "race", "traversal", "ssrf", "xss",
    }
    tokens1 = _normalize_tokens(f1.message)
    tokens2 = _normalize_tokens(f2.message)
    shared_keywords = (tokens1 & tokens2) & security_logic_overlap_keywords

    if line_diff == 0:
        # Same exact line
        if f1.category.lower() == f2.category.lower():
            return True
        if sim >= 0.25 or len(shared_keywords) >= 1:
            return True
    else:
        # Adjacent line (line_diff == 1)
        if sim >= 0.45 or len(shared_keywords) >= 2:
            return True

    return False


def _select_better_finding(f1: Finding, f2: Finding) -> Finding:
    """
    Choose the most useful and complete finding between two duplicates.

    Heuristics:
    1. Higher severity takes precedence (e.g. critical > high > medium).
    2. If severities are identical, prefer the more informative/descriptive message.
    """
    w1 = SEVERITY_WEIGHTS.get(f1.severity.lower(), 0)
    w2 = SEVERITY_WEIGHTS.get(f2.severity.lower(), 0)

    if w1 > w2:
        return f1
    if w2 > w1:
        return f2

    # Tie-breaker: longer and more detailed message
    return f1 if len(f1.message.strip()) >= len(f2.message.strip()) else f2


def deduplicate_findings(findings: List[Finding]) -> List[Finding]:
    """
    Deduplicate a list of findings from multiple agents while preserving
    the most descriptive, highest-severity findings.
    """
    if not findings:
        return []

    unique_findings: List[Finding] = []

    for finding in findings:
        duplicate_index: Optional[int] = None

        for idx, existing in enumerate(unique_findings):
            if _are_findings_duplicates(existing, finding):
                duplicate_index = idx
                break

        if duplicate_index is not None:
            # Replace with the better finding
            better = _select_better_finding(unique_findings[duplicate_index], finding)
            unique_findings[duplicate_index] = better
        else:
            unique_findings.append(finding)

    return unique_findings


def compute_verdict(findings: List[Finding]) -> VerdictType:
    """
    Compute deterministic PR verdict based on aggregated findings.

    Rules:
    - 'request_changes': at least one 'critical' or 'high' severity finding.
    - 'comment': no critical/high findings, but at least one 'medium' finding.
    - 'approve': no critical, high, or medium findings (low and info allowed).
    """
    severities = {f.severity.lower() for f in findings}

    if "critical" in severities or "high" in severities:
        return "request_changes"
    if "medium" in severities:
        return "comment"
    return "approve"


# ---------------------------------------------------------------------------
# LangGraph state specification for workflow compatibility
# ---------------------------------------------------------------------------


class ReviewState(TypedDict):
    """LangGraph State representation for code-review pipelines."""
    pr_diff: str
    security_result: Optional[ReviewResult]
    style_result: Optional[ReviewResult]
    logic_result: Optional[ReviewResult]
    final_result: Optional[ReviewResult]
    errors: List[str]


# ---------------------------------------------------------------------------
# ReviewSupervisor
# ---------------------------------------------------------------------------


class ReviewSupervisor:
    """
    Orchestrates specialized code-review agents (Security, Style, Logic),
    runs them concurrently via asyncio.gather, aggregates and deduplicates
    their findings, and calculates the overall PR verdict.
    """

    def __init__(
        self,
        security_agent: Optional[SecurityAgent] = None,
        style_agent: Optional[StyleAgent] = None,
        logic_agent: Optional[LogicAgent] = None,
        model_name: Optional[str] = None,
    ) -> None:
        self.security_agent = security_agent or SecurityAgent(model_name=model_name)
        self.style_agent = style_agent or StyleAgent(model_name=model_name)
        self.logic_agent = logic_agent or LogicAgent(model_name=model_name)

    async def review(self, pr_diff: str) -> ReviewResult:
        """
        Execute concurrent multi-agent review of a PR diff.

        Steps:
        1. Run Security, Style, and Logic agents concurrently.
        2. Handle individual agent errors gracefully without crashing the review.
        3. Aggregate all identified findings.
        4. Deduplicate overlapping findings across agents.
        5. Compute the deterministic PR review verdict.

        Parameters
        ----------
        pr_diff : str
            The full Pull Request git diff or patch text.

        Returns
        -------
        ReviewResult
            Aggregated findings, deterministic verdict, and any agent errors.
        """
        logger.info("ReviewSupervisor: Starting sequential multi-agent review...")

        # ── Step 1: Sequential execution to respect free-tier rate limits ──
        # Running all 3 agents concurrently fires 6+ LLM calls simultaneously,
        # instantly exhausting the per-minute quota on free tier.
        # Sequential execution spaces calls out and is kinder to rate limits.
        agent_keys = ["security", "style", "logic"]
        agents = [self.security_agent, self.style_agent, self.logic_agent]
        breakdown: Dict[str, int] = {"security": 0, "style": 0, "logic": 0}
        all_findings: List[Finding] = []
        errors: List[str] = []

        for name, agent in zip(agent_keys, agents):
            try:
                res = await agent.run(pr_diff)
                count = len(res.findings)
                logger.info("%sAgent finished with %d finding(s).", name.capitalize(), count)
                breakdown[name] = count
                all_findings.extend(res.findings)
                if res.errors:
                    errors.extend(res.errors)
            except Exception as exc:
                err_msg = f"{name.capitalize()}Agent failed during review: {exc}"
                logger.error(err_msg, exc_info=exc)
                errors.append(err_msg)

        # ── Step 2: Deduplicate findings ──────────────────────────────────
        initial_count = len(all_findings)
        deduped_findings = deduplicate_findings(all_findings)
        logger.info(
            "ReviewSupervisor: Findings aggregated: %d, after deduplication: %d",
            initial_count,
            len(deduped_findings),
        )

        # ── Step 3: Compute deterministic verdict ─────────────────────────
        verdict = compute_verdict(deduped_findings)
        logger.info("ReviewSupervisor: Final PR verdict: %s", verdict)

        return ReviewResult(
            findings=deduped_findings,
            verdict=verdict,
            agent_breakdown=breakdown,
            errors=errors if errors else None,
        )

    # ------------------------------------------------------------------
    # LangGraph integration helper
    # ------------------------------------------------------------------

    def create_workflow(self):
        """
        Construct and return a compiled LangGraph StateGraph workflow for
        the multi-agent code-review pipeline.

        Graph topology:
                         START
                           │
                 ┌─────────┼─────────┐
                 ▼         ▼         ▼
              security   style     logic
                 │         │         │
                 └─────────┼─────────┘
                           ▼
                       aggregate
                           │
                          END
        """
        try:
            from langgraph.graph import END, START, StateGraph
        except ImportError:
            raise ImportError(
                "langgraph must be installed to use create_workflow()."
            )

        workflow = StateGraph(ReviewState)

        # Node definitions
        async def run_security(state: ReviewState):
            try:
                res = await self.security_agent.run(state["pr_diff"])
                return {"security_result": res}
            except Exception as e:
                return {"errors": [f"SecurityAgent failed: {e}"]}

        async def run_style(state: ReviewState):
            try:
                res = await self.style_agent.run(state["pr_diff"])
                return {"style_result": res}
            except Exception as e:
                return {"errors": [f"StyleAgent failed: {e}"]}

        async def run_logic(state: ReviewState):
            try:
                res = await self.logic_agent.run(state["pr_diff"])
                return {"logic_result": res}
            except Exception as e:
                return {"errors": [f"LogicAgent failed: {e}"]}

        def aggregate_results(state: ReviewState):
            findings: List[Finding] = []
            errors: List[str] = list(state.get("errors") or [])
            breakdown: Dict[str, int] = {"security": 0, "style": 0, "logic": 0}

            for name, key in [
                ("security", "security_result"),
                ("style", "style_result"),
                ("logic", "logic_result"),
            ]:
                res = state.get(key)
                if res and isinstance(res, ReviewResult):
                    breakdown[name] = len(res.findings)
                    findings.extend(res.findings)

            deduped = deduplicate_findings(findings)
            verdict = compute_verdict(deduped)
            final_res = ReviewResult(
                findings=deduped,
                verdict=verdict,
                agent_breakdown=breakdown,
                errors=errors if errors else None,
            )
            return {"final_result": final_res}

        workflow.add_node("security", run_security)
        workflow.add_node("style", run_style)
        workflow.add_node("logic", run_logic)
        workflow.add_node("aggregate", aggregate_results)

        # Concurrent fan-out from START
        workflow.add_edge(START, "security")
        workflow.add_edge(START, "style")
        workflow.add_edge(START, "logic")

        # Fan-in to aggregate
        workflow.add_edge("security", "aggregate")
        workflow.add_edge("style", "aggregate")
        workflow.add_edge("logic", "aggregate")

        workflow.add_edge("aggregate", END)

        return workflow.compile()

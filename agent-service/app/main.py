"""
main.py
=======
FastAPI application for the AI Code Reviewer Agent Service.

Endpoints
---------
* GET  /health - Health check endpoint (service status, 200 OK)
* POST /review - Executes the multi-agent code review pipeline via ReviewSupervisor

Architecture
------------
             Node.js / Client
                    │
                    │ POST /review
                    ▼
           ┌─────────────────┐
           │    FastAPI      │
           │    /review      │
           └────────┬────────┘
                    │
                    ▼
           ReviewSupervisor
                    │
       ┌────────────┼────────────┐
       ▼            ▼            ▼
  SecurityAgent  StyleAgent  LogicAgent
       │            │            │
       └────────────┼────────────┘
                    ▼
             Aggregate Findings
                    │
                    ▼
              ReviewResponse
                    │
                    ▼
             Node.js / Client
"""

from __future__ import annotations

import logging
from typing import Dict, List, Literal, Optional

from dotenv import load_dotenv
from fastapi import Depends, FastAPI, HTTPException, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field, field_validator

from app.agents import Finding, ReviewResult, ReviewSupervisor
from app.config import get_cors_origins

# ---------------------------------------------------------------------------
# Logging configuration
# ---------------------------------------------------------------------------

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("agent_service.main")


# ---------------------------------------------------------------------------
# FastAPI Application Initialization
# ---------------------------------------------------------------------------

app = FastAPI(
    title="AI Code Reviewer Agent Service",
    version="1.0.0",
    description="Automated multi-agent code review service powered by Google Gemini, LangChain, and LangGraph.",
)

# ---------------------------------------------------------------------------
# CORS Middleware
# ---------------------------------------------------------------------------

allowed_origins = get_cors_origins()
logger.info("Configured CORS allowed origins: %s", allowed_origins)

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------------------------------------------------------------------------
# Request and Response Models
# ---------------------------------------------------------------------------


class ReviewRequest(BaseModel):
    """Payload sent by the backend to initiate a Pull Request code review."""

    repo_url: str = Field(
        ...,
        description="Full URL of the Git repository being reviewed.",
        examples=["https://github.com/example/repository"],
    )
    pr_number: int = Field(
        ...,
        gt=0,
        description="Pull Request number (must be greater than 0).",
        examples=[123],
    )
    diff: str = Field(
        ...,
        description="The git diff or patch text of the Pull Request.",
    )
    changed_files: List[str] = Field(
        default_factory=list,
        description="List of file paths modified by this Pull Request.",
        examples=[["src/services/user.py", "src/controllers/user.py"]],
    )
    base_sha: str = Field(
        ...,
        description="Base commit SHA of the Pull Request target branch.",
        examples=["abc1234"],
    )
    head_sha: str = Field(
        ...,
        description="Head commit SHA of the Pull Request source branch.",
        examples=["def5678"],
    )

    @field_validator("repo_url", "diff", "base_sha", "head_sha")
    @classmethod
    def check_non_empty(cls, value: str, info) -> str:
        if not value or not value.strip():
            raise ValueError(f"'{info.field_name}' must not be empty or whitespace.")
        return value.strip()

    @field_validator("changed_files")
    @classmethod
    def check_changed_files_list(cls, value: List[str]) -> List[str]:
        if not isinstance(value, list):
            raise ValueError("'changed_files' must be a list of strings.")
        return value


class FindingResponse(BaseModel):
    """A single code-review finding item in the API response."""

    file: str = Field(..., description="Path of the file containing the finding.")
    line: int = Field(..., description="Line number of the finding (1-based).")
    severity: str = Field(
        ...,
        description="Severity: 'critical', 'high', 'medium', 'low', or 'info'.",
    )
    message: str = Field(..., description="Actionable description of the issue and fix.")
    category: str = Field(
        ...,
        description="Category: 'security', 'style', 'logic', 'performance'.",
    )


class ReviewResponse(BaseModel):
    """The structured response returned by the /review endpoint."""

    findings: List[FindingResponse] = Field(
        default_factory=list,
        description="Aggregated and deduplicated findings across all agents.",
    )
    summary: str = Field(
        ...,
        description="Concise deterministic summary of review findings.",
        examples=["3 issues found: 1 high, 1 medium, and 1 low severity."],
    )
    verdict: Literal["approve", "request_changes", "comment"] = Field(
        ...,
        description="Overall review verdict calculated from finding severities.",
    )
    agent_breakdown: Dict[str, int] = Field(
        default_factory=dict,
        description="Breakdown of findings discovered by each specialized agent.",
        examples=[{"security": 1, "style": 0, "logic": 2}],
    )


class HealthResponse(BaseModel):
    """Response returned by the /health endpoint."""

    status: str = Field(default="healthy", description="Service health status.")
    service: str = Field(default="ai-code-reviewer", description="Service identifier.")


# ---------------------------------------------------------------------------
# Helper Functions
# ---------------------------------------------------------------------------


def generate_summary(findings: List[FindingResponse]) -> str:
    """
    Generate a concise deterministic summary from the structured findings.
    Does not make an LLM call.

    Examples:
    - 0 findings: "No significant issues were found in the pull request."
    - 1 finding: "1 issue found: 1 high severity."
    - 3 findings: "3 issues found: 1 high, 1 medium, and 1 low severity."
    """
    if not findings:
        return "No significant issues were found in the pull request."

    counts: Dict[str, int] = {}
    for f in findings:
        sev = f.severity.lower()
        counts[sev] = counts.get(sev, 0) + 1

    total = len(findings)
    issue_label = f"{total} issue{'s' if total != 1 else ''} found"

    # Order severities by importance
    ordered_severities = ["critical", "high", "medium", "low", "info"]
    parts = [f"{counts[s]} {s}" for s in ordered_severities if counts.get(s, 0) > 0]

    if parts:
        if len(parts) == 1:
            sev_str = parts[0]
        elif len(parts) == 2:
            sev_str = f"{parts[0]} and {parts[1]}"
        else:
            sev_str = f"{', '.join(parts[:-1])}, and {parts[-1]}"
        return f"{issue_label}: {sev_str} severity."

    return f"{issue_label}."


def build_review_context(req: ReviewRequest) -> str:
    """
    Construct the unified review context string passed to the ReviewSupervisor.
    Includes PR metadata, changed files, commit SHAs, and the raw diff.
    """
    changed_str = "\n".join(f"- {f}" for f in req.changed_files) if req.changed_files else "None specified"
    return (
        f"Pull Request #{req.pr_number}\n"
        f"Repository: {req.repo_url}\n"
        f"Base Commit: {req.base_sha}\n"
        f"Head Commit: {req.head_sha}\n"
        f"Changed Files ({len(req.changed_files)}):\n{changed_str}\n\n"
        f"PR Diff:\n{req.diff}"
    )


# ---------------------------------------------------------------------------
# Dependency Injection for ReviewSupervisor
# ---------------------------------------------------------------------------

def get_supervisor() -> ReviewSupervisor:
    """Dependency provider returning a ReviewSupervisor instance with latest env configuration."""
    load_dotenv(override=True)
    return ReviewSupervisor()


# ---------------------------------------------------------------------------
# Centralized Exception Handlers
# ---------------------------------------------------------------------------


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    """Handle request validation errors cleanly with HTTP 400."""
    errors = []
    for err in exc.errors():
        loc = " -> ".join(str(item) for item in err.get("loc", []))
        msg = err.get("msg", "Invalid value")
        errors.append(f"{loc}: {msg}")

    logger.warning("Validation error on %s %s: %s", request.method, request.url.path, errors)
    return JSONResponse(
        status_code=status.HTTP_400_BAD_REQUEST,
        content={
            "error": "Validation error",
            "detail": errors,
        },
    )


@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    """Pass through HTTPExceptions with consistent JSON formatting."""
    if isinstance(exc.detail, dict):
        return JSONResponse(status_code=exc.status_code, content=exc.detail)
    return JSONResponse(
        status_code=exc.status_code,
        content={"error": str(exc.detail), "detail": str(exc.detail)},
    )


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    """Catch unhandled errors, log the details, and return a safe HTTP 500."""
    logger.error("Unhandled server exception on %s %s: %s", request.method, request.url.path, exc, exc_info=True)
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "error": "Internal server error",
            "detail": "An unexpected error occurred while processing the request",
        },
    )


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@app.get(
    "/health",
    response_model=HealthResponse,
    status_code=status.HTTP_200_OK,
    summary="Health Check",
    tags=["System"],
)
async def health():
    """
    Return the health status of the agent service.
    Does not invoke the Gemini model or supervisor.
    """
    return HealthResponse(
        status="healthy",
        service="ai-code-reviewer",
    )


@app.post(
    "/review",
    response_model=ReviewResponse,
    status_code=status.HTTP_200_OK,
    summary="Review Pull Request",
    tags=["Review"],
)
async def review(
    request: ReviewRequest,
    supervisor: ReviewSupervisor = Depends(get_supervisor),
):
    """
    Execute an automated multi-agent code review on a Pull Request.

    Runs SecurityAgent, StyleAgent, and LogicAgent concurrently, aggregates and
    deduplicates their findings, and assigns a deterministic PR verdict.
    """
    # Safe logging: log identifiers and summary metrics only (no diffs, no secrets)
    logger.info(
        "Review request received | repo: %s | PR #%d | base: %s | head: %s | changed_files: %d",
        request.repo_url,
        request.pr_number,
        request.base_sha[:7] if len(request.base_sha) >= 7 else request.base_sha,
        request.head_sha[:7] if len(request.head_sha) >= 7 else request.head_sha,
        len(request.changed_files),
    )

    try:
        review_context = build_review_context(request)
        logger.warning("=== REVIEW CALLED === model: %s | diff len: %d", supervisor.security_agent.model_name, len(request.diff))

        # Execute multi-agent review via ReviewSupervisor
        review_result: ReviewResult = await supervisor.review(review_context)
        logger.warning("=== SUPERVISOR RESULT === findings: %d | errors: %s", len(review_result.findings), review_result.errors)

        # Convert findings to response models
        finding_responses = [
            FindingResponse(
                file=f.file,
                line=f.line,
                severity=f.severity,
                message=f.message,
                category=f.category,
            )
            for f in review_result.findings
        ]

        summary = generate_summary(finding_responses)
        verdict = review_result.verdict or "approve"

        # Construct agent breakdown
        agent_breakdown = review_result.agent_breakdown or {
            "security": sum(1 for f in finding_responses if f.category == "security"),
            "style": sum(1 for f in finding_responses if f.category == "style"),
            "logic": sum(1 for f in finding_responses if f.category in ("logic", "performance")),
        }

        logger.info(
            "Review pipeline completed for PR #%d | findings: %d | verdict: %s",
            request.pr_number,
            len(finding_responses),
            verdict,
        )

        return ReviewResponse(
            findings=finding_responses,
            summary=summary,
            verdict=verdict,
            agent_breakdown=agent_breakdown,
        )

    except Exception as exc:
        logger.error(
            "Review pipeline failed for PR #%d at %s: %s",
            request.pr_number,
            request.repo_url,
            exc,
            exc_info=True,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error": "Review pipeline failed",
                "detail": "Unable to complete code review",
            },
        )

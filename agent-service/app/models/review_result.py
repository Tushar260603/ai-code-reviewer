"""
review_result.py
================
Structured models representing review findings and response payloads.
"""

from __future__ import annotations

from typing import Dict, List, Literal, Optional
from pydantic import BaseModel, Field

# Re-export Finding and ReviewResult from base_agent for backward compatibility
from app.agents.base_agent import Finding, ReviewResult, VerdictType


class FindingResponse(BaseModel):
    """API response model for an individual code review finding."""

    file: str = Field(..., description="File path of the finding.")
    line: int = Field(..., description="1-based line number.")
    severity: str = Field(..., description="Severity level: critical, high, medium, low, info.")
    message: str = Field(..., description="Actionable message describing the issue and remediation.")
    category: str = Field(..., description="Category: security, style, logic, performance.")


class ReviewResponse(BaseModel):
    """API response model for the completed PR code review."""

    findings: List[FindingResponse] = Field(default_factory=list)
    summary: str = Field(..., description="Concise human-readable summary of review findings.")
    verdict: Literal["approve", "request_changes", "comment"] = Field(
        ..., description="Deterministic review verdict."
    )
    agent_breakdown: Dict[str, int] = Field(
        default_factory=dict, description="Count of findings per specialized agent."
    )

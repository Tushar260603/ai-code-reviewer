"""
pr_context.py
=============
Pydantic data models for Pull Request context and review requests.
"""

from __future__ import annotations

from typing import List
from pydantic import BaseModel, Field, field_validator


class PRContext(BaseModel):
    """Unified data model encapsulating a Pull Request's review context."""

    repo_url: str = Field(..., description="Repository URL.")
    pr_number: int = Field(..., gt=0, description="Pull Request number.")
    diff: str = Field(..., description="Raw unified diff text.")
    changed_files: List[str] = Field(default_factory=list, description="Modified file paths.")
    base_sha: str = Field(..., description="Base target commit SHA.")
    head_sha: str = Field(..., description="Head source commit SHA.")

    @field_validator("repo_url", "diff", "base_sha", "head_sha")
    @classmethod
    def validate_non_empty(cls, value: str, info) -> str:
        if not value or not value.strip():
            raise ValueError(f"'{info.field_name}' must not be empty or whitespace.")
        return value.strip()

    def to_agent_context(self) -> str:
        """Format the PR context into a descriptive prompt for AI review agents."""
        files_str = "\n".join(f"- {f}" for f in self.changed_files) if self.changed_files else "None listed"
        return (
            f"Pull Request #{self.pr_number}\n"
            f"Repository: {self.repo_url}\n"
            f"Base Commit: {self.base_sha}\n"
            f"Head Commit: {self.head_sha}\n"
            f"Changed Files ({len(self.changed_files)}):\n{files_str}\n\n"
            f"PR Diff:\n{self.diff}"
        )

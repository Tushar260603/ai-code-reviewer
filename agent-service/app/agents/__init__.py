"""
agents package
==============
Exports all specialized code review agents and the supervisor.
"""

from .base_agent import BaseAgent, Finding, ReviewResult, VerdictType
from .logic_agent import LogicAgent
from .security_agent import SecurityAgent
from .style_agent import StyleAgent
from .supervisor import ReviewSupervisor, compute_verdict, deduplicate_findings

__all__ = [
    "BaseAgent",
    "Finding",
    "ReviewResult",
    "VerdictType",
    "SecurityAgent",
    "StyleAgent",
    "LogicAgent",
    "ReviewSupervisor",
    "deduplicate_findings",
    "compute_verdict",
]

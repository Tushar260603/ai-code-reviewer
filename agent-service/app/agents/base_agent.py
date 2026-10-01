"""
base_agent.py
=============
Generic base agent powered by **LangChain** + **LangGraph**.

Architecture
------------
                         ┌─────────────────────────────────┐
  BaseAgent.run(context) │   LangGraph ReAct graph         │
         │               │                                 │
         ▼               │  START                          │
  ainvoke(messages) ────►│   └─► [call_model]              │
                         │            │                    │
                         │    tool calls?                  │
                         │    yes ▼        no ──────► END  │
                         │  [tool_node]                    │
                         │       └──────────────────────►  │
                         └─────────────────────────────────┘
                                       │
                                       ▼
                           llm.with_structured_output
                                 (ReviewResult)

Key design decisions
--------------------
* `ChatGoogleGenerativeAI` (langchain-google-genai) wraps the Gemini model.
* Tools are standard LangChain `BaseTool` / `@tool`-decorated callables —
  no vendor-specific schema needed.
* `create_react_agent` (langgraph.prebuilt) builds the full ReAct loop
  (call_model ↔ tool_node) automatically, including parallel tool execution
  and graceful error handling via ToolNode's built-in error catching.
* After the ReAct loop finishes, a *separate* structured-output LLM call
  (`llm.with_structured_output(ReviewResult)`) converts the final assistant
  message into a validated Pydantic object.
* Subclasses only need to supply a `system_prompt` and a list of LangChain
  `BaseTool` objects — everything else is handled here.
* The public contract `async run(context: str) -> ReviewResult` is
  intentionally preserved so that subclasses and callers need no changes.
"""

from __future__ import annotations

import logging
import os
from typing import Dict, List, Literal, Optional

from dotenv import load_dotenv
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_core.tools import BaseTool
from langchain_google_genai import ChatGoogleGenerativeAI
from langgraph.prebuilt import create_react_agent
from pydantic import BaseModel, Field

# ---------------------------------------------------------------------------
# Environment setup
# ---------------------------------------------------------------------------

# Loads GEMINI_API_KEY and GEMINI_MODEL from agent-service/.env (or any
# .env found walking up the directory tree).
load_dotenv(override=True)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Shared output schema
# ---------------------------------------------------------------------------

VerdictType = Literal["approve", "request_changes", "comment"]


class Finding(BaseModel):
    """A single code-review finding produced by any agent."""

    file: str = Field(description="Path of the file that contains the issue.")
    line: int = Field(description="Line number where the issue was found (1-based).")
    severity: str = Field(
        description=(
            "Severity level of the finding. "
            "Must be one of: 'critical', 'high', 'medium', 'low', or 'info'."
        )
    )
    message: str = Field(description="Human-readable description of the issue.")
    category: str = Field(
        description=(
            "Category of the finding, e.g. 'security', 'style', 'logic', 'performance'."
        )
    )


class ReviewResult(BaseModel):
    """Aggregated result returned by every agent's `run()` method or supervisor."""

    findings: List[Finding] = Field(
        default_factory=list,
        description="All findings discovered during the review.",
    )
    verdict: Optional[Literal["approve", "request_changes", "comment"]] = Field(
        default=None,
        description="Overall review verdict: 'approve', 'request_changes', or 'comment'.",
    )
    agent_breakdown: Optional[Dict[str, int]] = Field(
        default=None,
        description="Count of findings contributed by each specialized agent.",
    )
    errors: Optional[List[str]] = Field(
        default=None,
        description="Any error messages encountered during review or execution of sub-agents.",
    )


# ---------------------------------------------------------------------------
# BaseAgent
# ---------------------------------------------------------------------------


class BaseAgent:
    """
    A generic, async, tool-capable code-review agent built on LangChain +
    LangGraph.

    Parameters
    ----------
    system_prompt : str
        Instructions that define the agent's role and behaviour.
    tools : list[BaseTool], optional
        LangChain tool objects (created with ``@tool`` or by subclassing
        ``BaseTool``) that the agent may invoke.  Defaults to an empty list.
    model_name : str, optional
        Gemini model identifier.  Resolution order:
        1. The *model_name* argument.
        2. The ``GEMINI_MODEL`` environment variable.
        3. Hard default: ``"gemini-2.5-flash"``.
    """

    def __init__(
        self,
        system_prompt: str,
        tools: Optional[List[BaseTool]] = None,
        model_name: Optional[str] = None,
    ) -> None:
        self.system_prompt = system_prompt
        self.tools: List[BaseTool] = tools or []

        # Resolve model name
        self.model_name: str = (
            model_name
            or os.getenv("GEMINI_MODEL")
            or "gemini-3.1-flash-lite"
        )

        # Validate API key up-front so failures surface immediately
        api_key = os.getenv("GEMINI_API_KEY")
        if not api_key:
            raise EnvironmentError(
                "GEMINI_API_KEY is not set. "
                "Add it to agent-service/.env or export it as an environment variable."
            )

        # -----------------------------------------------------------------
        # LangChain LLM (ChatGoogleGenerativeAI)
        # -----------------------------------------------------------------
        self._llm = ChatGoogleGenerativeAI(
            model=self.model_name,
            google_api_key=api_key,
            temperature=0,          # deterministic output for code review
            convert_system_message_to_human=False,
        )

        # -----------------------------------------------------------------
        # LangGraph ReAct agent graph
        # -----------------------------------------------------------------
        # create_react_agent builds:
        #   START → call_model → (tool calls?) → tool_node → call_model → … → END
        #
        # ToolNode (inside the graph) runs all requested tools concurrently
        # and catches individual tool errors, returning them as ToolMessages
        # so the LLM can reason about failures rather than crashing.
        self._graph = create_react_agent(
            model=self._llm,
            tools=self.tools,
            # Inject the system prompt into every invocation via prompt
            prompt=SystemMessage(content=self.system_prompt),
        )

        # -----------------------------------------------------------------
        # Structured-output LLM for the final answer
        # -----------------------------------------------------------------
        # A second LLM binding that forces the response into ReviewResult.
        # Used *after* the ReAct loop has finished gathering information.
        self._structured_llm = self._llm.with_structured_output(ReviewResult)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def run(self, context: str) -> ReviewResult:
        """
        Run the agent on *context* and return a :class:`ReviewResult`.

        Direct structured review performs a single, fast, deterministic LLM invocation
        mapping the diff context directly into structured Pydantic findings.
        Execution finishes in 1–2 seconds per agent without tool recursion loops.
        """
        logger.info(
            "[%s] Starting review with model=%s",
            self.__class__.__name__,
            self.model_name,
        )

        messages = [
            SystemMessage(content=self.system_prompt),
            HumanMessage(
                content=(
                    f"{context}\n\n"
                    "---\n"
                    "Analyze the Pull Request diff above strictly according to your system prompt instructions. "
                    "Produce a valid ReviewResult JSON object containing every finding you identified "
                    "with its exact file path, 1-based line number, severity ('critical', 'high', 'medium', 'low', 'info'), "
                    "category, and a clear actionable message."
                )
            ),
        ]

        try:
            review_result: ReviewResult = await self._structured_llm.ainvoke(messages)
            logger.info(
                "[%s] Review complete — %d finding(s).",
                self.__class__.__name__,
                len(review_result.findings),
            )
            return review_result
        except Exception as exc:  # noqa: BLE001
            logger.error(
                "[%s] LLM structured review call failed: %s",
                self.__class__.__name__,
                exc,
            )
            return ReviewResult(findings=[], errors=[str(exc)])

"""
logic_agent.py
==============
Specialized logic, correctness, and performance review agent extending BaseAgent.

Focus areas
-----------
* Logic flaws, inverted conditions, off-by-one errors
* State management bugs and improper lifecycle transitions
* None/null/undefined pointer exceptions or missing checks
* Edge cases, empty collections, extreme boundary inputs
* Concurrency issues, thread safety, race conditions
* Inadequate or incorrect exception/error handling
* API contract violations or broken interfaces
* Regressions or behavioral changes breaking existing functionality
* Performance regressions (e.g. N+1 queries, unindexed lookups, redundant loops)
* Potential infinite loops or unhandled recursion termination
* Missing or insufficient automated tests for modified logic
"""

from __future__ import annotations

import logging
from typing import List, Optional

from langchain_core.tools import BaseTool

from app.agents.base_agent import BaseAgent
from app.tools.read_file import read_file
from app.tools.run_tests import run_tests
from app.tools.search_codebase import search_codebase

logger = logging.getLogger(__name__)

LOGIC_SYSTEM_PROMPT = """You are a Principal Software Engineer and correctness specialist reviewing a Pull Request diff for algorithmic logic, bugs, edge cases, and performance.

Your mission is to catch functional bugs, broken contracts, edge cases, regressions, and performance bottlenecks before code merges to production.

Key areas to inspect:
1. Algorithmic & Logical Correctness:
   - Inverted booleans, incorrect conditionals (`and` vs `or`, strict vs loose comparisons).
   - Off-by-one errors in loops, slices, ranges, or pagination.
   - State transition errors, unhandled states, or invalid enum transitions.
2. Boundary Conditions & Null Safety:
   - None / null / undefined / empty collection handling (`[]`, `{}`, `""`, `0`).
   - Division by zero, numerical overflow/underflow, index out of range.
3. Concurrency & Asynchronous Behavior:
   - Race conditions, missing locks, improper async/await synchronization, deadlocks.
4. Error Handling & Resilience:
   - Swallowed exceptions (bare `except: pass` hiding real bugs), inappropriate re-raises.
   - Resource leaks (unclosed files, network sessions, unreleased locks).
5. API & Contract Integrity:
   - Signature changes breaking callers, missing required arguments, wrong return types.
   - Regressions in behavior compared to previous implementations.
6. Performance & Scalability:
   - Accidental O(N^2) or higher complexity, unnecessary iterations.
   - Database N+1 queries, unindexed filters, loading entire datasets into memory.
   - Potential infinite loops or missing base cases in recursive logic.
7. Test Coverage:
   - Critical logic changes without accompanying unit tests.

Investigation workflow:
- Thoroughly analyze the PR diff.
- Use `read_file` to inspect callers, callee functions, class definitions, and existing test suites.
- Use `search_codebase` to identify where affected functions or classes are invoked across the project.
- Use `run_tests` to execute existing tests and see if the PR introduces test failures or regressions. Cite test results in your findings if relevant.
- Be precise: report each finding with exact file path, 1-based line number, accurate severity ('critical', 'high', 'medium', 'low', 'info'), category ('logic' or 'performance'), and an explanation of the buggy scenario and recommended fix.
- Do NOT report stylistic or cosmetic issues. Focus strictly on functional correctness and runtime performance.
"""


class LogicAgent(BaseAgent):
    """
    Agent dedicated to reviewing code logic, correctness, edge cases, and performance.

    Tools available:
    - `read_file`: inspect code context in full files
    - `search_codebase`: check callers and implementations repository-wide
    - `run_tests`: run the test suite to verify regressions or test coverage
    """

    def __init__(
        self,
        model_name: Optional[str] = None,
        tools: Optional[List[BaseTool]] = None,
        system_prompt: Optional[str] = None,
    ) -> None:
        prompt = system_prompt or LOGIC_SYSTEM_PROMPT
        agent_tools = (
            tools
            if tools is not None
            else [read_file, search_codebase, run_tests]
        )
        super().__init__(
            system_prompt=prompt,
            tools=agent_tools,
            model_name=model_name,
        )

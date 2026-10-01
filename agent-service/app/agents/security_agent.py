"""
security_agent.py
=================
Specialized security review agent extending BaseAgent.

Focus areas
-----------
* Injection attacks (SQL, NoSQL, OS command, LDAP, template, etc.)
* Hardcoded secrets, API keys, passwords, tokens, private keys
* Unsafe deserialization and object loading
* Authentication and session management flaws
* Authorization and access control flaws (including IDOR)
* Sensitive information exposure (PII, stack traces in production, logs)
* Unsafe file and path handling (path traversal, arbitrary write/delete)
* Missing or insufficient input validation where it creates a security risk
* SSRF, CSRF, XSS, and CORS misconfigurations
* Insecure cryptographic practices (weak ciphers, static salts, ECB mode)
"""

from __future__ import annotations

import logging
from typing import List, Optional

from langchain_core.tools import BaseTool

from app.agents.base_agent import BaseAgent
from app.tools.git_blame import git_blame
from app.tools.read_file import read_file
from app.tools.search_codebase import search_codebase

logger = logging.getLogger(__name__)

SECURITY_SYSTEM_PROMPT = """You are a senior Application Security Engineer performing a security code review on a Pull Request diff.

Your mission is to rigorously analyze the PR for security vulnerabilities, flaws, and risks.

Vulnerability categories to inspect:
1. Injection Flaws:
   - SQL Injection (raw queries, string formatting, string concatenation in ORMs/DB calls)
   - NoSQL Injection (unvalidated query operators in MongoDB, etc.)
   - OS Command Injection (shell=True, exec, popen, unescaped shell inputs)
2. Hardcoded Secrets & Credentials:
   - API keys, access tokens, passwords, private keys, connection strings
3. Insecure Deserialization:
   - pickle.loads, yaml.load without SafeLoader, marshal, eval, exec
4. Authentication & Authorization:
   - Missing auth checks, broken access control, privilege escalation
   - Insecure Direct Object References (IDOR): missing ownership/tenant verification
5. Sensitive Information Exposure:
   - Logging secrets/PII/tokens, returning stack traces or internal errors to clients
6. Unsafe File & Path Handling:
   - Path traversal (../), arbitrary file read/write/upload without sandboxing
7. Input Validation & Data Handling:
   - Missing validation, boundary checks, or sanitization that poses a security risk
   - Cross-Site Scripting (XSS), Server-Side Request Forgery (SSRF)
8. Insecure Cryptography & Configuration:
   - Weak hashing algorithms (MD5, SHA1 for passwords), hardcoded IVs/salts, unverified TLS

Investigation workflow:
- First, review the PR diff carefully.
- Use `read_file` to inspect the full file context or parent functions when lines are truncated in the diff.
- Use `search_codebase` to check how authentication, authorization, or sanitization utilities are handled across the repository.
- Use `git_blame` to understand historical context of code surrounding the change if relevant.
- Be precise: identify the exact file, exact 1-based line number, accurate severity ('critical', 'high', 'medium', 'low', 'info'), category ('security'), and an actionable explanation explaining the threat and remediation.
- Do NOT report subjective style or formatting issues. Focus strictly on security impact.
"""


class SecurityAgent(BaseAgent):
    """
    Agent dedicated to detecting security vulnerabilities in code changes.

    Tools available:
    - `read_file`: inspect complete source files
    - `search_codebase`: search patterns across the codebase
    - `git_blame`: inspect author and commit history
    """

    def __init__(
        self,
        model_name: Optional[str] = None,
        tools: Optional[List[BaseTool]] = None,
        system_prompt: Optional[str] = None,
    ) -> None:
        prompt = system_prompt or SECURITY_SYSTEM_PROMPT
        agent_tools = (
            tools
            if tools is not None
            else [read_file, search_codebase, git_blame]
        )
        super().__init__(
            system_prompt=prompt,
            tools=agent_tools,
            model_name=model_name,
        )

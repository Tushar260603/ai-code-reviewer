"""
config.py
=========
Central configuration for the AI Code Reviewer Agent Service.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import List

from dotenv import load_dotenv

# Load .env file from agent-service or workspace root
load_dotenv()

REPO_ROOT = os.getenv("REPO_ROOT", str(Path.cwd()))
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")


def get_cors_origins() -> List[str]:
    """
    Parse allowed CORS origins from CORS_ORIGINS or NODE_SERVER_URL environment variables.

    Supports:
    - CORS_ORIGINS="http://localhost:8000,http://localhost:3000"
    - NODE_SERVER_URL="http://localhost:8000"
    - Safe default development fallbacks
    """
    cors_env = os.getenv("CORS_ORIGINS")
    if cors_env:
        return [origin.strip() for origin in cors_env.split(",") if origin.strip()]
    node_server = os.getenv("NODE_SERVER_URL")
    if node_server:
        return [node_server.strip()]
    return ["http://localhost:8000", "http://localhost:3000"]

"""
conftest.py
===========
Shared pytest fixtures for the agent-service test suite.
"""

import os
import pytest
from pathlib import Path


# ---------------------------------------------------------------------------
# Ensure REPO_ROOT is always set for tests even without a .env file
# ---------------------------------------------------------------------------
@pytest.fixture(autouse=True)
def set_repo_root(tmp_path, monkeypatch):
    """
    Point REPO_ROOT at a fresh temporary directory for each test.
    Individual tests that need specific files should write them inside tmp_path.
    Tests that need the REAL repo root can override this fixture.
    """
    monkeypatch.setenv("REPO_ROOT", str(tmp_path))
    yield tmp_path


@pytest.fixture
def real_repo_root(monkeypatch):
    """
    Point REPO_ROOT at the actual project repo (from .env or cwd).
    Use for integration tests only.
    """
    root = os.getenv("REPO_ROOT") or str(
        Path(__file__).resolve().parents[2]  # …/AI-Reviewer-PROJECT-26-09
    )
    monkeypatch.setenv("REPO_ROOT", root)
    return Path(root)

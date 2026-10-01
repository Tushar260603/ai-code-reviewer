"""
client.py
=========
Helper for acquiring PyGithub client instances.
"""

from .comment_poster import get_github_client

__all__ = ["get_github_client"]

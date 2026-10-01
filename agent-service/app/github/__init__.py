"""
github package
==============
GitHub integration utilities: unified diff parsing and PyGithub comment/check run posting.
"""

from .comment_poster import (
    create_check_run,
    get_github_client,
    post_inline_comment,
    post_summary_comment,
    resolve_repository,
)
from .diff_parser import parse_diff

__all__ = [
    "parse_diff",
    "post_summary_comment",
    "post_inline_comment",
    "create_check_run",
    "get_github_client",
    "resolve_repository",
]

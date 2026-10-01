"""
diff_parser.py
==============
Parser for unified Git diff strings into structured file changes and line numbers.

Pure standard-library implementation with no external dependencies or I/O.
"""

from __future__ import annotations

import re
from typing import Any, Dict, List, Optional

# Regex to match hunk headers, e.g.:
# @@ -10,5 +10,7 @@ def get_user():
# @@ -1 +1,2 @@
# @@ -0,0 +1,5 @@
HUNK_HEADER_RE = re.compile(
    r"^@@\s+-(\d+)(?:,(\d+))?\s+\+(\d+)(?:,(\d+))?\s+@@"
)

# Regex to parse git diff file headers
DIFF_GIT_RE = re.compile(r"^diff --git\s+(?:\"?a/(.+?)\"?)\s+(?:\"?b/(.+?)\"?)$")
OLD_FILE_RE = re.compile(r"^---\s+(?:\"?[a/]*(.+?)\"?)$")
NEW_FILE_RE = re.compile(r"^\+\+\+\s+(?:\"?[b/]*(.+?)\"?)$")


def _clean_path(path: str) -> str:
    """Normalize file paths from diff headers, stripping a/ or b/ prefixes and quotes."""
    p = path.strip().strip('"').strip("'")
    if p.startswith("a/") or p.startswith("b/"):
        p = p[2:]
    return p.replace("\\", "/")


def parse_diff(diff: str) -> List[Dict[str, Any]]:
    """
    Parse a unified Git diff string into structured file modifications.

    For each file, tracks added and removed lines with their respective
    1-based line numbers in the new and old versions of the file.

    Args:
        diff: Unified Git diff text (e.g. output of `git diff`).

    Returns:
        A list of dictionaries for each modified file in the format:
        [
            {
                "file": "src/user.py",
                "added_lines": [
                    {"line_number": 11, "content": "..."}
                ],
                "removed_lines": [
                    {"line_number": 11, "content": "..."}
                ]
            }
        ]
    """
    if not diff or not diff.strip():
        return []

    lines = diff.splitlines()
    files: List[Dict[str, Any]] = []
    file_map: Dict[str, Dict[str, Any]] = {}

    current_file: Optional[str] = None
    old_file_path: Optional[str] = None
    new_file_path: Optional[str] = None
    in_hunk = False
    old_line = 0
    new_line = 0

    def get_or_create_file_entry(filepath: str) -> Dict[str, Any]:
        if filepath not in file_map:
            entry = {
                "file": filepath,
                "added_lines": [],
                "removed_lines": [],
            }
            file_map[filepath] = entry
            files.append(entry)
        return file_map[filepath]

    for line in lines:
        # Detect new file diff header
        if line.startswith("diff --git"):
            in_hunk = False
            match = DIFF_GIT_RE.match(line)
            if match:
                old_file_path = _clean_path(match.group(1))
                new_file_path = _clean_path(match.group(2))
                current_file = new_file_path
            else:
                # Fallback for paths with special characters
                parts = line.split()
                if len(parts) >= 4:
                    old_file_path = _clean_path(parts[2])
                    new_file_path = _clean_path(parts[3])
                    current_file = new_file_path
            continue

        # Check for rename target
        if line.startswith("rename to "):
            renamed_to = _clean_path(line[len("rename to "):])
            current_file = renamed_to
            new_file_path = renamed_to
            continue

        # Handle --- header
        if line.startswith("--- "):
            in_hunk = False
            target = line[4:].strip()
            if target != "/dev/null":
                old_file_path = _clean_path(target)
            continue

        # Handle +++ header
        if line.startswith("+++ "):
            in_hunk = False
            target = line[4:].strip()
            if target == "/dev/null":
                # Deleted file: target is old_file_path
                current_file = old_file_path
            else:
                new_file_path = _clean_path(target)
                current_file = new_file_path
            continue

        # Binary files notice
        if line.startswith("Binary files ") or line.startswith("GIT binary patch"):
            in_hunk = False
            if current_file:
                get_or_create_file_entry(current_file)
            continue

        # Check for hunk header
        hunk_match = HUNK_HEADER_RE.match(line)
        if hunk_match:
            in_hunk = True
            old_start = int(hunk_match.group(1))
            new_start = int(hunk_match.group(3))

            # If start is 0 (e.g. empty file), first line will be 1
            old_line = old_start if old_start > 0 else 1
            new_line = new_start if new_start > 0 else 1

            if current_file:
                get_or_create_file_entry(current_file)
            continue

        # If inside a hunk, process content lines
        if in_hunk and current_file:
            entry = get_or_create_file_entry(current_file)

            if line.startswith("+"):
                # Added line in new file
                content = line[1:]
                entry["added_lines"].append(
                    {
                        "line_number": new_line,
                        "content": content,
                    }
                )
                new_line += 1

            elif line.startswith("-"):
                # Removed line in old file
                content = line[1:]
                entry["removed_lines"].append(
                    {
                        "line_number": old_line,
                        "content": content,
                    }
                )
                old_line += 1

            elif line.startswith(" "):
                # Context line (present in both)
                old_line += 1
                new_line += 1

            elif line == "":
                # Empty context line
                old_line += 1
                new_line += 1

            elif line.startswith("\\"):
                # e.g. "\ No newline at end of file" -> ignore
                continue
            else:
                # Other metadata line encountered, end current hunk
                in_hunk = False

    return files

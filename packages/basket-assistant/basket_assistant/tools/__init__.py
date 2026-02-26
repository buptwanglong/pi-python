"""
Built-in tools for the coding agent.

This module provides all the built-in tools that the agent can use.
"""

from .bash import BASH_TOOL, BashParams, BashResult, execute_bash
from .edit import EDIT_TOOL, EditParams, EditResult, edit_file
from .grep import GREP_TOOL, GrepMatch, GrepParams, GrepResult, grep_files
from .read import READ_TOOL, ReadParams, ReadResult, read_file
from .skill import SkillParams, create_skill_tool
from .web_fetch import WEB_FETCH_TOOL, WebFetchParams, web_fetch
from .task import TaskParams, create_task_tool
from .web_search import WebSearchParams, create_web_search_tool
from .write import WRITE_TOOL, WriteParams, WriteResult, write_file

# All built-in tools
BUILT_IN_TOOLS = [
    READ_TOOL,
    WRITE_TOOL,
    EDIT_TOOL,
    BASH_TOOL,
    GREP_TOOL,
    WEB_FETCH_TOOL,
]

__all__ = [
    # Tools
    "BUILT_IN_TOOLS",
    "READ_TOOL",
    "WRITE_TOOL",
    "EDIT_TOOL",
    "BASH_TOOL",
    "GREP_TOOL",
    # Read
    "ReadParams",
    "ReadResult",
    "read_file",
    # Write
    "WriteParams",
    "WriteResult",
    "write_file",
    # Edit
    "EditParams",
    "EditResult",
    "edit_file",
    # Bash
    "BashParams",
    "BashResult",
    "execute_bash",
    # Grep
    "GrepParams",
    "GrepMatch",
    "GrepResult",
    "grep_files",
    # Skill
    "SkillParams",
    "create_skill_tool",
    # Web Fetch
    "WebFetchParams",
    "web_fetch",
    "WEB_FETCH_TOOL",
    # Task
    "TaskParams",
    "create_task_tool",
    # Web Search
    "WebSearchParams",
    "create_web_search_tool",
]

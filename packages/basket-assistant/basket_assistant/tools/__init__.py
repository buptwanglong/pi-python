"""
Built-in tools for the coding agent.

This module provides all the built-in tools that the agent can use.
"""

from .bash import BASH_TOOL, BashParams, BashResult, execute_bash
from .blackboard_tools import (
    BlackboardReadParams,
    BlackboardWriteParams,
    create_blackboard_read_tool,
    create_blackboard_write_tool,
)
from .dag_task import DAGNodeSpec, DAGTaskParams, create_dag_task_tool
from .edit import EDIT_TOOL, EditParams, EditResult, edit_file
from .grep import GREP_TOOL, GrepMatch, GrepParams, GrepResult, grep_files
from .read import READ_TOOL, ReadParams, ReadResult, read_file
from .skill import SkillParams, create_skill_tool
from .web_fetch import WEB_FETCH_TOOL, WebFetchParams, web_fetch
from .task import TaskParams, TaskSpec, ParallelTaskParams, create_task_tool, create_parallel_task_tool
from .ask_user_question import (
    AskUserQuestionParams,
    create_ask_user_question_tool,
)
from .todo_write import TodoItem, TodoWriteParams, create_todo_write_tool
from .web_search import WebSearchParams, create_web_search_tool
from .write import WRITE_TOOL, WriteParams, WriteResult, write_file

from basket_assistant.skills.registry import load_builtin_skill_tool_modules

load_builtin_skill_tool_modules()

__all__ = [
    # Tools
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
    "TaskSpec",
    "ParallelTaskParams",
    "create_task_tool",
    "create_parallel_task_tool",
    # AskUserQuestion
    "AskUserQuestionParams",
    "create_ask_user_question_tool",
    # TodoWrite
    "TodoItem",
    "TodoWriteParams",
    "create_todo_write_tool",
    # Web Search
    "WebSearchParams",
    "create_web_search_tool",
    # Blackboard
    "BlackboardReadParams",
    "BlackboardWriteParams",
    "create_blackboard_read_tool",
    "create_blackboard_write_tool",
    # DAG Task
    "DAGNodeSpec",
    "DAGTaskParams",
    "create_dag_task_tool",
]

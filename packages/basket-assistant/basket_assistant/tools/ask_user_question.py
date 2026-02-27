"""
AskUserQuestion tool - Ask the user a question; answer is supplied in the next message (session resume).

Does not block: writes question/options to _last_ask_user_question; agent_tool_call_end
merges with tool_call_id and appends to pending_asks. User replies in next turn to resume.
"""

from typing import Any, List, Optional

from pydantic import BaseModel, Field

ASK_USER_QUESTION_PLACEHOLDER = (
    "Question sent. User will reply in the next message; then I will continue."
)


class AskUserQuestionParams(BaseModel):
    """Parameters for the AskUserQuestion tool."""

    question: str = Field(..., description="The question to ask the user.")
    options: Optional[List[dict]] = Field(
        default=None,
        description="Optional list of choices, e.g. [{\"id\": \"a\", \"label\": \"Option A\"}]",
    )


def create_ask_user_question_tool(agent_ref: Any) -> dict:
    """
    Create the ask_user_question tool. Call from main when registering tools.

    agent_ref must have: _last_ask_user_question (dict or None) to store question/options
    for the current call; tool_call_id is merged in agent_tool_call_end and appended
    to pending_asks.

    Returns a dict with name, description, parameters, execute_fn for agent.register_tool().
    """
    description = (
        "Ask the user a question. Use when you need clarification, scope, preferences, "
        "or a choice before proceeding (e.g. in plan mode to clarify requirements). "
        "The question and optional choices are shown to the user; they reply in their next message, "
        "and that reply is used as this tool's result so you can continue.\n\n"
        "Parameters: question (required), options (optional list of {id, label} dicts)."
    )

    async def execute_ask_user_question(
        question: str, options: Optional[List[dict]] = None
    ) -> str:
        if not question or not isinstance(question, str):
            return "Error: question must be a non-empty string."
        opts = options if isinstance(options, list) else []
        agent_ref._last_ask_user_question = {
            "question": question.strip(),
            "options": opts,
        }
        return ASK_USER_QUESTION_PLACEHOLDER

    return {
        "name": "ask_user_question",
        "description": description,
        "parameters": AskUserQuestionParams,
        "execute_fn": execute_ask_user_question,
    }


__all__ = [
    "ASK_USER_QUESTION_PLACEHOLDER",
    "AskUserQuestionParams",
    "create_ask_user_question_tool",
]

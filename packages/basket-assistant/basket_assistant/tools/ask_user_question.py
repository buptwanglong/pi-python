"""
AskUserQuestion tool - Ask the user a question; answer is supplied in the next message (session resume).

Does not block: the agent_tool_call_start handler builds { tool_call_id, question, options }
from the event and appends to pending_asks. This tool only validates args and returns a placeholder.
User replies in next turn to resume.
"""

from typing import List, Optional

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


def create_ask_user_question_tool(ctx=None) -> dict:
    """
    Create the ask_user_question tool. Call from main when registering tools.

    Pending asks are populated by the agent_tool_call_start handler (tool_call_id + arguments);
    this tool does not hold state and only returns a placeholder string for the model.

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

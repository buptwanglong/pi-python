"""
Trajectory schema for agent runs.

JSON-serializable Pydantic models for task trajectory (RL and tuning).
"""

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field, ConfigDict


class ToolCallRecord(BaseModel):
    """Record of a single tool call and its result."""

    tool_name: str
    tool_call_id: str
    arguments: Dict[str, Any] = Field(default_factory=dict)
    result_summary: Optional[str] = None
    error: Optional[str] = None

    model_config = ConfigDict(extra="forbid")


class TurnRecord(BaseModel):
    """Record of one agent turn: input messages, assistant message, and tool calls."""

    turn_index: int
    input_messages: List[Dict[str, Any]] = Field(
        default_factory=list,
        description="Messages sent to the model for this turn (conversation history before this assistant reply)",
    )
    assistant_message: Dict[str, Any] = Field(default_factory=dict)
    tool_calls: List[ToolCallRecord] = Field(default_factory=list)

    model_config = ConfigDict(extra="forbid")


class TaskTrajectory(BaseModel):
    """Full trajectory of one task (one user question / one agent run)."""

    task_id: str
    started_at: float = Field(..., description="Unix timestamp")
    ended_at: float = Field(..., description="Unix timestamp")
    model_provider: str = ""
    model_id: str = ""
    success: bool = False
    error_message: Optional[str] = None
    user_input: str = ""
    system_prompt: Optional[str] = None
    tool_names: List[str] = Field(default_factory=list)
    turns: List[TurnRecord] = Field(default_factory=list)
    final_message_text: Optional[str] = None
    total_turns: int = 0
    total_usage: Dict[str, Any] = Field(
        default_factory=lambda: {
            "input": 0,
            "output": 0,
            "total_tokens": 0,
            "cost_total": 0.0,
        }
    )

    model_config = ConfigDict(extra="forbid")

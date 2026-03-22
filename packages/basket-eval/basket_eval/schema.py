"""Task instance schema for evaluation."""

from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field

from basket_trajectory.schema import TaskTrajectory


class OracleType(str, Enum):
    """Types of oracle evaluation."""

    TEST_PASS = "test_pass"
    FILE_DIFF = "file_diff"
    LLM_JUDGE = "llm_judge"
    CUSTOM_SCRIPT = "custom_script"


class TaskSetup(BaseModel):
    """Setup instructions for a task instance."""

    repo_url: Optional[str] = None
    base_ref: Optional[str] = None
    pre_commands: List[str] = Field(default_factory=list)
    working_dir: Optional[str] = None
    env_vars: Dict[str, str] = Field(default_factory=dict)

    model_config = ConfigDict(frozen=True)


class TaskOracle(BaseModel):
    """Oracle for evaluating task completion."""

    type: OracleType
    test_command: Optional[str] = None
    expected_files: Optional[Dict[str, str]] = None
    judge_rubric: Optional[str] = None
    script_path: Optional[str] = None
    expected_exit_code: int = 0

    model_config = ConfigDict(frozen=True)


class TaskInstance(BaseModel):
    """A single evaluation task: setup + prompt + oracle."""

    instance_id: str
    description: str
    setup: TaskSetup = Field(default_factory=TaskSetup)
    prompt: str
    oracle: TaskOracle
    timeout_seconds: int = 300
    tags: List[str] = Field(default_factory=list)
    metadata: Dict[str, Any] = Field(default_factory=dict)

    model_config = ConfigDict(frozen=True)


class EvalResult(BaseModel):
    """Result of evaluating a task instance."""

    instance_id: str
    success: bool
    score: Optional[float] = None
    error_message: Optional[str] = None
    trajectory: Optional[TaskTrajectory] = None
    duration_seconds: float = 0.0
    oracle_output: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)

    model_config = ConfigDict(frozen=True)

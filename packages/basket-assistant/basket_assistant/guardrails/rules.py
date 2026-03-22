"""Guardrail rule definitions."""

from typing import List, Literal, Optional

from pydantic import BaseModel, ConfigDict


class GuardrailResult(BaseModel):
    """Result of a guardrail check."""

    allowed: bool
    rule_id: Optional[str] = None
    message: Optional[str] = None

    model_config = ConfigDict(frozen=True)


class GuardrailRule(BaseModel):
    """A single guardrail rule definition.

    Metadata describing a rule for documentation/serialization purposes.
    Actual enforcement is done by check functions in `checks.py`.
    """

    id: str
    description: str
    tool_names: List[str]  # which tools this rule applies to ("*" for all)
    severity: Literal["block", "warn"] = "block"

    model_config = ConfigDict(frozen=True)

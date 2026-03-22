"""
Guardrails layer: blocks dangerous tool operations before execution.

Provides a composable engine that evaluates check functions against tool calls
and returns allow/block decisions with explanatory messages.
"""

from .checks import (
    DANGEROUS_PATTERNS,
    check_dangerous_commands,
    check_path_outside_workspace,
    check_secret_exposure,
)
from .defaults import create_default_engine
from .engine import CheckFunction, GuardrailEngine
from .rules import GuardrailResult, GuardrailRule

__all__ = [
    # Engine
    "GuardrailEngine",
    "CheckFunction",
    "create_default_engine",
    # Rules / results
    "GuardrailRule",
    "GuardrailResult",
    # Built-in checks
    "check_dangerous_commands",
    "check_path_outside_workspace",
    "check_secret_exposure",
    "DANGEROUS_PATTERNS",
]

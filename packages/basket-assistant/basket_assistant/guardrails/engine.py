"""Guardrail evaluation engine.

The engine holds an ordered list of check functions and evaluates them
sequentially.  The first check that returns ``allowed=False`` wins and
the tool call is blocked.
"""

from typing import Any, Callable, Dict, List, Optional

from .checks import (
    check_dangerous_commands,
    check_path_outside_workspace,
    check_secret_exposure,
)
from .rules import GuardrailResult

# A check function signature: (tool_name, arguments) -> GuardrailResult
CheckFunction = Callable[[str, Dict[str, Any]], GuardrailResult]


class GuardrailEngine:
    """Evaluates guardrail rules against tool calls.

    Attributes:
        workspace_dir: Optional workspace root for path-based checks.
        enabled: Master switch -- when ``False``, all checks are skipped.
    """

    def __init__(
        self,
        checks: Optional[List[CheckFunction]] = None,
        workspace_dir: Optional[str] = None,
        enabled: bool = True,
    ) -> None:
        self._workspace_dir = workspace_dir
        self._enabled = enabled

        if checks is not None:
            self._checks: List[CheckFunction] = list(checks)
        else:
            # Provide sensible defaults
            self._checks = [
                check_dangerous_commands,
                check_secret_exposure,
            ]
            if workspace_dir:
                # Bind workspace_dir via a closure so the check function keeps
                # the two-arg signature expected by the engine.
                ws = workspace_dir  # capture

                def _path_check(
                    tn: str, args: Dict[str, Any]
                ) -> GuardrailResult:
                    return check_path_outside_workspace(tn, args, ws)

                self._checks.append(_path_check)

    # -- Public API ---------------------------------------------------------

    @property
    def enabled(self) -> bool:
        return self._enabled

    @enabled.setter
    def enabled(self, value: bool) -> None:
        self._enabled = value

    @property
    def workspace_dir(self) -> Optional[str]:
        return self._workspace_dir

    @property
    def checks(self) -> List[CheckFunction]:
        """Return a shallow copy of the registered checks."""
        return list(self._checks)

    def evaluate(
        self, tool_name: str, arguments: Dict[str, Any]
    ) -> GuardrailResult:
        """Run all checks; return first blocking result or an allow."""
        if not self._enabled:
            return GuardrailResult(allowed=True)

        for check in self._checks:
            result = check(tool_name, arguments)
            if not result.allowed:
                return result

        return GuardrailResult(allowed=True)

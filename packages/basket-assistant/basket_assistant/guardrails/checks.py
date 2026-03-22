"""Built-in guardrail check functions.

Each check function takes (tool_name, arguments) and returns a GuardrailResult.
Returning ``allowed=False`` blocks the tool call with an explanatory message.
"""

import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from .rules import GuardrailResult

# ---------------------------------------------------------------------------
# Dangerous bash patterns: (regex, human-readable description)
# ---------------------------------------------------------------------------
DANGEROUS_PATTERNS: List[Tuple[str, str]] = [
    (r"\brm\s+(-[rRf]+\s+)*/", "Recursive delete from root"),
    (r"\brm\s+(-[rRf]+\s+)*~", "Recursive delete from home"),
    (r"\bchmod\s+777\b", "Setting world-writable permissions"),
    (r"\bchmod\s+-R\s+777\b", "Recursive world-writable permissions"),
    (r"\bmkfs\b", "Filesystem formatting"),
    (r"\bdd\s+.*of=/dev/", "Direct disk write"),
    (r">\s*/dev/sd[a-z]", "Writing to block device"),
    (r"\bcurl\s+.*\|\s*(ba)?sh\b", "Piping curl to shell"),
    (r"\bwget\s+.*\|\s*(ba)?sh\b", "Piping wget to shell"),
    (r":\(\)\{\s*:\|:&\s*\};:", "Fork bomb"),
]

# ---------------------------------------------------------------------------
# Secret-exposure patterns
# ---------------------------------------------------------------------------
_SECRET_PATTERNS: List[Tuple[str, str]] = [
    (r"\bcat\s+.*\.env\b", "Reading .env file"),
    (r"\becho\s+.*\$[A-Z_]*KEY\b", "Echoing potential API key"),
    (r"\becho\s+.*\$[A-Z_]*SECRET\b", "Echoing potential secret"),
    (r"\becho\s+.*\$[A-Z_]*TOKEN\b", "Echoing potential token"),
    (r"\becho\s+.*\$[A-Z_]*PASSWORD\b", "Echoing potential password"),
    (r"\bprintenv\b", "Printing all environment variables"),
]


def _allowed() -> GuardrailResult:
    """Short-hand for an allow result."""
    return GuardrailResult(allowed=True)


# ---------------------------------------------------------------------------
# Public check functions
# ---------------------------------------------------------------------------


def check_dangerous_commands(
    tool_name: str, arguments: Dict[str, Any]
) -> GuardrailResult:
    """Check bash commands for dangerous patterns."""
    if tool_name != "bash":
        return _allowed()

    command = arguments.get("command", "")
    for pattern, description in DANGEROUS_PATTERNS:
        if re.search(pattern, command):
            return GuardrailResult(
                allowed=False,
                rule_id="dangerous_command",
                message=f"Blocked: {description}. Command: {command[:100]}",
            )
    return _allowed()


def check_path_outside_workspace(
    tool_name: str,
    arguments: Dict[str, Any],
    workspace_dir: Optional[str] = None,
) -> GuardrailResult:
    """Check that file operations don't write outside the workspace."""
    if tool_name not in ("write", "edit"):
        return _allowed()

    if workspace_dir is None:
        return _allowed()  # no workspace restriction configured

    file_path = arguments.get("file_path", "")
    if not file_path:
        return _allowed()

    try:
        resolved = Path(file_path).resolve()
        workspace = Path(workspace_dir).resolve()
        # Use os.path-compatible prefix check (avoids partial-directory matches)
        if not str(resolved).startswith(str(workspace) + "/") and resolved != workspace:
            return GuardrailResult(
                allowed=False,
                rule_id="path_outside_workspace",
                message=(
                    f"Blocked: write to {file_path} is outside workspace {workspace_dir}"
                ),
            )
    except Exception:
        pass

    return _allowed()


def check_secret_exposure(
    tool_name: str, arguments: Dict[str, Any]
) -> GuardrailResult:
    """Check for potential secret exposure in bash commands."""
    if tool_name != "bash":
        return _allowed()

    command = arguments.get("command", "")
    for pattern, description in _SECRET_PATTERNS:
        if re.search(pattern, command, re.IGNORECASE):
            return GuardrailResult(
                allowed=False,
                rule_id="secret_exposure",
                message=f"Blocked: {description}. Command: {command[:100]}",
            )

    return _allowed()

"""Default guardrail configuration and convenience factory."""

from typing import Optional

from .engine import GuardrailEngine


def create_default_engine(
    workspace_dir: Optional[str] = None,
    enabled: bool = True,
) -> GuardrailEngine:
    """Create a ``GuardrailEngine`` with all built-in checks enabled.

    This is the recommended way to obtain an engine instance -- it wires up
    dangerous-command, secret-exposure, and (optionally) workspace-boundary
    checks automatically.

    Args:
        workspace_dir: If provided, file-write operations outside this
            directory are blocked.
        enabled: Master switch.  Pass ``False`` to create a no-op engine.
    """
    return GuardrailEngine(
        workspace_dir=workspace_dir,
        enabled=enabled,
    )

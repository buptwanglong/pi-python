"""Wrap tool execute_fn with subprocess hook runner (tool.execute.before / after)."""

from pathlib import Path
from typing import Any, Callable, Dict

from .hook_runner import HookRunner


def wrap_tool_execute_with_hooks(
    tool_name: str,
    execute_fn: Callable[..., Any],
    hook_runner: HookRunner,
    get_cwd: Callable[[], Path],
) -> Callable[..., Any]:
    """Wrap execute_fn to run tool.execute.before and tool.execute.after hooks (subprocess)."""

    async def wrapped(**kwargs: Any) -> Any:
        input_before = {
            "tool_name": tool_name,
            "tool_call_id": "",
            "arguments": dict(kwargs),
            "cwd": str(get_cwd()),
        }
        output_before: Dict[str, Any] = {"modified_arguments": None}
        result_before = await hook_runner.run(
            "tool.execute.before",
            input_before,
            output=output_before,
            cwd=get_cwd(),
        )
        if result_before.get("permission") == "deny":
            reason = result_before.get("reason") or "Blocked by hook."
            return f"Error: {reason}"
        args = output_before.get("modified_arguments") or kwargs
        if not isinstance(args, dict):
            args = kwargs
        exc_raised: BaseException | None = None
        try:
            result = await execute_fn(**args)
            error_msg = None
        except Exception as e:
            result = None
            error_msg = str(e)
            exc_raised = e
        input_after = {
            "tool_name": tool_name,
            "tool_call_id": "",
            "arguments": args,
            "result": result,
            "error": error_msg,
            "cwd": str(get_cwd()),
        }
        await hook_runner.run(
            "tool.execute.after",
            input_after,
            cwd=get_cwd(),
        )
        if exc_raised is not None:
            raise exc_raised
        return result

    return wrapped


__all__ = ["wrap_tool_execute_with_hooks"]

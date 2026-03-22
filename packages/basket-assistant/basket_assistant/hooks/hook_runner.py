"""
Hook Runner: subprocess-based hook execution (language-agnostic).

Loads hook definitions from hooks.json and/or settings.hooks, runs each hook
as a subprocess with JSON on stdin/stdout. Exit code 2 or permission "deny"
stops further hooks and denies the action.
"""

import asyncio
import json
import logging
import re
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# Exit code that means "deny" (do not run tool / block action)
HOOK_EXIT_DENY = 2

# Claude Code → Basket canonical event name mapping
# Allows users to use either naming convention in hooks.json
HOOK_ALIAS_MAP: dict[str, str] = {
    "PreToolUse": "tool.execute.before",
    "PostToolUse": "tool.execute.after",
    "Stop": "session.ended",
    "Notification": "message.turn_done",
}


def normalize_hook_event(event_name: str) -> str:
    """Normalize a hook event name to its canonical form.

    Maps Claude Code-style names (PreToolUse, PostToolUse, Stop, Notification)
    to Basket canonical names (tool.execute.before, tool.execute.after, etc.).
    Returns the input unchanged if it is already canonical.
    """
    return HOOK_ALIAS_MAP.get(event_name, event_name)


class HookDef:
    """Single hook definition from config."""

    __slots__ = ("command", "timeout", "matcher")

    def __init__(
        self,
        command: str,
        timeout: Optional[int] = None,
        matcher: Optional[str] = None,
    ):
        self.command = command
        self.timeout = timeout
        self.matcher = matcher

    def matches(self, hook_name: str, input_data: Dict[str, Any]) -> bool:
        """Return True if this hook should run for the given event and input."""
        # Normalize hook_name so aliases map to canonical names
        canonical = normalize_hook_event(hook_name)
        if not self.matcher:
            return True
        if canonical in ("tool.execute.before", "tool.execute.after"):
            tool_name = input_data.get("tool_name") or ""
            if re.search(self.matcher, tool_name, re.IGNORECASE):
                return True
            # For bash tool, also match against command string
            if tool_name == "bash":
                cmd = (input_data.get("arguments") or {}).get("command") or ""
                if re.search(self.matcher, cmd):
                    return True
            return False
        return True


def _to_json_safe(obj: Any) -> Any:
    """Recursively convert to JSON-serializable types (Path -> str, Pydantic model_dump, etc.)."""
    if obj is None or isinstance(obj, (bool, int, float, str)):
        return obj
    if isinstance(obj, Path):
        return str(obj)
    if hasattr(obj, "model_dump"):
        return _to_json_safe(obj.model_dump())
    if isinstance(obj, dict):
        return {k: _to_json_safe(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_to_json_safe(x) for x in obj]
    return str(obj)


def _expand_path(s: str) -> str:
    """Expand ~ to home directory in a string (e.g. command line)."""
    if s.startswith("~/"):
        return str(Path.home() / s[2:])
    if s.startswith("~"):
        return str(Path.home() / s[1:])
    return s


def _expand_command(command: str) -> str:
    """Expand ~ in each space-separated token (e.g. ~/.basket/hooks/x.sh or python ~/script.py)."""
    return " ".join(
        _expand_path(part) if part.startswith("~") else part
        for part in command.strip().split()
    )


def _load_hooks_from_file(path: Path) -> Dict[str, List[Dict[str, Any]]]:
    """Load hooks config from a JSON file. Returns event_name -> list of def dicts."""
    if not path.exists() or not path.is_file():
        return {}
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception as e:
        logger.warning("Failed to load hooks file %s: %s", path, e)
        return {}
    hooks = data.get("hooks") or {}
    if not isinstance(hooks, dict):
        return {}
    out: Dict[str, List[Dict[str, Any]]] = {}
    for event_name, defs in hooks.items():
        if not isinstance(defs, list):
            continue
        out[event_name] = [d for d in defs if isinstance(d, dict) and d.get("command")]
    return out


def _merge_hook_defs(
    project: Dict[str, List[Dict[str, Any]]],
    user: Dict[str, List[Dict[str, Any]]],
    settings: Dict[str, List[Dict[str, Any]]],
) -> Dict[str, List[HookDef]]:
    """Merge hook definitions: project first, then user, then settings (append).

    Event names are normalized so Claude Code aliases (PreToolUse, PostToolUse, etc.)
    are merged into their canonical Basket names.
    """
    all_events: Dict[str, List[HookDef]] = {}
    for source in (project, user, settings):
        for event_name, defs in source.items():
            canonical = normalize_hook_event(event_name)
            if canonical not in all_events:
                all_events[canonical] = []
            for d in defs:
                cmd = d.get("command")
                if not cmd:
                    continue
                cmd = _expand_command(cmd)
                all_events[canonical].append(
                    HookDef(
                        command=cmd,
                        timeout=d.get("timeout"),
                        matcher=d.get("matcher"),
                    )
                )
    return all_events


class HookRunner:
    """
    Runs hooks as subprocesses. Loads config from hooks.json and optional settings.hooks.
    """

    def __init__(
        self,
        project_root: Optional[Path] = None,
        settings_hooks: Optional[Dict[str, List[Dict[str, Any]]]] = None,
    ):
        """
        Initialize and load hook config.

        Args:
            project_root: Project directory (for .basket/hooks.json).
            settings_hooks: Optional hooks from settings (e.g. settings.hooks).
        """
        self._project_root = project_root or Path.cwd()
        self._settings_hooks = settings_hooks or {}
        self._hooks: Dict[str, List[HookDef]] = {}
        self._load_config()

    def _load_config(self) -> None:
        """Load and merge hook config from files and settings."""
        project_path = self._project_root / ".basket" / "hooks.json"
        user_path = Path.home() / ".basket" / "hooks.json"
        project = _load_hooks_from_file(project_path)
        user = _load_hooks_from_file(user_path)

        settings_hooks = self._settings_hooks
        if isinstance(settings_hooks, dict):
            # Normalize to same shape as file: event -> list of {command, timeout, matcher}
            pass
        else:
            settings_hooks = {}

        self._hooks = _merge_hook_defs(project, user, settings_hooks)

    async def run(
        self,
        hook_name: str,
        input_data: Dict[str, Any],
        output: Optional[Dict[str, Any]] = None,
        cwd: Optional[Path] = None,
    ) -> Dict[str, Any]:
        """
        Run all hooks for the given event. Subprocess: stdin = one line JSON input,
        stdout = one line JSON output; exit code 2 = deny.

        Args:
            hook_name: Event name (e.g. "tool.execute.before", "session.created").
            input_data: JSON-serializable input for hooks (must not contain non-serializable types).
            output: Optional mutable dict to write modified_arguments etc. into (for before hook).
            cwd: Working directory for subprocesses.

        Returns:
            Result dict with keys: "permission" ("allow" | "deny"), "reason" (if deny),
            "modified_arguments" (if allow and hook returned them). If any hook returns
            deny or exit 2, permission is "deny" and further hooks are not run.
        """
        result: Dict[str, Any] = {
            "permission": "allow",
            "reason": None,
            "modified_arguments": None,
        }
        if output is not None and "modified_arguments" not in output:
            output["modified_arguments"] = None

        # Normalize event name so aliases resolve to canonical keys
        canonical = normalize_hook_event(hook_name)

        defs = self._hooks.get(canonical, [])
        run_cwd = Path(cwd) if cwd else self._project_root
        matched = [d for d in defs if d.matches(canonical, input_data)]
        if defs:
            logger.info(
                "hook run event=%s canonical=%s defs=%d matched=%d",
                hook_name,
                canonical,
                len(defs),
                len(matched),
            )

        # Ensure input is JSON-serializable (Path -> str, Pydantic -> dict, etc.)
        input_copy = _to_json_safe(input_data)
        input_copy["hook_event_name"] = canonical
        if "cwd" not in input_copy:
            input_copy["cwd"] = str(run_cwd)
        input_json = json.dumps(input_copy, ensure_ascii=False)

        for hook_def in defs:
            if not hook_def.matches(canonical, input_data):
                continue
            logger.info("hook exec event=%s command=%s", canonical, hook_def.command)
            try:
                out_json, exit_code = await self._run_one(
                    hook_def, input_json, run_cwd
                )
            except asyncio.TimeoutError:
                logger.warning("Hook timed out: %s %s", canonical, hook_def.command)
                result["permission"] = "deny"
                result["reason"] = "Hook script timed out."
                return result
            except Exception as e:
                logger.warning("Hook failed: %s %s: %s", canonical, hook_def.command, e)
                result["permission"] = "deny"
                result["reason"] = str(e)
                return result

            if exit_code == HOOK_EXIT_DENY:
                result["permission"] = "deny"
                result["reason"] = (out_json or {}).get("reason") or "Hook returned deny (exit 2)."
                logger.info(
                    "hook result event=%s permission=deny reason=%s",
                    canonical,
                    result["reason"],
                )
                return result

            if out_json:
                perm = out_json.get("permission")
                if perm == "deny":
                    result["permission"] = "deny"
                    result["reason"] = out_json.get("reason") or "Hook returned permission deny."
                    logger.info(
                        "hook result event=%s permission=deny reason=%s",
                        canonical,
                        result["reason"],
                    )
                    return result
                if out_json.get("modified_arguments") is not None:
                    result["modified_arguments"] = out_json["modified_arguments"]
                    if output is not None:
                        output["modified_arguments"] = out_json["modified_arguments"]

        if defs:
            logger.info("hook result event=%s permission=allow", canonical)
        return result

    async def _run_one(
        self,
        hook_def: HookDef,
        input_json: str,
        cwd: Path,
    ) -> tuple[Optional[Dict[str, Any]], int]:
        """Spawn one hook subprocess; return (parsed_stdout_json, exit_code)."""
        # Run command via shell so that "python script.py" and "~/.basket/hooks/x.sh" work
        proc = await asyncio.create_subprocess_shell(
            hook_def.command,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.DEVNULL,
            cwd=str(cwd),
        )
        timeout_s = hook_def.timeout if hook_def.timeout is not None else 30
        try:
            stdout_bytes, _ = await asyncio.wait_for(
                proc.communicate(input=input_json.encode("utf-8") + b"\n"),
                timeout=timeout_s,
            )
        except asyncio.TimeoutError:
            try:
                proc.kill()
            except ProcessLookupError:
                pass
            raise
        stdout_str = stdout_bytes.decode("utf-8", errors="replace").strip()
        out_json: Optional[Dict[str, Any]] = None
        if stdout_str:
            for line in stdout_str.splitlines():
                line = line.strip()
                if line:
                    try:
                        out_json = json.loads(line)
                    except json.JSONDecodeError:
                        pass
                    break
        return out_json, proc.returncode or 0

    def get_hook_defs(self, hook_name: str) -> List[HookDef]:
        """Return list of hook definitions for the event (read-only)."""
        return list(self._hooks.get(hook_name, []))

__all__ = [
    "HookRunner",
    "HookDef",
    "HOOK_EXIT_DENY",
    "HOOK_ALIAS_MAP",
    "normalize_hook_event",
    "_merge_hook_defs",
]

"""
Tests for subprocess-based HookRunner (config load, matcher, run, exit 2 = deny).
"""

import asyncio
import json
import tempfile
from pathlib import Path

import pytest

from basket_assistant.extensions.hook_runner import (
    HookRunner,
    HookDef,
    HOOK_EXIT_DENY,
    _load_hooks_from_file,
    _merge_hook_defs,
)


def test_load_hooks_from_file_empty_path():
    """Missing or non-file path returns empty dict."""
    assert _load_hooks_from_file(Path("/nonexistent")) == {}
    with tempfile.NamedTemporaryFile(suffix=".txt", delete=False) as f:
        p = Path(f.name)
    p.unlink()
    assert _load_hooks_from_file(p) == {}


def test_load_hooks_from_file_valid(tmp_path):
    """Valid hooks.json is parsed; hooks without command are skipped."""
    hooks_file = tmp_path / "hooks.json"
    hooks_file.write_text(
        json.dumps({
            "version": 1,
            "hooks": {
                "tool.execute.before": [
                    {"command": "echo allow", "timeout": 5},
                    {"command": "script.sh", "matcher": "read"},
                ],
                "other": [],
                "bad": [{"timeout": 10}],
            }
        }, indent=2),
        encoding="utf-8",
    )
    out = _load_hooks_from_file(hooks_file)
    assert "tool.execute.before" in out
    assert len(out["tool.execute.before"]) == 2
    assert "other" not in out or out["other"] == []
    assert "bad" not in out or len(out.get("bad", [])) == 0


def test_merge_hook_defs():
    """Project, user, settings are merged in order; HookDef created."""
    project = {"e1": [{"command": "p1.sh"}]}
    user = {"e1": [{"command": "u1.sh", "timeout": 3}]}
    settings = {"e2": [{"command": "s1.sh"}]}
    merged = _merge_hook_defs(project, user, settings)
    assert "e1" in merged
    assert len(merged["e1"]) == 2
    assert merged["e1"][0].command.endswith("p1.sh")
    assert merged["e1"][1].command.endswith("u1.sh")
    assert merged["e1"][1].timeout == 3
    assert "e2" in merged
    assert len(merged["e2"]) == 1


def test_hook_def_matches_no_matcher():
    """Without matcher, always matches."""
    d = HookDef("x", matcher=None)
    assert d.matches("tool.execute.before", {"tool_name": "read"}) is True


def test_hook_def_matches_tool_name():
    """Matcher is regex against tool_name."""
    d = HookDef("x", matcher="read")
    assert d.matches("tool.execute.before", {"tool_name": "read"}) is True
    assert d.matches("tool.execute.before", {"tool_name": "bash"}) is False
    d2 = HookDef("x", matcher="read|write")
    assert d2.matches("tool.execute.before", {"tool_name": "write"}) is True


@pytest.mark.asyncio
async def test_hook_runner_run_no_hooks():
    """When no hooks for event, run returns allow."""
    runner = HookRunner(project_root=Path.cwd(), settings_hooks={})
    result = await runner.run("tool.execute.before", {"tool_name": "read", "arguments": {}})
    assert result.get("permission") == "allow"


@pytest.mark.asyncio
async def test_hook_runner_run_allow_script(tmp_path):
    """Script that echoes allow and exits 0 yields allow."""
    script = tmp_path / "allow.sh"
    script.write_text('#!/bin/sh\necho \'{"permission":"allow"}\'\nexit 0\n')
    script.chmod(0o755)
    hooks = {
        "tool.execute.before": [
            {"command": str(script), "timeout": 5},
        ],
    }
    runner = HookRunner(project_root=tmp_path, settings_hooks=hooks)
    result = await runner.run(
        "tool.execute.before",
        {"tool_name": "read", "arguments": {"filePath": "x"}},
        cwd=tmp_path,
    )
    assert result.get("permission") == "allow"


@pytest.mark.asyncio
async def test_hook_runner_run_deny_script(tmp_path):
    """Script that echoes deny and exits 2 yields deny and reason."""
    script = tmp_path / "deny.sh"
    script.write_text(
        '#!/bin/sh\n'
        'echo \'{"permission":"deny","reason":"Blocked by test."}\'\n'
        f'exit {HOOK_EXIT_DENY}\n'
    )
    script.chmod(0o755)
    hooks = {
        "tool.execute.before": [
            {"command": str(script), "timeout": 5},
        ],
    }
    runner = HookRunner(project_root=tmp_path, settings_hooks=hooks)
    result = await runner.run(
        "tool.execute.before",
        {"tool_name": "read", "arguments": {}},
        cwd=tmp_path,
    )
    assert result.get("permission") == "deny"
    assert "Blocked" in (result.get("reason") or "")


@pytest.mark.asyncio
async def test_hook_runner_run_exit_2_without_json(tmp_path):
    """Exit code 2 without valid JSON still yields deny."""
    script = tmp_path / "exit2.sh"
    script.write_text("#!/bin/sh\nexit 2\n")
    script.chmod(0o755)
    hooks = {
        "tool.execute.before": [{"command": str(script), "timeout": 5}],
    }
    runner = HookRunner(project_root=tmp_path, settings_hooks=hooks)
    result = await runner.run(
        "tool.execute.before",
        {"tool_name": "read", "arguments": {}},
        cwd=tmp_path,
    )
    assert result.get("permission") == "deny"


@pytest.mark.asyncio
async def test_hook_runner_run_modified_arguments(tmp_path):
    """Script returning modified_arguments writes to output dict."""
    script = tmp_path / "modify.py"
    script.write_text("""
import json, sys
d = json.load(sys.stdin)
out = {"permission": "allow", "modified_arguments": {"filePath": "other.txt"}}
print(json.dumps(out))
sys.exit(0)
""")
    hooks = {
        "tool.execute.before": [{"command": f"python3 {script}", "timeout": 5}],
    }
    runner = HookRunner(project_root=tmp_path, settings_hooks=hooks)
    output: dict = {"modified_arguments": None}
    result = await runner.run(
        "tool.execute.before",
        {"tool_name": "read", "arguments": {"filePath": "orig.txt"}},
        output=output,
        cwd=tmp_path,
    )
    assert result.get("permission") == "allow"
    assert output.get("modified_arguments") == {"filePath": "other.txt"}


@pytest.mark.asyncio
async def test_hook_runner_matcher_filters(tmp_path):
    """Hook with matcher only runs when tool_name matches."""
    log = tmp_path / "log.txt"
    script = tmp_path / "log.sh"
    script.write_text(f'#!/bin/sh\necho ran >> {log}\necho \'{{"permission":"allow"}}\'\nexit 0\n')
    script.chmod(0o755)
    hooks = {
        "tool.execute.before": [
            {"command": str(script), "matcher": "read"},
        ],
    }
    runner = HookRunner(project_root=tmp_path, settings_hooks=hooks)
    await runner.run(
        "tool.execute.before",
        {"tool_name": "read", "arguments": {}},
        cwd=tmp_path,
    )
    assert log.read_text().strip() == "ran"
    log.write_text("")
    await runner.run(
        "tool.execute.before",
        {"tool_name": "bash", "arguments": {}},
        cwd=tmp_path,
    )
    assert log.read_text().strip() == ""


# -------------------------------------------------------
# Hook event alias tests (Claude Code naming alignment)
# -------------------------------------------------------

def test_hook_def_matches_pretooluse_alias():
    """PreToolUse alias resolves to tool.execute.before."""
    d = HookDef("x", matcher="read")
    assert d.matches("PreToolUse", {"tool_name": "read"}) is True
    assert d.matches("PreToolUse", {"tool_name": "bash"}) is False


def test_hook_def_matches_posttooluse_alias():
    """PostToolUse alias resolves to tool.execute.after."""
    d = HookDef("x", matcher="read")
    assert d.matches("PostToolUse", {"tool_name": "read"}) is True
    assert d.matches("PostToolUse", {"tool_name": "bash"}) is False


@pytest.mark.asyncio
async def test_hook_runner_pretooluse_alias(tmp_path):
    """Hooks registered under PreToolUse fire for tool.execute.before events."""
    marker = tmp_path / "pretooluse_ran.marker"
    script = tmp_path / "allow.sh"
    script.write_text(
        f'#!/bin/sh\ntouch {marker}\necho \'{{"permission":"allow"}}\'\nexit 0\n'
    )
    script.chmod(0o755)
    hooks = {
        "PreToolUse": [
            {"command": str(script), "timeout": 5},
        ],
    }
    runner = HookRunner(project_root=tmp_path, settings_hooks=hooks)
    result = await runner.run(
        "tool.execute.before",
        {"tool_name": "read", "arguments": {}},
        cwd=tmp_path,
    )
    assert marker.exists(), "Hook script should have executed (marker file missing)"
    assert result.get("permission") == "allow"


@pytest.mark.asyncio
async def test_hook_runner_posttooluse_alias(tmp_path):
    """Hooks registered under PostToolUse fire for tool.execute.after events."""
    marker = tmp_path / "posttooluse_ran.marker"
    script = tmp_path / "after.sh"
    script.write_text(
        f'#!/bin/sh\ntouch {marker}\necho \'{{"permission":"allow"}}\'\nexit 0\n'
    )
    script.chmod(0o755)
    hooks = {
        "PostToolUse": [
            {"command": str(script), "timeout": 5},
        ],
    }
    runner = HookRunner(project_root=tmp_path, settings_hooks=hooks)
    result = await runner.run(
        "tool.execute.after",
        {"tool_name": "read", "arguments": {}},
        cwd=tmp_path,
    )
    assert marker.exists(), "Hook script should have executed (marker file missing)"
    assert result.get("permission") == "allow"


@pytest.mark.asyncio
async def test_hook_runner_stop_alias(tmp_path):
    """Hooks registered under Stop fire for session.ended events."""
    marker = tmp_path / "stop_ran.marker"
    script = tmp_path / "stop.sh"
    script.write_text(
        f'#!/bin/sh\ntouch {marker}\necho \'{{"permission":"allow"}}\'\nexit 0\n'
    )
    script.chmod(0o755)
    hooks = {
        "Stop": [
            {"command": str(script), "timeout": 5},
        ],
    }
    runner = HookRunner(project_root=tmp_path, settings_hooks=hooks)
    result = await runner.run(
        "session.ended",
        {},
        cwd=tmp_path,
    )
    assert marker.exists(), "Hook script should have executed (marker file missing)"
    assert result.get("permission") == "allow"


def test_merge_hook_defs_normalizes_aliases():
    """Merged hooks normalize Claude Code aliases to canonical names."""
    project = {"PreToolUse": [{"command": "pre.sh"}]}
    user = {"PostToolUse": [{"command": "post.sh"}]}
    settings = {"tool.execute.before": [{"command": "canonical.sh"}]}

    merged = _merge_hook_defs(project, user, settings)

    # Both PreToolUse and tool.execute.before should be under same canonical key
    assert "tool.execute.before" in merged
    assert len(merged["tool.execute.before"]) == 2
    assert "tool.execute.after" in merged
    assert len(merged["tool.execute.after"]) == 1

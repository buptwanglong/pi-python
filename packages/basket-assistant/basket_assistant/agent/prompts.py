"""System prompts, plan mode suffix, and skills/agents directory resolution."""

from pathlib import Path
from typing import Any, Dict, List, Optional

from ..core import SubAgentConfig, get_skill_full_content, load_agents_from_dirs
from ..core.workspace_bootstrap import load_workspace_sections, resolve_workspace_dir


def get_agents_dirs(settings: Any) -> List[Path]:
    """Resolve agents directories; default ~/.basket/agents and ./.basket/agents."""
    if getattr(settings, "agents_dirs", None):
        return [Path(d).expanduser().resolve() for d in settings.agents_dirs]
    return [
        Path.home() / ".basket" / "agents",
        Path.cwd() / ".basket" / "agents",
    ]


def get_subagent_configs(agent: Any) -> Dict[str, SubAgentConfig]:
    """Merge settings.agents with agents loaded from .basket/agents/*.md; later overrides.
    Excludes default_agent so the main agent is not listed as a Task subagent.
    """
    out: Dict[str, SubAgentConfig] = {}
    for k, v in agent.settings.agents.items():
        out[k] = v
    for k, v in load_agents_from_dirs(get_agents_dirs(agent.settings)).items():
        out[k] = v
    default_agent = getattr(agent.settings, "default_agent", None)
    if default_agent and default_agent in out:
        out = {k: v for k, v in out.items() if k != default_agent}
    return out


def get_skills_dirs(settings: Any) -> List[Path]:
    """Resolve skills directories; default includes Basket, OpenCode, Claude, Agents paths."""
    if getattr(settings, "skills_dirs", None):
        return [Path(d).expanduser().resolve() for d in settings.skills_dirs]
    return [
        Path.home() / ".basket" / "skills",
        Path.cwd() / ".basket" / "skills",
        Path.home() / ".config" / "opencode" / "skills",
        Path.cwd() / ".opencode" / "skills",
        Path.home() / ".claude" / "skills",
        Path.cwd() / ".claude" / "skills",
        Path.home() / ".agents" / "skills",
        Path.cwd() / ".agents" / "skills",
    ]


# Tool usage block appended to every base prompt (with or without workspace).
_TOOLS_SYSTEM_BLOCK = """You have access to tools to read, write, and edit files, execute shell commands, and search for code.

When using tools:
- Use 'read' to read file contents
- Use 'write' to create or overwrite files
- Use 'edit' to make precise changes to existing files
- Use 'bash' to run shell commands (git, npm, pytest, etc.)
- Use 'grep' to search for patterns in files
- Use 'web_search' to search the web
- Use 'web_fetch' to fetch web content
- Use 'todo_write' to write todos
- Use 'ask_user_question' to ask the user a question

You have a `skill` tool to discover and load reusable skills by name; use it when you need instructions for a specific task. The skill tool's description lists available skills.

Always explain what you're doing before using tools.
"""


def get_system_prompt_base(settings: Optional[Any] = None) -> str:
    """
    Get the base system prompt for the agent.

    When settings is None, loads via default SettingsManager (backward compatibility).
    When workspace_dir is set and skip_bootstrap is False, composes from AGENTS.md,
    IDENTITY.md, SOUL.md, USER.md plus the tools block; otherwise returns the
    built-in coding assistant prompt plus the tools block.
    """
    if settings is None:
        from ..core import SettingsManager
        settings = SettingsManager().load()
    if getattr(settings, "skip_bootstrap", False):
        return _builtin_base_prompt()
    workspace_dir = resolve_workspace_dir(settings)
    if workspace_dir is None:
        return _builtin_base_prompt()
    sections = load_workspace_sections(workspace_dir, skip_bootstrap=False)
    if not sections:
        return _builtin_base_prompt()
    parts = []
    for key, title in [
        ("identity", "Identity"),
        ("soul", "Soul (persona & boundaries)"),
        ("agents", "Operating instructions"),
        ("user", "User context"),
        ("tools", "Tools & environment notes"),
        ("memory", "Memory"),
    ]:
        if key in sections and sections[key]:
            parts.append(f"## {title}\n\n{sections[key]}")
    composed = "\n\n".join(parts)
    return composed + "\n\n---\n\n" + _TOOLS_SYSTEM_BLOCK


def _builtin_base_prompt() -> str:
    """Built-in prompt when no workspace or skip_bootstrap."""
    return "You are a helpful coding assistant. " + _TOOLS_SYSTEM_BLOCK


def get_plan_mode_prompt_suffix() -> str:
    """Append this to system prompt when plan mode is on."""
    return """

---
## Plan mode (read-only)

You are in **Plan mode**. You must only analyze and plan; do not modify files, run shell commands, or change session state.

- **Allowed:** read files, grep, web search/fetch, load skills. Use these to research the codebase and produce a plan.
- **Forbidden:** write, edit, bash, todo_write. If you attempt them, the tool will return a message that the action is disabled.

Your response must include:
1. **Analysis:** Findings and reasoning (what you inspected, current architecture, relevant docs).
2. **Plan:** A numbered list of implementation steps. The **last step** must be to present the plan for user approval. Do not implement the plan until the user has approved it.
"""


def get_system_prompt_for_run(
    agent: Any, invoked_skill_id: Optional[str] = None
) -> str:
    """System prompt for this run; if invoked_skill_id set, append that skill's full content."""
    prompt = agent._default_system_prompt
    if invoked_skill_id:
        dirs = get_skills_dirs(agent.settings)
        full = get_skill_full_content(invoked_skill_id, dirs)
        if full:
            prompt = prompt + "\n\n---\n\n## Active skill: " + invoked_skill_id + "\n\n" + full
    if agent._plan_mode:
        prompt = prompt + get_plan_mode_prompt_suffix()
    return prompt

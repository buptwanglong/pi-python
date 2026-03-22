"""System prompts, plan mode suffix, and skills/agents directory resolution."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Dict, List, Optional

from ..core import Settings, SubAgentConfig, get_skill_full_content, load_agents_from_dirs
from ..core.settings.resolver import (
    get_agent_root,
    get_agents_dirs,
)

if TYPE_CHECKING:
    from ._protocol import AssistantAgentProtocol

from ..core.loader.workspace_bootstrap import (
    load_daily_memory,
    load_workspace_sections,
    resolve_workspace_dir,
)
from ..skills.registry import get_builtin_skill_roots


# get_agents_dirs and get_agent_root are imported from core.settings.resolver
# and re-exported here for backward compatibility with callers that use prompts.get_agents_dirs().


def get_subagent_configs(agent: AssistantAgentProtocol) -> Dict[str, SubAgentConfig]:
    """Merge settings.agents with agents loaded from .basket/agents/*.md; later overrides.
    Excludes default_agent so the main agent is not listed as a Task subagent.
    """
    out: Dict[str, SubAgentConfig] = {}
    for k, v in agent.settings.agents.items():
        out[k] = v
    for k, v in load_agents_from_dirs(get_agents_dirs(agent.settings)).items():
        out[k] = v
    default_agent = agent.settings.default_agent
    if default_agent and default_agent in out:
        out = {k: v for k, v in out.items() if k != default_agent}
    return out


def get_skills_dirs(
    settings: Settings, plugin_skill_dirs: Optional[List[Path]] = None
) -> List[Path]:
    """Resolve skills directories: package builtin roots, ~/.basket/skills, cwd/.basket/skills, plugins.

    ``settings.skills_dirs`` is ignored (fixed layout); use symlinks under ~/.basket/skills if needed.
    Builtin roots come from ``skills.registry``; later dirs override earlier for the same skill id.
    """
    dirs: List[Path] = list(get_builtin_skill_roots())
    dirs.extend(
        [
            Path.home() / ".basket" / "skills",
            Path.cwd() / ".basket" / "skills",
        ]
    )
    if plugin_skill_dirs:
        dirs.extend(plugin_skill_dirs)
    return dirs


def get_slash_commands_dirs(plugin_commands_dirs: Optional[List[Path]] = None) -> List[Path]:
    """Fixed dirs for declarative slash commands (*.md). No settings override."""
    dirs: List[Path] = [
        Path.home() / ".basket" / "commands",
        Path.cwd() / ".basket" / "commands",
    ]
    if plugin_commands_dirs:
        dirs.extend(plugin_commands_dirs)
    return dirs


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


SECTION_ORDER = [
    ("identity", "Identity"),
    ("soul", "Soul (persona & boundaries)"),
    ("agents", "Operating instructions"),
    ("user", "User context"),
    ("tools", "Tools & environment notes"),
    ("memory", "Memory"),
    ("bootstrap", "Bootstrap"),
    ("boot", "Boot"),
    ("heartbeat", "Heartbeat"),
]


def compose_system_prompt_from_workspace(
    workspace_dir: Path,
    skip_bootstrap: bool = False,
    include_daily_memory: bool = True,
) -> str:
    """
    Compose system prompt from workspace md files and optional daily memory.
    Returns assembled sections plus _TOOLS_SYSTEM_BLOCK. Used by main agent and run_subagent.
    """
    sections = load_workspace_sections(workspace_dir, skip_bootstrap=skip_bootstrap)
    if include_daily_memory:
        daily = load_daily_memory(workspace_dir)
        if daily:
            existing = sections.get("memory", "")
            sections["memory"] = (existing + "\n\n" + daily).strip() if existing else daily
    parts = []
    for key, title in SECTION_ORDER:
        if key in sections and sections[key]:
            parts.append(f"## {title}\n\n{sections[key]}")
    if not parts:
        return _builtin_base_prompt()
    composed = "\n\n".join(parts)
    return composed + "\n\n---\n\n" + _TOOLS_SYSTEM_BLOCK


def _resolve_main_agent_workspace_dir(settings: Settings) -> Optional[Path]:
    """
    Resolve workspace path for main agent: agents[default_agent].workspace_dir if set and valid,
    else global settings.workspace_dir (or default ~/.basket/workspace via resolve_workspace_dir).
    """
    default_agent = settings.default_agent
    agents = settings.agents
    if default_agent and default_agent in agents:
        cfg = agents[default_agent]
        raw = cfg.workspace_dir
        if raw and str(raw).strip():
            path = Path(str(raw).strip()).expanduser().resolve()
            if path.exists() and path.is_dir():
                return path
            path.mkdir(parents=True, exist_ok=True)
            from ..core.loader.workspace_bootstrap import ensure_workspace_default_fill
            ensure_workspace_default_fill(path)
            return path
    return resolve_workspace_dir(settings)


def get_system_prompt_base(settings: Optional[Settings] = None) -> str:
    """
    Get the base system prompt for the agent.

    When settings is None, loads via default SettingsManager (backward compatibility).
    Workspace is always used: agents[default_agent].workspace_dir overrides global workspace_dir;
    when unset, default ~/.basket/workspace is used and default-filled. When skip_bootstrap is True,
    returns built-in prompt without loading workspace content.
    """
    if settings is None:
        from ..core import SettingsManager
        settings = SettingsManager().load()
    if getattr(settings, "skip_bootstrap", False):
        return _builtin_base_prompt()
    workspace_dir = _resolve_main_agent_workspace_dir(settings)
    if workspace_dir is None:
        return _builtin_base_prompt()
    return compose_system_prompt_from_workspace(
        workspace_dir,
        skip_bootstrap=False,
        include_daily_memory=True,
    )


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
    agent: AssistantAgentProtocol, invoked_skill_id: Optional[str] = None
) -> str:
    """System prompt for this run; if invoked_skill_id set, append that skill's full content."""
    prompt = agent._default_system_prompt
    if invoked_skill_id:
        plugin_skill_dirs = (
            agent._plugin_loader.get_all_skill_dirs()
            if hasattr(agent, "_plugin_loader") and agent._plugin_loader
            else None
        )
        dirs = get_skills_dirs(agent.settings, plugin_skill_dirs=plugin_skill_dirs)
        full = get_skill_full_content(invoked_skill_id, dirs)
        if full:
            prompt = prompt + "\n\n---\n\n## Active skill: " + invoked_skill_id + "\n\n" + full
    if agent._plan_mode:
        prompt = prompt + get_plan_mode_prompt_suffix()
    return prompt

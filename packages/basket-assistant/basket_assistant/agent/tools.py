"""Tool list, subagent filter/run, hook wrapper, and tool registration."""

from __future__ import annotations

import time
from pathlib import Path
from typing import TYPE_CHECKING, Dict, List

from basket_agent import Agent
from basket_ai.api import get_model
from basket_ai.types import Context, UserMessage

from ..core import SubAgentConfig
from ..core.workspace_bootstrap import ensure_workspace_default_fill
from ..hooks.tool_hooks import wrap_tool_execute_with_hooks
from ..guardrails.engine import GuardrailEngine

if TYPE_CHECKING:
    from ._protocol import AssistantAgentProtocol
from ..tools import (
    BUILT_IN_TOOLS,
    create_ask_user_question_tool,
    create_parallel_task_tool,
    create_skill_tool,
    create_task_tool,
    create_todo_write_tool,
    create_web_search_tool,
)

from . import prompts

PLAN_MODE_FORBIDDEN_TOOLS = frozenset({"write", "edit", "bash", "todo_write"})
PLAN_MODE_DISABLED_MESSAGE = (
    "Plan mode is on. This action is disabled. Only analysis and planning are allowed."
)


def _wrap_execute_fn_for_plan_mode(original_fn, get_plan_mode):
    """Return an async wrapper that runs original_fn unless plan mode is on."""

    async def wrapped(**kwargs):
        if get_plan_mode():
            return PLAN_MODE_DISABLED_MESSAGE
        return await original_fn(**kwargs)

    return wrapped


def _wrap_execute_fn_for_guardrails(original_fn, engine: GuardrailEngine, tool_name: str):
    """Return an async wrapper that checks guardrails before execution."""

    async def wrapped(**kwargs):
        result = engine.evaluate(tool_name, kwargs)
        if not result.allowed:
            return f"⛔ Guardrail blocked: {result.message}"
        return await original_fn(**kwargs)

    return wrapped


def _get_plugin_skill_dirs(agent: AssistantAgentProtocol) -> list:
    """Return plugin skill dirs from agent's plugin loader, or empty list."""
    loader = agent._plugin_loader
    return loader.get_all_skill_dirs() if loader else []


def get_registerable_tools(agent: AssistantAgentProtocol) -> List[dict]:
    """Return list of tool dicts (name, description, parameters, execute_fn) as used in register_tools."""
    include = agent.settings.skills_include or None
    if include is not None and len(agent.settings.skills_include) == 0:
        include = None
    skill_tool = create_skill_tool(
        lambda: prompts.get_skills_dirs(
            agent.settings, plugin_skill_dirs=_get_plugin_skill_dirs(agent)
        ),
        include,
    )
    ctx = agent.build_tool_context()
    configs = prompts.get_subagent_configs(agent)
    extra: List[dict] = [skill_tool]
    if configs:
        extra.append(create_task_tool(ctx))
        extra.append(create_parallel_task_tool(ctx))
    return list(BUILT_IN_TOOLS) + extra


def filter_tools_for_subagent(agent: AssistantAgentProtocol, cfg: SubAgentConfig) -> List[dict]:
    """Return tool dicts allowed for this subagent; cfg.tools None = all."""
    tools = get_registerable_tools(agent)
    if cfg.tools is None:
        return tools
    return [t for t in tools if cfg.tools.get(t["name"], False)]


def get_subagent_display_description(agent: AssistantAgentProtocol, name: str, cfg: SubAgentConfig) -> str:
    """Display label for a subagent: first paragraph of workspace AGENTS.md, else name."""
    try:
        workspace_path = _resolve_subagent_workspace_path(agent, name, cfg)
        agents_md = workspace_path / "AGENTS.md"
        if agents_md.exists() and agents_md.is_file():
            text = agents_md.read_text(encoding="utf-8").strip()
            if text:
                first = text.split("\n\n")[0].strip()[:200]
                if first:
                    return first
    except Exception:
        pass
    return name


def _resolve_subagent_workspace_path(agent: AssistantAgentProtocol, subagent_name: str, cfg: SubAgentConfig) -> Path:
    """Resolve workspace path for subagent: cfg.workspace_dir, else cfg.agent_dir/workspace, else default agents_dir/<name>/workspace."""
    raw = cfg.workspace_dir
    if raw and str(raw).strip():
        path = Path(str(raw).strip()).expanduser().resolve()
        if path.exists() and path.is_dir():
            return path
        path.mkdir(parents=True, exist_ok=True)
        return path
    agent_dir_raw = cfg.agent_dir
    if agent_dir_raw and str(agent_dir_raw).strip():
        path = Path(str(agent_dir_raw).strip()).expanduser().resolve() / "workspace"
        path.mkdir(parents=True, exist_ok=True)
        ensure_workspace_default_fill(path)
        return path
    dirs = prompts.get_agents_dirs(agent.settings)
    if not dirs:
        default_base = Path.home() / ".basket" / "agents"
        default_base.mkdir(parents=True, exist_ok=True)
        path = default_base / subagent_name / "workspace"
    else:
        path = dirs[0] / subagent_name / "workspace"
    path.mkdir(parents=True, exist_ok=True)
    ensure_workspace_default_fill(path)
    return path


async def run_subagent(agent: AssistantAgentProtocol, subagent_name: str, user_prompt: str) -> str:
    """Run a subagent with the given prompt; returns last assistant text.
    Subagent system prompt is built from workspace (OpenClaw-style md files); when workspace_dir
    is unset, default ~/.basket/agents/<name>/ is used and default-filled.
    """
    configs = prompts.get_subagent_configs(agent)
    cfg = configs.get(subagent_name)
    if not cfg:
        available = ", ".join(configs) if configs else "none"
        return f'SubAgent "{subagent_name}" not found. Available: {available}'

    workspace_path = _resolve_subagent_workspace_path(agent, subagent_name, cfg)
    ensure_workspace_default_fill(workspace_path)
    system_prompt = prompts.compose_system_prompt_from_workspace(
        workspace_path,
        skip_bootstrap=False,
        include_daily_memory=True,
    )

    if cfg.model and isinstance(cfg.model, dict):
        model_kwargs: dict = {
            "context_window": cfg.model.get("context_window", agent.settings.model.context_window),
            "max_tokens": cfg.model.get("max_tokens", agent.settings.model.max_tokens),
        }
        if agent.settings.model.base_url:
            model_kwargs["base_url"] = agent.settings.model.base_url
        model = get_model(
            cfg.model.get("provider", agent.settings.model.provider),
            cfg.model.get("model_id", agent.settings.model.model_id),
            **model_kwargs,
        )
    else:
        model = agent.model

    context = Context(
        systemPrompt=system_prompt,
        messages=[
            UserMessage(
                role="user",
                content=user_prompt,
                timestamp=int(time.time() * 1000),
            )
        ],
    )
    sub_agent = Agent(model, context)
    sub_agent.max_turns = agent.settings.agent.max_turns
    for t in filter_tools_for_subagent(agent, cfg):
        sub_agent.register_tool(
            name=t["name"],
            description=t["description"],
            parameters=t["parameters"],
            execute_fn=t["execute_fn"],
        )

    state = await sub_agent.run(stream_llm_events=False)

    for msg in reversed(state.context.messages):
        if getattr(msg, "role", None) == "assistant" and hasattr(msg, "content"):
            content = getattr(msg, "content", [])
            texts = []
            for block in content:
                if getattr(block, "type", None) == "text" and hasattr(block, "text"):
                    texts.append(block.text)
            if texts:
                return "\n".join(texts)
    return "(No response)"


def wrap_tool_with_hooks(agent: AssistantAgentProtocol, name: str, execute_fn):
    """Wrap execute_fn with tool.execute.before / after hooks if HookRunner is present."""
    runner = agent.hook_runner
    if runner is None:
        return execute_fn
    return wrap_tool_execute_with_hooks(
        name,
        execute_fn,
        runner,
        get_cwd=lambda: Path.cwd(),
    )


def register_tools(agent: AssistantAgentProtocol) -> None:
    """Register all built-in tools with the agent.

    Wrapping order (outermost runs first):
        plan_mode → guardrails → hooks → original_fn
    """
    ctx = agent.build_tool_context()
    get_plan = lambda: agent._plan_mode
    engine = agent._guardrail_engine

    def _apply_guardrails(fn, name):
        if engine is not None:
            return _wrap_execute_fn_for_guardrails(fn, engine, name)
        return fn

    for tool in BUILT_IN_TOOLS:
        name = tool["name"]
        fn = tool["execute_fn"]
        fn = wrap_tool_with_hooks(agent, name, fn)
        fn = _apply_guardrails(fn, name)
        if name in PLAN_MODE_FORBIDDEN_TOOLS:
            fn = _wrap_execute_fn_for_plan_mode(fn, get_plan)
        agent.agent.register_tool(
            name=name,
            description=tool["description"],
            parameters=tool["parameters"],
            execute_fn=fn,
        )
    include = agent.settings.skills_include or None
    if include is not None and len(agent.settings.skills_include) == 0:
        include = None
    skill_tool = create_skill_tool(
        lambda: prompts.get_skills_dirs(
            agent.settings, plugin_skill_dirs=_get_plugin_skill_dirs(agent)
        ),
        include,
    )
    fn = wrap_tool_with_hooks(agent, skill_tool["name"], skill_tool["execute_fn"])
    fn = _apply_guardrails(fn, skill_tool["name"])
    agent.agent.register_tool(
        name=skill_tool["name"],
        description=skill_tool["description"],
        parameters=skill_tool["parameters"],
        execute_fn=fn,
    )
    configs = prompts.get_subagent_configs(agent)
    if configs:
        task_tool = create_task_tool(ctx)
        fn = wrap_tool_with_hooks(agent, task_tool["name"], task_tool["execute_fn"])
        fn = _apply_guardrails(fn, task_tool["name"])
        agent.agent.register_tool(
            name=task_tool["name"],
            description=task_tool["description"],
            parameters=task_tool["parameters"],
            execute_fn=fn,
        )
        parallel_tool = create_parallel_task_tool(ctx)
        fn = wrap_tool_with_hooks(agent, parallel_tool["name"], parallel_tool["execute_fn"])
        fn = _apply_guardrails(fn, parallel_tool["name"])
        agent.agent.register_tool(
            name=parallel_tool["name"],
            description=parallel_tool["description"],
            parameters=parallel_tool["parameters"],
            execute_fn=fn,
        )
    web_search_tool = create_web_search_tool(agent.settings)
    fn = wrap_tool_with_hooks(
        agent, web_search_tool["name"], web_search_tool["execute_fn"]
    )
    fn = _apply_guardrails(fn, web_search_tool["name"])
    agent.agent.register_tool(
        name=web_search_tool["name"],
        description=web_search_tool["description"],
        parameters=web_search_tool["parameters"],
        execute_fn=fn,
    )
    todo_tool = create_todo_write_tool(ctx)
    todo_fn = todo_tool["execute_fn"]
    todo_fn = wrap_tool_with_hooks(agent, todo_tool["name"], todo_fn)
    todo_fn = _apply_guardrails(todo_fn, todo_tool["name"])
    if "todo_write" in PLAN_MODE_FORBIDDEN_TOOLS:
        todo_fn = _wrap_execute_fn_for_plan_mode(todo_fn, get_plan)
    agent.agent.register_tool(
        name=todo_tool["name"],
        description=todo_tool["description"],
        parameters=todo_tool["parameters"],
        execute_fn=todo_fn,
    )
    ask_tool = create_ask_user_question_tool(ctx)
    fn = wrap_tool_with_hooks(agent, ask_tool["name"], ask_tool["execute_fn"])
    fn = _apply_guardrails(fn, ask_tool["name"])
    agent.agent.register_tool(
        name=ask_tool["name"],
        description=ask_tool["description"],
        parameters=ask_tool["parameters"],
        execute_fn=fn,
    )

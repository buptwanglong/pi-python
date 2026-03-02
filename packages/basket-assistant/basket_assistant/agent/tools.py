"""Tool list, subagent filter/run, hook wrapper, and tool registration."""

import time
from pathlib import Path
from typing import Any, Dict, List

from basket_agent import Agent
from basket_ai.api import get_model
from basket_ai.types import Context, UserMessage

from ..core import SubAgentConfig
from ..extensions.api import _wrap_tool_execute_with_hooks
from ..tools import (
    BUILT_IN_TOOLS,
    create_ask_user_question_tool,
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


def get_registerable_tools(agent: Any) -> List[dict]:
    """Return list of tool dicts (name, description, parameters, execute_fn) as used in register_tools."""
    include = agent.settings.skills_include or None
    if include is not None and len(agent.settings.skills_include) == 0:
        include = None
    skill_tool = create_skill_tool(
        lambda: prompts.get_skills_dirs(agent.settings), include
    )
    return list(BUILT_IN_TOOLS) + [skill_tool]


def filter_tools_for_subagent(agent: Any, cfg: SubAgentConfig) -> List[dict]:
    """Return tool dicts allowed for this subagent; cfg.tools None = all."""
    tools = get_registerable_tools(agent)
    if cfg.tools is None:
        return tools
    return [t for t in tools if cfg.tools.get(t["name"], False)]


async def run_subagent(agent: Any, subagent_name: str, user_prompt: str) -> str:
    """Run a subagent with the given prompt; returns last assistant text."""
    configs = prompts.get_subagent_configs(agent)
    cfg = configs.get(subagent_name)
    if not cfg:
        available = ", ".join(configs) if configs else "none"
        return f'SubAgent "{subagent_name}" not found. Available: {available}'

    if cfg.model and isinstance(cfg.model, dict):
        model_kwargs: dict = {}
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
        systemPrompt=cfg.prompt,
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


def wrap_tool_with_hooks(agent: Any, name: str, execute_fn):
    """Wrap execute_fn with tool.execute.before / after hooks if HookRunner is present."""
    runner = getattr(agent.extension_loader, "hook_runner", None)
    if runner is None:
        return execute_fn
    return _wrap_tool_execute_with_hooks(
        name,
        execute_fn,
        runner,
        get_cwd=lambda: Path.cwd(),
    )


def register_tools(agent: Any) -> None:
    """Register all built-in tools with the agent. In plan mode, write/edit/bash/todo_write are no-ops."""
    get_plan = lambda: agent._plan_mode
    for tool in BUILT_IN_TOOLS:
        name = tool["name"]
        fn = tool["execute_fn"]
        fn = wrap_tool_with_hooks(agent, name, fn)
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
        lambda: prompts.get_skills_dirs(agent.settings), include
    )
    fn = wrap_tool_with_hooks(agent, skill_tool["name"], skill_tool["execute_fn"])
    agent.agent.register_tool(
        name=skill_tool["name"],
        description=skill_tool["description"],
        parameters=skill_tool["parameters"],
        execute_fn=fn,
    )
    configs = prompts.get_subagent_configs(agent)
    if configs:
        task_tool = create_task_tool(agent)
        fn = wrap_tool_with_hooks(agent, task_tool["name"], task_tool["execute_fn"])
        agent.agent.register_tool(
            name=task_tool["name"],
            description=task_tool["description"],
            parameters=task_tool["parameters"],
            execute_fn=fn,
        )
    web_search_tool = create_web_search_tool(agent.settings)
    fn = wrap_tool_with_hooks(
        agent, web_search_tool["name"], web_search_tool["execute_fn"]
    )
    agent.agent.register_tool(
        name=web_search_tool["name"],
        description=web_search_tool["description"],
        parameters=web_search_tool["parameters"],
        execute_fn=fn,
    )
    todo_tool = create_todo_write_tool(agent)
    todo_fn = todo_tool["execute_fn"]
    todo_fn = wrap_tool_with_hooks(agent, todo_tool["name"], todo_fn)
    if "todo_write" in PLAN_MODE_FORBIDDEN_TOOLS:
        todo_fn = _wrap_execute_fn_for_plan_mode(todo_fn, get_plan)
    agent.agent.register_tool(
        name=todo_tool["name"],
        description=todo_tool["description"],
        parameters=todo_tool["parameters"],
        execute_fn=todo_fn,
    )
    ask_tool = create_ask_user_question_tool(agent)
    fn = wrap_tool_with_hooks(agent, ask_tool["name"], ask_tool["execute_fn"])
    agent.agent.register_tool(
        name=ask_tool["name"],
        description=ask_tool["description"],
        parameters=ask_tool["parameters"],
        execute_fn=fn,
    )

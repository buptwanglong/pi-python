"""
Main entry point for the Basket CLI.
"""

import asyncio
import copy
import json
import logging
import os
import sys
import time
from pathlib import Path
from typing import Dict, List, Optional

from basket_agent import Agent
from basket_ai.api import get_model
from basket_ai.types import Context, TextContent, UserMessage

from .core import SettingsManager, SessionManager, SubAgentConfig, load_agents_from_dirs
from .extensions import ExtensionLoader
from .core import get_skill_full_content, get_skills_index
from .tools import (
    BUILT_IN_TOOLS,
    create_ask_user_question_tool,
    create_skill_tool,
    create_task_tool,
    create_todo_write_tool,
    create_web_search_tool,
)

logger = logging.getLogger(__name__)

# Tools disabled in plan mode (read-only: read, grep, web_fetch, web_search, skill)
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


class CodingAgent:
    """
    Main coding agent class.

    Manages the agent lifecycle, tools, and user interaction.
    """

    def __init__(self, settings_manager: Optional[SettingsManager] = None, load_extensions: bool = True):
        """
        Initialize the coding agent.

        Args:
            settings_manager: Optional settings manager (uses default if None)
            load_extensions: Whether to load extensions at startup
        """
        self.settings_manager = settings_manager or SettingsManager()
        self.settings = self.settings_manager.load()

        # Apply api_keys from settings to env so providers (e.g. Anthropic) can use them
        for key, value in self.settings.api_keys.items():
            if value:
                os.environ[key] = value

        # Create session manager
        sessions_dir = Path(self.settings.sessions_dir).expanduser()
        self.session_manager = SessionManager(sessions_dir)

        # Initialize model (optionally with custom base_url from settings)
        model_kwargs: dict = {}
        if self.settings.model.base_url:
            model_kwargs["base_url"] = self.settings.model.base_url
        self.model = get_model(
            self.settings.model.provider,
            self.settings.model.model_id,
            **model_kwargs,
        )
        logger.info(
            "Using model: provider=%s, model_id=%s, base_url=%s",
            self.settings.model.provider,
            self.settings.model.model_id,
            self.settings.model.base_url or "(default)",
        )

        # Create context (base + skills index only)
        system_prompt = self._get_system_prompt()
        self.context = Context(
            systemPrompt=system_prompt,
            messages=[],
        )
        self._default_system_prompt = system_prompt

        # Create agent
        self.agent = Agent(self.model, self.context)
        self.agent.max_turns = self.settings.agent.max_turns

        # Todo list state (updated by todo_write tool)
        self._current_todos: List[dict] = []
        # Session id for todo persistence; set by set_session_id() or run_interactive/gateway
        self._session_id: Optional[str] = None
        # CLI: whether to show full todo list above prompt (toggle via /todos)
        self._todo_show_full: bool = False
        # Plan mode: read-only analysis and planning; no write/edit/bash/todo_write
        self._plan_mode: bool = getattr(
            self.settings.permissions, "default_mode", "default"
        ) == "plan"
        # Pending asks (ask_user_question): list of {tool_call_id, question, options}
        self._pending_asks: List[dict] = []
        # Last ask payload before tool_call_id is known (set by tool, merged in tool_call_end)
        self._last_ask_user_question: Optional[dict] = None

        # Register tools
        self._register_tools()

        # Setup event handlers
        self._setup_event_handlers()

        # Load extensions
        self.extension_loader = ExtensionLoader(self)
        if load_extensions:
            num_loaded = self.extension_loader.load_default_extensions()
            if num_loaded > 0:
                print(f"📦 Loaded {num_loaded} extension(s)")

    async def set_session_id(self, session_id: Optional[str]) -> None:
        """
        Set the current session id and load its todo list and pending_asks from disk.
        When session_id is None, clear _session_id, _current_todos, and _pending_asks.
        """
        self._session_id = session_id
        if session_id:
            self._current_todos = await self.session_manager.load_todos(session_id)
            self._pending_asks = await self.session_manager.load_pending_asks(session_id)
        else:
            self._current_todos = []
            self._pending_asks = []

    def set_plan_mode(self, on: bool) -> None:
        """Enable or disable plan mode (read-only analysis and planning)."""
        self._plan_mode = on

    def get_plan_mode(self) -> bool:
        """Return True if plan mode is on."""
        return self._plan_mode

    async def try_resume_pending_ask(
        self,
        user_content: str,
        tool_call_id: Optional[str] = None,
        *,
        stream_llm_events: bool = True,
        invoked_skill_id: Optional[str] = None,
    ) -> bool:
        """
        If there is a pending_ask, treat user_content as the answer: replace the
        corresponding ToolResultMessage content, remove that pending, and run agent.
        Returns True if a pending was consumed and run started; False otherwise.

        If tool_call_id is given, use that entry; else FIFO (oldest).
        """
        if not self._pending_asks:
            return False
        if tool_call_id:
            entry = next(
                (p for p in self._pending_asks if p.get("tool_call_id") == tool_call_id),
                None,
            )
        else:
            entry = self._pending_asks[0]
        if not entry:
            return False
        target_id = entry["tool_call_id"]
        for msg in self.context.messages:
            if getattr(msg, "role", None) == "toolResult" and getattr(
                msg, "tool_call_id", None
            ) == target_id:
                msg.content = [TextContent(type="text", text=user_content)]
                break
        else:
            return False
        self._pending_asks = [p for p in self._pending_asks if p.get("tool_call_id") != target_id]
        if self._session_id:
            await self.session_manager.save_pending_asks(
                self._session_id, self._pending_asks
            )
        await self._run_with_trajectory_if_enabled(
            stream_llm_events=stream_llm_events,
            invoked_skill_id=invoked_skill_id,
        )
        return True

    def _get_agents_dirs(self) -> list[Path]:
        """Resolve agents directories; default ~/.basket/agents and ./.basket/agents."""
        if self.settings.agents_dirs:
            return [Path(d).expanduser().resolve() for d in self.settings.agents_dirs]
        return [
            Path.home() / ".basket" / "agents",
            Path.cwd() / ".basket" / "agents",
        ]

    def _get_subagent_configs(self) -> Dict[str, SubAgentConfig]:
        """Merge settings.agents with agents loaded from .basket/agents/*.md; later overrides."""
        out: Dict[str, SubAgentConfig] = {}
        for k, v in self.settings.agents.items():
            out[k] = v
        for k, v in load_agents_from_dirs(self._get_agents_dirs()).items():
            out[k] = v
        return out

    def _get_registerable_tools(self) -> List[dict]:
        """Return list of tool dicts (name, description, parameters, execute_fn) as used in _register_tools."""
        include = self.settings.skills_include or None
        if include is not None and len(self.settings.skills_include) == 0:
            include = None
        skill_tool = create_skill_tool(self._get_skills_dirs, include)
        return list(BUILT_IN_TOOLS) + [skill_tool]

    def _filter_tools_for_subagent(self, cfg: SubAgentConfig) -> List[dict]:
        """Return tool dicts allowed for this subagent; cfg.tools None = all."""
        tools = self._get_registerable_tools()
        if cfg.tools is None:
            return tools
        return [t for t in tools if cfg.tools.get(t["name"], False)]

    async def run_subagent(self, subagent_name: str, user_prompt: str) -> str:
        """Run a subagent with the given prompt; returns last assistant text."""
        configs = self._get_subagent_configs()
        cfg = configs.get(subagent_name)
        if not cfg:
            available = ", ".join(configs) if configs else "none"
            return f'SubAgent "{subagent_name}" not found. Available: {available}'

        if cfg.model and isinstance(cfg.model, dict):
            model_kwargs: dict = {}
            if self.settings.model.base_url:
                model_kwargs["base_url"] = self.settings.model.base_url
            model = get_model(
                cfg.model.get("provider", self.settings.model.provider),
                cfg.model.get("model_id", self.settings.model.model_id),
                **model_kwargs,
            )
        else:
            model = self.model

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
        sub_agent.max_turns = self.settings.agent.max_turns
        for t in self._filter_tools_for_subagent(cfg):
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

    def _get_skills_dirs(self) -> list[Path]:
        """Resolve skills directories; default includes Basket, OpenCode, Claude, Agents paths."""
        if self.settings.skills_dirs:
            return [Path(d).expanduser().resolve() for d in self.settings.skills_dirs]
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

    def _get_system_prompt(self) -> str:
        """Get the system prompt for the agent (base + brief skill tool mention)."""
        base = """You are a helpful coding assistant. You have access to tools to read, write, and edit files, execute shell commands, and search for code.

When using tools:
- Use 'read' to read file contents
- Use 'write' to create or overwrite files
- Use 'edit' to make precise changes to existing files
- Use 'bash' to run shell commands (git, npm, pytest, etc.)
- Use 'grep' to search for patterns in files

You have a `skill` tool to discover and load reusable skills by name; use it when you need instructions for a specific task. The skill tool's description lists available skills.

Always explain what you're doing before using tools.
"""
        return base

    def _get_plan_mode_prompt_suffix(self) -> str:
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

    def get_system_prompt_for_run(self, invoked_skill_id: Optional[str] = None) -> str:
        """System prompt for this run; if invoked_skill_id set, append that skill's full content."""
        prompt = self._default_system_prompt
        if invoked_skill_id:
            dirs = self._get_skills_dirs()
            full = get_skill_full_content(invoked_skill_id, dirs)
            if full:
                prompt = prompt + "\n\n---\n\n## Active skill: " + invoked_skill_id + "\n\n" + full
        if self._plan_mode:
            prompt = prompt + self._get_plan_mode_prompt_suffix()
        return prompt

    def _register_tools(self) -> None:
        """Register all built-in tools with the agent. In plan mode, write/edit/bash/todo_write are no-ops."""
        get_plan = lambda: self._plan_mode
        for tool in BUILT_IN_TOOLS:
            name = tool["name"]
            fn = tool["execute_fn"]
            if name in PLAN_MODE_FORBIDDEN_TOOLS:
                fn = _wrap_execute_fn_for_plan_mode(fn, get_plan)
            self.agent.register_tool(
                name=name,
                description=tool["description"],
                parameters=tool["parameters"],
                execute_fn=fn,
            )
        # Skill tool: dynamic description with available_skills
        include = self.settings.skills_include or None
        if include is not None and len(self.settings.skills_include) == 0:
            include = None
        skill_tool = create_skill_tool(self._get_skills_dirs, include)
        self.agent.register_tool(
            name=skill_tool["name"],
            description=skill_tool["description"],
            parameters=skill_tool["parameters"],
            execute_fn=skill_tool["execute_fn"],
        )
        # Task tool: delegate to subagents (only when at least one subagent is configured)
        configs = self._get_subagent_configs()
        if configs:
            task_tool = create_task_tool(self)
            self.agent.register_tool(
                name=task_tool["name"],
                description=task_tool["description"],
                parameters=task_tool["parameters"],
                execute_fn=task_tool["execute_fn"],
            )
        # Web Search: duckduckgo by default; Serper when web_search_provider=serper and key set
        web_search_tool = create_web_search_tool(self.settings)
        self.agent.register_tool(
            name=web_search_tool["name"],
            description=web_search_tool["description"],
            parameters=web_search_tool["parameters"],
            execute_fn=web_search_tool["execute_fn"],
        )
        # TodoWrite: session task list (replaced in full on each call)
        todo_tool = create_todo_write_tool(self)
        todo_fn = todo_tool["execute_fn"]
        if "todo_write" in PLAN_MODE_FORBIDDEN_TOOLS:
            todo_fn = _wrap_execute_fn_for_plan_mode(todo_fn, get_plan)
        self.agent.register_tool(
            name=todo_tool["name"],
            description=todo_tool["description"],
            parameters=todo_tool["parameters"],
            execute_fn=todo_fn,
        )
        # AskUserQuestion: ask user; answer comes in next message (session resume)
        ask_tool = create_ask_user_question_tool(self)
        self.agent.register_tool(
            name=ask_tool["name"],
            description=ask_tool["description"],
            parameters=ask_tool["parameters"],
            execute_fn=ask_tool["execute_fn"],
        )

    def _setup_event_handlers(self) -> None:
        """Setup event handlers for agent events."""

        def on_text_delta(event):
            """Handle text delta events - always show assistant reply."""
            delta = event.get("delta", "")
            if delta:
                print(delta, end="", flush=True)

        def on_tool_call_start(event):
            """Handle tool call start events."""
            if self.settings.agent.verbose:
                print(f"\n[Tool: {event['tool_name']}]", flush=True)

        async def on_tool_call_end(event):
            """Handle tool call end events."""
            if event.get("error"):
                print(f"[Error: {event['error']}]", flush=True)
            elif event.get("tool_name") == "todo_write" and self._current_todos:
                in_progress = [t for t in self._current_todos if t.get("status") == "in_progress"]
                if in_progress and self.settings.agent.verbose:
                    print(f"\n[Todo: {len(self._current_todos)} items; in progress: {in_progress[0].get('content', '')[:50]!r}]", flush=True)
                elif self.settings.agent.verbose:
                    print(f"\n[Todo: {len(self._current_todos)} items]", flush=True)
            elif event.get("tool_name") == "ask_user_question" and getattr(self, "_last_ask_user_question", None):
                last = self._last_ask_user_question
                self._last_ask_user_question = None
                tool_call_id = event.get("tool_call_id") or ""
                if tool_call_id:
                    entry = {
                        "tool_call_id": tool_call_id,
                        "question": last.get("question", ""),
                        "options": last.get("options") or [],
                    }
                    self._pending_asks.append(entry)
                    if self._session_id:
                        await self.session_manager.save_pending_asks(
                            self._session_id, self._pending_asks
                        )
                    q = entry.get("question", "") or "Question"
                    if len(q) > 60:
                        q = q[:57] + "..."
                    n = len(self._pending_asks)
                    print(
                        f"\n[Ask: {q}] Reply in your next message"
                        + (f" ({n} pending)" if n > 1 else ""),
                        flush=True,
                    )

        self.agent.on("text_delta", on_text_delta)
        self.agent.on("agent_tool_call_start", on_tool_call_start)
        self.agent.on("agent_tool_call_end", on_tool_call_end)

    def _get_trajectory_dir(self) -> Optional[str]:
        """Trajectory directory from env or settings; None if disabled."""
        out = os.environ.get("BASKET_TRAJECTORY_DIR") or (self.settings.trajectory_dir or "").strip()
        return out or None

    def _on_trajectory_event(self, event: dict) -> None:
        """Forward agent event to current trajectory recorder (if any)."""
        recorder = getattr(self, "_trajectory_recorder", None)
        if recorder is not None:
            recorder.on_event(event)

    def _ensure_trajectory_handlers(self) -> None:
        """Register trajectory event handlers once (no-op when trajectory disabled)."""
        if getattr(self, "_trajectory_handlers_registered", False):
            return
        for event_type in (
            "agent_turn_start",
            "agent_turn_end",
            "agent_tool_call_start",
            "agent_tool_call_end",
            "agent_complete",
            "agent_error",
        ):
            self.agent.on(event_type, self._on_trajectory_event)
        self._trajectory_handlers_registered = True

    async def _run_with_trajectory_if_enabled(
        self, stream_llm_events: bool = True, invoked_skill_id: Optional[str] = None
    ):
        """Run agent; if trajectory_dir is set, record trajectory and write to disk."""
        old_system = self.context.system_prompt
        self.context.system_prompt = self.get_system_prompt_for_run(invoked_skill_id)
        try:
            trajectory_dir = self._get_trajectory_dir()
            if not trajectory_dir:
                return await self.agent.run(stream_llm_events=stream_llm_events)

            from pathlib import Path
            from basket_trajectory import TrajectoryRecorder, write_trajectory

            self._ensure_trajectory_handlers()
            recorder = TrajectoryRecorder()
            self._trajectory_recorder = recorder

            user_input = ""
            for msg in reversed(self.context.messages):
                if getattr(msg, "role", None) == "user":
                    content = getattr(msg, "content", "")
                    user_input = content if isinstance(content, str) else str(content)
                    break
            recorder.start_task(user_input)

            state = None
            try:
                state = await self.agent.run(stream_llm_events=stream_llm_events)
            except Exception:
                raise
            finally:
                self._trajectory_recorder = None
                try:
                    recorder.finalize(state)
                    path = Path(trajectory_dir).expanduser()
                    path.mkdir(parents=True, exist_ok=True)
                    write_trajectory(recorder.get_trajectory(), path / f"task_{recorder.task_id}.json")
                except Exception as e:
                    logger.warning("Failed to write trajectory: %s", e)

            return state
        finally:
            self.context.system_prompt = old_system

    async def run_interactive(self) -> None:
        """
        Run the agent in interactive mode.

        Continuously prompts for user input and runs the agent.
        """
        if self._session_id is None:
            session_id = await self.session_manager.create_session(self.model.id)
            await self.set_session_id(session_id)

        print("Basket - Interactive Mode")
        print("Type 'exit' or 'quit' to quit, 'help' for help")
        print("-" * 50)

        while True:
            try:
                # Todo region above prompt
                if self._current_todos:
                    block = self._format_todo_block()
                    if block:
                        print(block, flush=True)
                # Get user input
                user_input = input("\n> ").strip()

                if not user_input:
                    continue

                # Handle special commands
                if user_input.lower() in ["exit", "quit"]:
                    print("Goodbye!")
                    break

                if user_input.lower() == "help":
                    self._print_help()
                    continue

                if user_input.lower() == "settings":
                    self._print_settings()
                    continue

                if user_input.lower() == "/todos":
                    self._todo_show_full = not self._todo_show_full
                    print(f"Todo list: {'full' if self._todo_show_full else 'compact'}", flush=True)
                    continue

                if user_input.strip().lower() in ("/plan", "/plan on", "/plan off"):
                    on = user_input.strip().lower() != "/plan off"
                    self.set_plan_mode(on)
                    print(f"Plan mode {'on' if on else 'off'}", flush=True)
                    continue

                # Pending ask_user_question: treat this input as the answer (FIFO)
                if self._pending_asks:
                    print()  # newline before agent output
                    try:
                        resumed = await self.try_resume_pending_ask(
                            user_input, stream_llm_events=True
                        )
                        if resumed:
                            print()  # newline after agent output
                            continue
                    except Exception as resume_err:
                        logger.exception("Resume pending ask failed")
                        print(f"\n❌ Error: {resume_err}", flush=True)
                        continue

                invoked_skill_id: Optional[str] = None
                message_content = user_input

                # Handle built-in /skill <id> [rest of message]
                if user_input.strip().lower().startswith("/skill "):
                    parts = user_input.split(maxsplit=2)
                    if len(parts) < 2:
                        print("Usage: /skill <id> [your message]")
                        continue
                    invoked_skill_id = parts[1].strip()
                    message_content = parts[2].strip() if len(parts) > 2 else ""
                    if not message_content:
                        message_content = "Please help according to the active skill instructions."

                # Handle other slash commands (from extensions)
                elif user_input.startswith("/"):
                    command_parts = user_input.split(maxsplit=1)
                    command = command_parts[0]
                    args = command_parts[1] if len(command_parts) > 1 else ""

                    if self.extension_loader.extension_api.execute_command(command, args):
                        continue
                    else:
                        print(f"Unknown command: {command}")
                        available = self.extension_loader.extension_api.get_commands()
                        if available:
                            print(f"Available commands: {', '.join(available)}")
                        continue

                # Add user message to context
                self.context.messages.append(
                    UserMessage(
                        role="user",
                        content=message_content,
                        timestamp=int(time.time() * 1000),
                    )
                )

                # Save context snapshot for error recovery
                messages_snapshot = copy.deepcopy(self.context.messages)

                # Run agent
                print()  # Newline before agent output
                try:
                    await self._run_with_trajectory_if_enabled(
                        stream_llm_events=True, invoked_skill_id=invoked_skill_id
                    )
                except Exception as agent_error:
                    logger.exception("Agent run failed")
                    # Restore context on agent failure
                    self.context.messages = messages_snapshot
                    raise agent_error
                print()  # Newline after agent output

            except KeyboardInterrupt:
                print("\n\nInterrupted. Type 'exit' to quit.")
                continue
            except Exception as e:
                logger.exception("Interactive loop error")
                print(f"\n❌ Error: {e}")
                if self.settings.agent.verbose:
                    import traceback
                    traceback.print_exc()
                print("Context has been restored to previous state.")

    async def run_once(self, message: str, invoked_skill_id: Optional[str] = None) -> str:
        """
        Run the agent once with a message.

        Args:
            message: User message
            invoked_skill_id: Optional skill id to load full instructions for this run

        Returns:
            Agent response text
        """
        # Add user message
        self.context.messages.append(
            UserMessage(role="user", content=message, timestamp=int(time.time() * 1000))
        )

        # Run agent
        state = await self._run_with_trajectory_if_enabled(
            stream_llm_events=False, invoked_skill_id=invoked_skill_id
        )

        # Get last assistant message
        last_message = state.context.messages[-1]
        if hasattr(last_message, "content"):
            text_blocks = [
                block.text
                for block in last_message.content
                if hasattr(block, "text")
            ]
            return "\n".join(text_blocks)

        return ""

    def _format_todo_block(self) -> str:
        """Format _current_todos for CLI display above prompt. Compact: one line; full: one line per item with icon."""
        if not self._current_todos:
            return ""
        total = len(self._current_todos)
        done = sum(1 for t in self._current_todos if t.get("status") == "completed")
        in_progress = [t for t in self._current_todos if t.get("status") == "in_progress"]
        if self._todo_show_full:
            icons = {"completed": "✓", "pending": "○", "in_progress": "→", "cancelled": "✗"}
            lines = []
            for t in self._current_todos:
                icon = icons.get(t.get("status", "pending"), "○")
                content = (t.get("content") or "").strip()
                lines.append(f"  {icon} {content}")
            return "\n".join(lines)
        if in_progress:
            content = (in_progress[0].get("content") or "").strip()
            return f"[Todo {done}/{total}] → {content}"
        return f"[Todo {total} items]"

    def _print_help(self) -> None:
        """Print help information."""
        print("""
Available commands:
  help      - Show this help message
  settings  - Show current settings
  /todos    - Toggle full/compact todo list above prompt
  /plan     - Toggle plan mode (read-only analysis and planning); /plan on, /plan off
  exit/quit - Exit the program
  /skill <id> - Load full instructions for a skill for this turn (e.g. /skill refactor)

Available tools:
  read      - Read files
  write     - Write files
  edit      - Edit files with exact string replacement
  bash      - Execute shell commands
  grep      - Search for patterns in files

Example prompts:
  "Read the README.md file"
  "Create a new file hello.py with a hello world function"
  "Search for 'TODO' in all Python files"
  "Run the tests using pytest"
""")

    def _print_settings(self) -> None:
        """Print current settings."""
        print(f"""
Current settings:
  Model: {self.settings.model.provider} / {self.settings.model.model_id}
  Temperature: {self.settings.model.temperature}
  Max tokens: {self.settings.model.max_tokens}
  Max turns: {self.settings.agent.max_turns}
  Verbose: {self.settings.agent.verbose}
  Sessions dir: {self.settings.sessions_dir}
""")


async def main_async(args: Optional[list] = None) -> int:
    """
    Async main function.

    Args:
        args: Command line arguments (defaults to sys.argv[1:])

    Returns:
        Exit code
    """
    if args is None:
        args = sys.argv[1:]

    # Configure logging: default write to ~/.basket/logs/ (INFO); LOG_LEVEL overrides level
    fmt = "%(asctime)s %(name)s: %(levelname)s: %(message)s"
    log_level_name = (os.environ.get("LOG_LEVEL") or "").upper()
    level = logging.INFO
    if log_level_name:
        level = getattr(logging, log_level_name, level) or level
    log_dir = Path.home() / ".basket" / "logs"
    try:
        log_dir.mkdir(parents=True, exist_ok=True)
        log_file = log_dir / "basket.log"
        file_handler = logging.FileHandler(log_file, encoding="utf-8")
        file_handler.setLevel(level)
        file_handler.setFormatter(logging.Formatter(fmt))
        root = logging.getLogger()
        root.setLevel(level)
        root.addHandler(file_handler)
        for name in ("basket_tui.app", "basket_assistant.modes.tui"):
            logging.getLogger(name).setLevel(level)
        logger.info("Log file: %s", log_file)
    except OSError as e:
        logger.debug("Could not create log file: %s", e)

    # Parse simple arguments
    use_tui = "--tui" in args
    if use_tui:
        args = [a for a in args if a != "--tui"]

    use_plan_mode = "--plan" in args
    if use_plan_mode:
        args = [a for a in args if a != "--plan"]
    if "--permission-mode" in args:
        i = args.index("--permission-mode")
        if i + 1 < len(args) and args[i + 1] == "plan":
            use_plan_mode = True
        args = args[:i] + args[i + 2:] if i + 1 < len(args) else args[:i]

    use_remote = "--remote" in args
    if use_remote:
        args = [a for a in args if a != "--remote"]
    remote_bind = os.environ.get("BASKET_REMOTE_BIND", "0.0.0.0")
    remote_port = 7681
    try:
        remote_port = int(os.environ.get("BASKET_REMOTE_PORT", "7681"))
    except ValueError:
        pass
    if "--bind" in args:
        i = args.index("--bind")
        if i + 1 < len(args):
            remote_bind = args[i + 1]
            args = args[:i] + args[i + 2:]
    if "--port" in args:
        i = args.index("--port")
        if i + 1 < len(args):
            try:
                remote_port = int(args[i + 1])
            except ValueError:
                pass
            args = args[:i] + args[i + 2:]

    if "--help" in args or "-h" in args:
        print("""
Basket - AI-powered personal assistant

Usage:
  basket                 - Start interactive mode
  basket --tui           - Start TUI mode (terminal UI)
  basket --remote        - Start remote web terminal (requires basket-remote, ttyd; use with ZeroTier)
  basket "message"       - Run once with a message
  basket --plan          - Run in plan mode (read-only; same as --permission-mode plan)
  basket serve start     - Start resident assistant (gateway)
  basket serve stop      - Stop resident assistant
  basket serve status    - Show assistant status
  basket serve attach    - Attach TUI to running assistant
  basket --help          - Show this help
  basket --version       - Show version

Interactive mode commands:
  help      - Show help
  settings  - Show settings
  exit/quit - Exit

Environment variables:
  OPENAI_API_KEY        - OpenAI API key
  ANTHROPIC_API_KEY     - Anthropic API key
  GOOGLE_API_KEY        - Google API key
  BASKET_REMOTE_BIND    - Bind address for --remote (default: 0.0.0.0)
  BASKET_REMOTE_PORT    - Port for --remote (default: 7681)
  BASKET_SERVE_PORT     - Port for resident assistant (default: 7682)
""")
        return 0

    if "--version" in args or "-v" in args:
        print("Basket v0.1.0")
        return 0

    # Serve subcommands: resident assistant gateway (start / stop / status / attach)
    def _build_serve_channel_config():
        """Build channel_config from settings.json (serve). Assistant does not interpret channel schema; gateway/channels do."""
        cfg = {"websocket": True, "feishu": None}
        try:
            sm = SettingsManager()
            settings = sm.load()
            if getattr(settings, "serve", None) and isinstance(settings.serve, dict):
                cfg.update(settings.serve)
        except Exception as e:
            logger.debug("Loading serve channel config: %s", e)
        return cfg

    if len(args) >= 2 and args[0] == "serve" and args[1] in ("start", "stop", "status", "attach"):
        sub = args[1]
        rest = args[2:]
        if sub == "start":
            foreground = "--foreground" in rest
            rest = [a for a in rest if a != "--foreground"]
            if rest:
                print("Usage: basket serve start [--foreground]")
                return 1
            try:
                from .serve import run_gateway, is_serve_running
            except ImportError as e:
                logger.warning("serve import failed: %s", e)
                print("Error: basket serve requires starlette and uvicorn.")
                print("Install with: poetry add starlette 'uvicorn[standard]'")
                return 1
            running, pid = is_serve_running()
            if running:
                print(f"Assistant is already running (pid {pid}). Use 'basket serve stop' first.")
                return 1
            port = 7682
            try:
                port = int(os.environ.get("BASKET_SERVE_PORT", "7682"))
            except ValueError:
                pass
            if not foreground:
                print("Starting assistant in foreground. Use Ctrl+C to stop.")
                print("Tip: run with 'nohup basket serve start &' or systemd for background.")
            channel_config = _build_serve_channel_config()
            await run_gateway(
                host="127.0.0.1",
                port=port,
                agent_factory=CodingAgent,
                channel_config=channel_config,
            )
            return 0
        if sub == "stop":
            try:
                from .serve import read_serve_state, clear_serve_state, is_serve_running
            except ImportError:
                print("Error: basket serve requires the serve module.")
                return 1
            import signal
            pid, _ = read_serve_state()
            if pid is None:
                print("Assistant is not running (no pid file).")
                return 0
            running, _ = is_serve_running()
            if not running:
                print("Assistant is not running (stale pid file removed).")
                clear_serve_state()
                return 0
            try:
                os.kill(pid, signal.SIGTERM)
            except OSError as e:
                print(f"Error stopping assistant: {e}")
                return 1
            print(f"Sent SIGTERM to pid {pid}. Waiting for exit...")
            for _ in range(30):
                await asyncio.sleep(0.5)
                if not is_serve_running()[0]:
                    break
            clear_serve_state()
            print("Assistant stopped.")
            return 0
        if sub == "status":
            try:
                from .serve import read_serve_state, is_serve_running
            except ImportError:
                print("Error: basket serve requires the serve module.")
                return 1
            running, pid = is_serve_running()
            _, port = read_serve_state()
            if not running:
                print("Assistant is not running.")
                return 0
            print(f"Assistant is running (pid {pid}, port {port}).")
            if port is not None:
                try:
                    import urllib.request
                    req = urllib.request.Request(f"http://127.0.0.1:{port}/status")
                    with urllib.request.urlopen(req, timeout=2) as resp:
                        data = json.load(resp)
                        if "uptime_seconds" in data:
                            print(f"Uptime: {data['uptime_seconds']}s")
                        if "version" in data:
                            print(f"Version: {data['version']}")
                except Exception:
                    pass
            return 0
        if sub == "attach":
            attach_url = None
            if "--url" in rest:
                i = rest.index("--url")
                if i + 1 < len(rest):
                    attach_url = rest[i + 1]
                    rest = rest[:i] + rest[i + 2:]
            if rest:
                print("Usage: basket serve attach [--url WS_URL]")
                return 1
            try:
                from .serve import get_serve_port, is_serve_running
                from .modes.attach import run_tui_mode_attach
            except ImportError as e:
                logger.warning("attach import failed: %s", e)
                if "attach" in str(e):
                    print("Error: TUI attach requires 'basket-tui' package.")
                    print("Install with: poetry add basket-tui")
                else:
                    print("Error: basket serve attach requires the serve and attach modules.")
                return 1
            if attach_url is None:
                running, _ = is_serve_running()
                if not running:
                    print("Assistant is not running. Start it with: basket serve start")
                    return 1
                port = get_serve_port()
                if port is None:
                    print("Cannot determine port. Use: basket serve attach --url ws://127.0.0.1:7682/ws")
                    return 1
                attach_url = f"ws://127.0.0.1:{port}/ws"
            await run_tui_mode_attach(attach_url)
            return 0

    # Remote mode: run ttyd with basket --tui, no agent in this process
    if use_remote:
        if len(args) > 0:
            print("Remote mode does not support one-shot messages. Run: basket --remote [--bind <IP>] [--port <port>]")
            return 1
        try:
            from basket_remote import run_serve
        except ImportError as e:
            logger.warning("basket_remote import failed: %s", e)
            print("Error: Remote mode requires 'basket-remote' package.")
            print("Install with: poetry add basket-remote")
            return 1
        command = [sys.executable, "-m", "basket_assistant.main", "--tui"]
        try:
            run_serve(bind=remote_bind, port=remote_port, command=command)
        except RuntimeError as e:
            print(f"Error: {e}")
            return 1
        return 0

    # Create agent
    try:
        agent = CodingAgent()
    except Exception as e:
        logger.exception("Failed to initialize agent")
        print(f"Error initializing agent: {e}")
        return 1

    if use_plan_mode:
        agent.set_plan_mode(True)

    # Run mode
    if len(args) == 0:
        # Choose mode based on flag
        if use_tui:
            # TUI mode (pass CodingAgent so trajectory recording works when enabled)
            try:
                from .modes.tui import run_tui_mode
                await run_tui_mode(agent)
            except ImportError as e:
                logger.warning("TUI import failed: %s", e)
                print(f"Error: TUI mode requires 'basket-tui' package: {e}")
                print("Install with: poetry add basket-tui")
                return 1
        else:
            # Interactive mode (basic CLI)
            await agent.run_interactive()
    else:
        # One-shot mode
        message = " ".join(args)
        response = await agent.run_once(message)
        print(response)

    return 0


def main() -> int:
    """
    Main entry point.

    Returns:
        Exit code
    """
    return asyncio.run(main_async())


if __name__ == "__main__":
    sys.exit(main())

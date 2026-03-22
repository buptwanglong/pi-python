"""Input processor - priority-based input routing.

Handles user input with priority order:
1. Pending ask (highest)
2. Commands (/plan, /todos)
3. Skill invocation (/skill <id>)
4. Declarative slash commands (*.md under .basket/commands)
5. Normal input (lowest)
"""

import re
import time
from dataclasses import dataclass
from typing import Any, Dict, Optional

from basket_ai.types import Message, UserMessage

from basket_assistant.core.loader.slash_commands_loader import (
    SlashCommandSpec,
    expand_slash_body,
)


@dataclass
class ProcessResult:
    """Result of input processing."""

    action: str  # "handled" | "send_to_agent" | "exit"
    message: Optional[Message] = None
    invoked_skill_id: Optional[str] = None
    error: Optional[str] = None
    command_output: Optional[str] = None


class InputProcessor:
    """Priority-based input routing processor.

    Routes user input based on priority:
    1. Pending ask (agent needs answer)
    2. Commands (registered commands)
    3. Skill invocation (/skill <id>)
    4. Declarative slash commands (markdown specs)
    5. Normal input (send to agent)
    """

    def __init__(
        self,
        agent: Any,
        command_registry: Any,
        slash_commands: Optional[Dict[str, SlashCommandSpec]] = None,
    ) -> None:
        """Initialize the input processor.

        Args:
            agent: Agent instance with _pending_asks and try_resume_pending_ask
            command_registry: CommandRegistry instance
            slash_commands: Declarative commands by name (no leading slash)
        """
        self.agent = agent
        self.command_registry = command_registry
        self.slash_commands = slash_commands or {}

    async def process(self, user_input: str) -> ProcessResult:
        """Process user input with priority-based routing.

        Args:
            user_input: Raw user input text

        Returns:
            ProcessResult indicating what action to take
        """
        # Priority 1: Pending ask (highest)
        if hasattr(self.agent, "_pending_asks") and self.agent._pending_asks:
            # Try to resume pending ask
            resumed, _ = await self.agent.try_resume_pending_ask(user_input)
            if resumed:
                return ProcessResult(action="handled")

        # Priority 2–5: slash-prefixed input
        if user_input.startswith("/"):
            # Priority 2: Builtin commands
            if self.command_registry.has_command(user_input):
                command_name = user_input.split(maxsplit=1)[0][1:].lower()
                if command_name != "skill" or self.command_registry.get_command("skill"):
                    success, result = await self.command_registry.execute(user_input)
                    if not success:
                        return ProcessResult(action="handled", error=result)
                    if command_name in ("exit", "quit"):
                        return ProcessResult(action="exit")
                    out = result if isinstance(result, str) else str(result)
                    return ProcessResult(
                        action="handled",
                        command_output=out if out else None,
                    )

            # Priority 3: /skill <id> [message]
            if user_input.startswith("/skill ") or user_input == "/skill":
                return await self._handle_skill_invocation(user_input)

            # Priority 4: Declarative slash commands
            parts = user_input.split(maxsplit=1)
            cmd_name = parts[0][1:].lower()
            spec = self.slash_commands.get(cmd_name)
            if spec is not None:
                args_text = parts[1] if len(parts) > 1 else ""
                content = expand_slash_body(spec.body_template, args_text)
                message = UserMessage(
                    role="user", content=content, timestamp=int(time.time() * 1000)
                )
                return ProcessResult(
                    action="send_to_agent",
                    message=message,
                    invoked_skill_id=spec.skill_id,
                )

            # Unknown /
            command_token = parts[0]
            return ProcessResult(
                action="handled", error=f"Unknown command: {command_token}"
            )

        # Priority 5: Normal input (lowest)
        return self._handle_normal_input(user_input)

    async def _handle_skill_invocation(self, user_input: str) -> ProcessResult:
        """Handle skill invocation (/skill <id> [message]).

        Args:
            user_input: Input text starting with /skill

        Returns:
            ProcessResult with skill invocation details
        """
        # Parse skill format: /skill <skill-id> [optional message]
        match = re.match(r"/skill\s+([a-z0-9]+(?:-[a-z0-9]+)*)\s*(.*)", user_input)
        if not match:
            return ProcessResult(
                action="handled",
                error="Usage: /skill <skill-id> [optional message]",
            )

        skill_id = match.group(1)
        optional_message = match.group(2).strip() if match.group(2) else ""

        # Build message for agent
        content = f"Load and use skill: {skill_id}"
        if optional_message:
            content += f"\n\nAdditional context: {optional_message}"

        message = UserMessage(
            role="user", content=content, timestamp=int(time.time() * 1000)
        )

        return ProcessResult(
            action="send_to_agent", message=message, invoked_skill_id=skill_id
        )

    def _handle_normal_input(self, user_input: str) -> ProcessResult:
        """Handle normal user input.

        Args:
            user_input: User input text

        Returns:
            ProcessResult with user message
        """
        message = UserMessage(
            role="user", content=user_input, timestamp=int(time.time() * 1000)
        )
        return ProcessResult(action="send_to_agent", message=message)


__all__ = ["InputProcessor", "ProcessResult"]

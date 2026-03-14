"""Input processor - priority-based input routing.

Handles user input with priority order:
1. Pending ask (highest)
2. Commands (/plan, /todos)
3. Skill invocation (/skill <id>)
4. Extension commands
5. Normal input (lowest)
"""

import re
import time
from dataclasses import dataclass
from typing import Any, Optional

from basket_ai.types import Message, UserMessage


@dataclass
class ProcessResult:
    """Result of input processing."""

    action: str  # "handled" | "send_to_agent"
    message: Optional[Message] = None
    invoked_skill_id: Optional[str] = None
    error: Optional[str] = None


class InputProcessor:
    """Priority-based input routing processor.

    Routes user input based on priority:
    1. Pending ask (agent needs answer)
    2. Commands (registered commands)
    3. Skill invocation (/skill <id>)
    4. Normal input (send to agent)
    """

    def __init__(self, agent: Any, command_registry: Any) -> None:
        """Initialize the input processor.

        Args:
            agent: Agent instance with _pending_asks and try_resume_pending_ask
            command_registry: CommandRegistry instance
        """
        self.agent = agent
        self.command_registry = command_registry

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

        # Priority 2: Commands
        if user_input.startswith("/"):
            # Check if it's a registered command (not skill invocation)
            if self.command_registry.has_command(user_input):
                # Check if command is "skill" - special handling
                command_name = user_input.split(maxsplit=1)[0][1:].lower()
                if command_name != "skill" or self.command_registry.get_command("skill"):
                    # Execute command
                    success, result = await self.command_registry.execute(user_input)
                    if not success:
                        return ProcessResult(action="handled", error=result)
                    return ProcessResult(action="handled")

            # Priority 3: Skill invocation (/skill <id>)
            if user_input.startswith("/skill ") or user_input == "/skill":
                return await self._handle_skill_invocation(user_input)

            # Unknown command
            command_name = user_input.split(maxsplit=1)[0]
            return ProcessResult(
                action="handled", error=f"Unknown command: {command_name}"
            )

        # Priority 4: Normal input (lowest)
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
            action="handled", message=message, invoked_skill_id=skill_id
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

"""Base class for interaction modes.

This module provides the abstract InteractionMode base class that all
interaction modes (CLI, TUI, Attach) inherit from.

Key responsibilities:
- Session management (create/restore)
- Publisher/adapter lifecycle
- Command registry + input processor integration
- Agent execution with error recovery
"""

import logging
import uuid
from abc import ABC, abstractmethod
from typing import Any, Optional, Tuple

from basket_ai.types import UserMessage

from ..commands.registry import CommandRegistry
from ..processors.input_processor import InputProcessor
from ..errors import ModeInitializationError

logger = logging.getLogger(__name__)


class InteractionMode(ABC):
    """Abstract base class for all interaction modes.

    This class provides common functionality for CLI, TUI, and Attach modes:
    - Session creation and restoration
    - Publisher and adapter setup
    - Command registry and input processing
    - Agent execution with error recovery

    Subclasses must implement:
    - setup_publisher_adapter(): Create and return publisher/adapter pair
    - run(): Main interaction loop

    Example:
        >>> class CLIMode(InteractionMode):
        ...     def setup_publisher_adapter(self):
        ...         publisher = EventPublisher(self.agent)
        ...         adapter = CLIAdapter(publisher)
        ...         return publisher, adapter
        ...
        ...     async def run(self):
        ...         while True:
        ...             user_input = input("> ")
        ...             should_continue = await self.process_and_run_agent(user_input)
        ...             if not should_continue:
        ...                 break
    """

    def __init__(self, agent: Any) -> None:
        """Initialize the interaction mode.

        Args:
            agent: AssistantAgent instance
        """
        self.agent = agent
        self.command_registry = CommandRegistry(agent)
        self.input_processor = InputProcessor(agent, self.command_registry)
        self.publisher: Optional[Any] = None
        self.adapter: Optional[Any] = None

    @abstractmethod
    def setup_publisher_adapter(self) -> Tuple[Any, Any]:
        """Set up publisher and adapter for this mode.

        Subclasses must implement this method to create and configure
        their specific publisher/adapter pair.

        Returns:
            Tuple of (publisher, adapter)

        Example:
            >>> def setup_publisher_adapter(self):
            ...     publisher = EventPublisher(self.agent)
            ...     adapter = CLIAdapter(publisher)
            ...     return publisher, adapter
        """
        pass

    @abstractmethod
    async def run(self) -> None:
        """Run the main interaction loop.

        Subclasses must implement this method to handle their specific
        interaction pattern (REPL, TUI event loop, WebSocket server, etc.).

        Example:
            >>> async def run(self):
            ...     while True:
            ...         user_input = await self.get_input()
            ...         should_continue = await self.process_and_run_agent(user_input)
            ...         if not should_continue:
            ...             break
        """
        pass

    async def initialize(self) -> None:
        """Initialize the interaction mode.

        This method:
        1. Creates a new session or restores existing one
        2. Sets up publisher and adapter
        3. Prepares the mode for interaction

        Raises:
            ModeInitializationError: If initialization fails
        """
        try:
            # Create or restore session
            if self.agent._session_id:
                # Restore existing session
                logger.info(
                    "Restoring session: session_id=%s", self.agent._session_id
                )
                await self.agent.set_session_id(
                    self.agent._session_id, load_history=True
                )
            else:
                # Create new session
                session_id = await self.agent.session_manager.create_session(
                    model_id=self.agent.model.model_id
                )
                await self.agent.set_session_id(session_id, load_history=False)
                logger.info("Created new session: session_id=%s", session_id)

            # Setup publisher and adapter
            self.publisher, self.adapter = self.setup_publisher_adapter()
            logger.debug(
                "Publisher and adapter initialized: publisher=%s, adapter=%s",
                type(self.publisher).__name__,
                type(self.adapter).__name__,
            )

        except Exception as e:
            logger.error("Failed to initialize interaction mode: %s", e)
            raise ModeInitializationError(
                f"Failed to initialize interaction mode: {e}"
            ) from e

    async def cleanup(self) -> None:
        """Clean up resources.

        This method:
        1. Cleans up adapter resources
        2. Performs any mode-specific cleanup

        Subclasses can override this to add additional cleanup logic.
        """
        if self.adapter and hasattr(self.adapter, "cleanup"):
            self.adapter.cleanup()
            logger.debug("Adapter cleaned up")

    async def process_and_run_agent(
        self, user_input: str, stream: bool = True
    ) -> bool:
        """Process user input and run agent if needed.

        This method:
        1. Processes input through InputProcessor (handles commands, pending asks, etc.)
        2. If input should go to agent, adds message to context and runs agent
        3. Handles errors with context recovery
        4. Returns False if user wants to exit

        Args:
            user_input: Raw user input text
            stream: Whether to stream LLM events (default: True)

        Returns:
            True to continue interaction, False to exit

        Example:
            >>> should_continue = await mode.process_and_run_agent("Hello!", stream=True)
            >>> if not should_continue:
            ...     print("Goodbye!")
            ...     break
        """
        # Process input
        result = await self.input_processor.process(user_input)

        # Check for exit commands
        if user_input.strip() in ["/quit", "/exit"]:
            return False

        # If command was handled, don't run agent
        if result.action == "handled":
            if result.error:
                print(f"Error: {result.error}")
            return True

        # Add message to context and run agent
        if result.message:
            # Save message length for error recovery
            initial_msg_count = len(self.agent.context.messages)

            try:
                # Add user message
                self.agent.context.messages.append(result.message)

                # Update system prompt if skill was invoked
                if result.invoked_skill_id:
                    system_prompt = self.agent.get_system_prompt_for_run(
                        result.invoked_skill_id
                    )
                    self.agent.context.systemPrompt = system_prompt

                # Run agent
                await self.agent.agent.run(stream_llm_events=stream)

                # Print newline after streaming output
                if stream:
                    print()

            except KeyboardInterrupt:
                # User interrupted - restore context
                logger.info("User interrupted agent execution")
                print("\n^C")
                self.agent.context.messages = self.agent.context.messages[
                    :initial_msg_count
                ]
                return True

            except Exception as e:
                # Error during execution - restore context and log
                logger.error("Agent execution failed: %s", e, exc_info=True)
                print(f"\nError: {e}")
                self.agent.context.messages = self.agent.context.messages[
                    :initial_msg_count
                ]
                return True

        return True


__all__ = ["InteractionMode"]

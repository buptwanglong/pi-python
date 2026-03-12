"""
TUI Mode Integration (New Architecture)

Integrates basket-tui v2 with basket-assistant.
"""

import asyncio
import logging
from pathlib import Path
from typing import Optional

from basket_tui.app import PiCodingAgentApp
from basket_tui.core.events import UserInputEvent
from basket_tui.core.state_machine import Phase
from basket_ai.types import UserMessage

logger = logging.getLogger(__name__)


async def run_tui_mode(
    coding_agent,
    max_cols: Optional[int] = None,
) -> None:
    """
    Run TUI mode with new architecture

    Args:
        coding_agent: AssistantAgent instance
        max_cols: Maximum column width
    """
    # Create or restore session
    if not getattr(coding_agent, "_session_id", None):
        session_id = await coding_agent.session_manager.create_session(
            coding_agent.model.id
        )
        await coding_agent.set_session_id(session_id)
        logger.info(f"Created new session: {session_id}")
    else:
        logger.info(f"Using existing session: {coding_agent._session_id}")

    # Create TUI app
    app = PiCodingAgentApp(
        agent=coding_agent.agent,
        coding_agent=coding_agent,
        max_cols=max_cols,
    )

    # Handle user input
    async def handle_user_input(text: str) -> None:
        """Handle user input and run agent"""
        # Add user message to context
        coding_agent.context.messages.append(
            UserMessage(role="user", content=text)
        )

        # Transition to waiting phase
        app.transition_phase(Phase.WAITING_MODEL)

        try:
            # Run agent
            await coding_agent._run_with_trajectory_if_enabled(
                stream_llm_events=True
            )

            # Persist messages
            if coding_agent._session_id:
                await coding_agent.session_manager.append_messages(
                    coding_agent._session_id, [coding_agent.context.messages[-1]]
                )

        except Exception as e:
            logger.exception("Agent run failed")
            app.message_renderer.add_system_message(f"Error: {e}")
        finally:
            # Transition back to idle
            app.transition_phase(Phase.IDLE)

    # Subscribe to user input events
    app.event_bus.subscribe(
        UserInputEvent, lambda e: asyncio.create_task(handle_user_input(e.text))
    )

    # Set input callback
    app.input_handler.set_callback(handle_user_input)

    # Load history messages
    for msg in coding_agent.context.messages:
        role = getattr(msg, "role", "assistant")
        content = getattr(msg, "content", "")
        if isinstance(content, list):
            content = "\n".join(
                getattr(block, "text", "")
                for block in content
                if hasattr(block, "text")
            )
        if content:
            if role == "user":
                app.message_renderer.add_user_message(content)
            else:
                app.message_renderer.add_system_message(f"[{role}] {content}")

    # Run app
    await app.run_async()

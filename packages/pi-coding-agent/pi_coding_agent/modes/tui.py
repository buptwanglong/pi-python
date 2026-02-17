"""
TUI Mode for Pi Coding Agent

Runs the coding agent with an interactive TUI interface.
"""

import asyncio
from typing import Optional

from pi_agent import Agent
from pi_tui import PiCodingAgentApp


async def run_tui_mode(agent: Agent) -> None:
    """
    Run the coding agent in TUI mode.

    Args:
        agent: The Pi Agent instance to connect to the TUI

    This function:
    1. Creates a TUI app instance
    2. Connects agent events to TUI display methods
    3. Sets up input handling to forward messages to the agent
    4. Runs the TUI application
    """
    app = PiCodingAgentApp(agent=agent)

    # Track current response being built
    current_response = {"text": "", "thinking": "", "in_thinking": False}

    def on_text_delta(event):
        """Handle text delta events from the agent."""
        delta = event.get("delta", "")
        current_response["text"] += delta

        # Use call_soon_threadsafe to update from agent thread
        app.call_from_thread(app.append_text, delta)

    def on_thinking_delta(event):
        """Handle thinking delta events from the agent."""
        delta = event.get("delta", "")
        current_response["thinking"] += delta

        if not current_response["in_thinking"]:
            current_response["in_thinking"] = True
            # Show thinking header
            app.call_from_thread(app.append_message, "system", "💭 Thinking...")

        app.call_from_thread(app.append_thinking, delta)

    def on_tool_call_start(event):
        """Handle tool call start events from the agent."""
        tool_name = event.get("tool_name", "unknown")
        # Note: tool args might not be available yet in start event
        app.call_from_thread(app.show_tool_call, tool_name)

    def on_tool_call_end(event):
        """Handle tool call end events from the agent."""
        error = event.get("error")

        if error:
            app.call_from_thread(app.show_tool_result, str(error), success=False)
        else:
            # Tool result will be in the context, we just show success
            app.call_from_thread(app.show_tool_result, "Tool executed successfully", success=True)

    def on_agent_turn_complete(event):
        """Handle agent turn completion."""
        # Reset response tracking
        current_response["text"] = ""
        current_response["thinking"] = ""
        current_response["in_thinking"] = False

    def on_agent_error(event):
        """Handle agent errors."""
        error = event.get("error", "Unknown error")
        app.call_from_thread(app.append_message, "system", f"❌ Error: {error}")

    # Register event handlers
    agent.on("text_delta", on_text_delta)
    agent.on("thinking_delta", on_thinking_delta)
    agent.on("agent_tool_call_start", on_tool_call_start)
    agent.on("agent_tool_call_end", on_tool_call_end)
    agent.on("agent_turn_complete", on_agent_turn_complete)
    agent.on("agent_error", on_agent_error)

    async def handle_user_input(user_input: str):
        """
        Handle user input by forwarding to the agent.

        Args:
            user_input: The user's message
        """
        from pi_ai.types import UserMessage

        # Add user message to context
        agent.context.messages.append(
            UserMessage(
                role="user",
                content=user_input,
                timestamp=0,
            )
        )

        # Show thinking indicator
        app.call_from_thread(app.append_message, "assistant", "")

        # Run agent (this will emit events we're listening to)
        try:
            await agent.run(stream_llm_events=True)
        except Exception as e:
            app.call_from_thread(app.append_message, "system", f"❌ Error: {e}")

    # Set input handler
    app.set_input_handler(handle_user_input)

    # Run the app
    await app.run_async()


__all__ = ["run_tui_mode"]

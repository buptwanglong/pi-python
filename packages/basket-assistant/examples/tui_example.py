"""
Example: Running Pi Coding Agent with TUI

This example demonstrates how to use the TUI mode with the coding agent.
"""

import asyncio
import os
from basket_assistant.main import CodingAgent


async def main():
    """Run the TUI example."""
    # Check for API key
    if not os.getenv("OPENAI_API_KEY") and not os.getenv("ANTHROPIC_API_KEY"):
        print("⚠️  Warning: No API key found!")
        print("Set OPENAI_API_KEY or ANTHROPIC_API_KEY environment variable")
        print()
        print("Example:")
        print("  export OPENAI_API_KEY='your-key-here'")
        print("  poetry run python examples/tui_example.py")
        return

    print("🚀 Starting Pi Coding Agent with TUI...")
    print()

    try:
        # Create coding agent
        agent = CodingAgent()

        # Import TUI mode
        from basket_assistant.modes.tui import run_tui_mode

        # Run in TUI mode
        await run_tui_mode(agent.agent)

    except KeyboardInterrupt:
        print("\n\n👋 Goodbye!")
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())

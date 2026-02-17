"""
Example Extension: Project Context

Adds tools to manage project-specific context and knowledge.
"""

import json
from pathlib import Path
from pydantic import BaseModel, Field
from typing import Optional


class ContextAddParams(BaseModel):
    """Parameters for adding context."""

    key: str = Field(..., description="Context key (e.g., 'architecture', 'api_patterns')")
    value: str = Field(..., description="Context value/description")
    category: str = Field(default="general", description="Context category")


class ContextGetParams(BaseModel):
    """Parameters for getting context."""

    key: str = Field(..., description="Context key to retrieve")


def setup(pi):
    """
    Extension setup function.

    Args:
        pi: ExtensionAPI instance
    """

    # Context storage location
    context_file = Path.cwd() / ".pi" / "project_context.json"

    def load_context() -> dict:
        """Load project context from file."""
        if context_file.exists():
            try:
                with open(context_file) as f:
                    return json.load(f)
            except Exception:
                return {}
        return {}

    def save_context(context: dict) -> None:
        """Save project context to file."""
        context_file.parent.mkdir(parents=True, exist_ok=True)
        with open(context_file, "w") as f:
            json.dump(context, f, indent=2)

    @pi.register_tool(
        name="context_add",
        description="Add project-specific context or knowledge",
        parameters=ContextAddParams,
    )
    async def context_add_tool(key: str, value: str, category: str = "general") -> str:
        """Add context to project knowledge base."""
        try:
            context = load_context()

            if category not in context:
                context[category] = {}

            context[category][key] = value
            save_context(context)

            return f"✅ Added context: {category}/{key}"

        except Exception as e:
            return f"❌ Error adding context: {e}"

    @pi.register_tool(
        name="context_get",
        description="Retrieve project-specific context",
        parameters=ContextGetParams,
    )
    async def context_get_tool(key: str) -> str:
        """Get context from project knowledge base."""
        try:
            context = load_context()

            # Search across all categories
            results = []
            for category, items in context.items():
                if key in items:
                    results.append(f"[{category}] {key}: {items[key]}")

            if results:
                return "\n".join(results)
            else:
                return f"⚠️  No context found for key: {key}"

        except Exception as e:
            return f"❌ Error retrieving context: {e}"

    @pi.register_command("/context")
    def context_command(args: str):
        """Show all project context."""
        try:
            context = load_context()

            if not context:
                print("📝 No project context stored yet")
                print("   Use context_add tool to add knowledge")
                return

            print("📝 Project Context:")
            for category, items in context.items():
                print(f"\n  [{category}]")
                for key, value in items.items():
                    # Truncate long values
                    display_value = value if len(value) <= 60 else value[:57] + "..."
                    print(f"    • {key}: {display_value}")

        except Exception as e:
            print(f"❌ Error: {e}")

    @pi.register_command("/context-clear")
    def context_clear_command(args: str):
        """Clear all project context."""
        try:
            if context_file.exists():
                context_file.unlink()
                print("✅ Project context cleared")
            else:
                print("⚠️  No context to clear")
        except Exception as e:
            print(f"❌ Error: {e}")

    # Add context at startup if configured
    @pi.on("agent_tool_call_end")
    async def on_tool_complete(event, ctx=None):
        """Auto-save interesting tool results as context."""
        tool_name = event.get("tool_name")
        result = event.get("result")

        # Example: Auto-save successful grep patterns
        if tool_name == "grep" and result and "found" in str(result).lower():
            # Could auto-extract useful patterns
            pass

    print("✅ Project context extension loaded!")
    print("   Tools: context_add, context_get")
    print("   Commands: /context, /context-clear")
    print(f"   Storage: {context_file}")

"""
Example Extension: Git Helper

Adds convenient git operations as tools and commands.
"""

import subprocess
from pydantic import BaseModel, Field


class GitCommitParams(BaseModel):
    """Parameters for git commit tool."""

    message: str = Field(..., description="Commit message")
    add_all: bool = Field(default=True, description="Stage all changes before commit")


class GitBranchParams(BaseModel):
    """Parameters for git branch tool."""

    branch_name: str = Field(..., description="Branch name")
    create: bool = Field(default=False, description="Create the branch if it doesn't exist")


def setup(basket):
    """
    Extension setup function.

    Args:
        basket: ExtensionAPI instance
    """

    @basket.register_tool(
        name="git_commit",
        description="Create a git commit with a message",
        parameters=GitCommitParams,
    )
    async def git_commit_tool(message: str, add_all: bool = True) -> str:
        """Create a git commit."""
        try:
            # Stage changes
            if add_all:
                result = subprocess.run(
                    ["git", "add", "-A"],
                    capture_output=True,
                    text=True,
                    timeout=10,
                )
                if result.returncode != 0:
                    return f"❌ Git add failed: {result.stderr}"

            # Commit
            result = subprocess.run(
                ["git", "commit", "-m", message],
                capture_output=True,
                text=True,
                timeout=10,
            )

            if result.returncode == 0:
                return f"✅ Committed: {message}\n{result.stdout}"
            else:
                return f"❌ Commit failed: {result.stderr}"

        except subprocess.TimeoutExpired:
            return "❌ Git operation timed out"
        except Exception as e:
            return f"❌ Git error: {e}"

    @basket.register_tool(
        name="git_branch",
        description="Switch to a git branch, optionally creating it",
        parameters=GitBranchParams,
    )
    async def git_branch_tool(branch_name: str, create: bool = False) -> str:
        """Switch to a git branch."""
        try:
            if create:
                # Create and switch
                result = subprocess.run(
                    ["git", "checkout", "-b", branch_name],
                    capture_output=True,
                    text=True,
                    timeout=10,
                )
            else:
                # Just switch
                result = subprocess.run(
                    ["git", "checkout", branch_name],
                    capture_output=True,
                    text=True,
                    timeout=10,
                )

            if result.returncode == 0:
                return f"✅ Switched to branch: {branch_name}\n{result.stdout}"
            else:
                return f"❌ Branch switch failed: {result.stderr}"

        except subprocess.TimeoutExpired:
            return "❌ Git operation timed out"
        except Exception as e:
            return f"❌ Git error: {e}"

    @basket.register_command("/git-status")
    def git_status_command(args: str):
        """Show git status."""
        try:
            result = subprocess.run(
                ["git", "status", "--short"],
                capture_output=True,
                text=True,
                timeout=5,
            )
            if result.returncode == 0:
                print("📊 Git Status:")
                print(result.stdout if result.stdout else "  (no changes)")
            else:
                print(f"❌ Error: {result.stderr}")
        except Exception as e:
            print(f"❌ Git error: {e}")

    @basket.register_command("/git-log")
    def git_log_command(args: str):
        """Show recent git log."""
        count = args.strip() or "5"
        try:
            result = subprocess.run(
                ["git", "log", f"-{count}", "--oneline"],
                capture_output=True,
                text=True,
                timeout=5,
            )
            if result.returncode == 0:
                print(f"📜 Recent {count} commits:")
                print(result.stdout)
            else:
                print(f"❌ Error: {result.stderr}")
        except Exception as e:
            print(f"❌ Git error: {e}")

    # Event handler to track git operations
    @basket.on("agent_tool_call_start")
    async def on_git_tool(event, ctx=None):
        """Log git tool usage."""
        tool_name = event.get("tool_name")
        if tool_name and tool_name.startswith("git_"):
            print(f"🔧 Git operation: {tool_name}")

    print("✅ Git helper extension loaded!")
    print("   Tools: git_commit, git_branch")
    print("   Commands: /git-status, /git-log")

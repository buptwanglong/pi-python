"""
Example Extension: Code Formatter

Demonstrates adding a code formatting tool via extension.
"""

import subprocess
from pathlib import Path
from pydantic import BaseModel, Field


class FormatParams(BaseModel):
    """Parameters for the format tool."""

    file_path: str = Field(..., description="Path to file to format")
    formatter: str = Field(default="auto", description="Formatter to use (auto, black, prettier, rustfmt)")


def setup(pi):
    """
    Extension setup function.

    Args:
        pi: ExtensionAPI instance
    """

    @pi.register_tool(
        name="format",
        description="Format a code file using appropriate formatter",
        parameters=FormatParams,
    )
    async def format_tool(file_path: str, formatter: str = "auto") -> str:
        """Format a code file."""
        path = Path(file_path)

        if not path.exists():
            return f"Error: File not found: {file_path}"

        # Auto-detect formatter
        if formatter == "auto":
            suffix = path.suffix
            if suffix == ".py":
                formatter = "black"
            elif suffix in [".js", ".ts", ".jsx", ".tsx", ".json", ".css", ".html"]:
                formatter = "prettier"
            elif suffix == ".rs":
                formatter = "rustfmt"
            else:
                return f"Error: No formatter available for {suffix} files"

        # Run formatter
        try:
            if formatter == "black":
                result = subprocess.run(
                    ["black", str(path)],
                    capture_output=True,
                    text=True,
                    timeout=30,
                )
            elif formatter == "prettier":
                result = subprocess.run(
                    ["prettier", "--write", str(path)],
                    capture_output=True,
                    text=True,
                    timeout=30,
                )
            elif formatter == "rustfmt":
                result = subprocess.run(
                    ["rustfmt", str(path)],
                    capture_output=True,
                    text=True,
                    timeout=30,
                )
            else:
                return f"Error: Unknown formatter: {formatter}"

            if result.returncode == 0:
                return f"✅ Formatted {path.name} with {formatter}"
            else:
                return f"❌ Format failed: {result.stderr}"

        except FileNotFoundError:
            return f"❌ Formatter '{formatter}' not found. Please install it first."
        except subprocess.TimeoutExpired:
            return f"❌ Format timed out after 30 seconds"
        except Exception as e:
            return f"❌ Format error: {e}"

    @pi.register_command("/format")
    def format_command(args: str):
        """Format a file via command."""
        if not args:
            print("Usage: /format <file_path> [formatter]")
            return

        parts = args.split()
        file_path = parts[0]
        formatter = parts[1] if len(parts) > 1 else "auto"

        print(f"🔧 Formatting {file_path} with {formatter}...")

    print("✅ Code formatter extension loaded!")
    print("   Use 'format' tool or /format command")

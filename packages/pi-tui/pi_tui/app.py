"""
Main TUI Application for Pi Coding Agent

This module provides the main Textual App that handles:
- User input and interaction
- Streaming LLM response display
- Tool call visualization
- Agent event handling
"""

from typing import Optional
from textual.app import App, ComposeResult
from textual.containers import Vertical
from textual.widgets import Header, Footer, Input
from textual.binding import Binding
from rich.markdown import Markdown
from rich.text import Text

from .components.streaming_log import StreamingLog


class PiCodingAgentApp(App):
    """
    Interactive TUI for Pi Coding Agent.

    Features:
    - Real-time streaming of LLM responses
    - Markdown rendering with syntax highlighting
    - Tool execution display
    - Multi-line input support
    """

    TITLE = "Pi Coding Agent"
    SUB_TITLE = "Interactive AI Coding Assistant"

    BINDINGS = [
        Binding("ctrl+c", "quit", "Quit", priority=True),
        Binding("ctrl+l", "clear", "Clear"),
        Binding("ctrl+d", "toggle_dark", "Toggle Dark Mode"),
    ]

    CSS = """
    #output-container {
        height: 1fr;
        border: solid $primary;
        margin: 1;
    }

    #output {
        height: 100%;
    }

    #input {
        dock: bottom;
        height: 3;
        border: solid $accent;
        margin: 0 1;
    }

    .thinking {
        color: $text-muted;
        italic: true;
    }

    .tool-call {
        color: $success;
        bold: true;
    }

    .error {
        color: $error;
        bold: true;
    }
    """

    def __init__(self, agent=None, **kwargs):
        """
        Initialize the TUI app.

        Args:
            agent: Optional Pi Agent instance to connect to
            **kwargs: Additional arguments for Textual App
        """
        super().__init__(**kwargs)
        self.agent = agent
        self._input_handler = None

    def compose(self) -> ComposeResult:
        """Create the UI layout."""
        yield Header()
        with Vertical(id="output-container"):
            yield StreamingLog(id="output", auto_scroll=True, wrap=True)
        yield Input(
            id="input",
            placeholder="Type your message... (Ctrl+C to quit)",
        )
        yield Footer()

    def on_mount(self) -> None:
        """Called when app is mounted."""
        # Focus input by default
        self.query_one("#input", Input).focus()

        # Display welcome message
        self.append_message("system", "Welcome to Pi Coding Agent!")
        self.append_message("system", "Type your request and press Enter.")

    async def on_input_submitted(self, event: Input.Submitted) -> None:
        """
        Handle user input submission.

        Args:
            event: Input submitted event
        """
        user_input = event.value.strip()

        if not user_input:
            return

        # Clear input
        event.input.value = ""

        # Display user message
        self.append_message("user", user_input)

        # Forward to agent if connected
        if self.agent and self._input_handler:
            await self._input_handler(user_input)
        else:
            # Echo response (for testing without agent)
            self.append_message("assistant", f"Echo: {user_input}")

    def set_input_handler(self, handler):
        """
        Set the callback for handling user input.

        Args:
            handler: Async function that takes user_input string
        """
        self._input_handler = handler

    def append_message(self, role: str, content: str) -> None:
        """
        Append a message to the output log.

        Args:
            role: Message role (user, assistant, system)
            content: Message content
        """
        log = self.query_one("#output", StreamingLog)

        if role == "user":
            log.write(Text(f"👤 You: {content}", style="bold cyan"))
        elif role == "assistant":
            log.write(Text(f"🤖 Assistant: {content}", style="bold green"))
        elif role == "system":
            log.write(Text(f"ℹ️  {content}", style="dim"))
        else:
            log.write(content)

    def append_text(self, text: str) -> None:
        """
        Append streaming text to the output.

        Args:
            text: Text delta to append
        """
        log = self.query_one("#output", StreamingLog)
        log.write(text, expand=True)

    def append_thinking(self, thinking: str) -> None:
        """
        Append thinking/reasoning text.

        Args:
            thinking: Thinking content
        """
        log = self.query_one("#output", StreamingLog)
        log.write(Text(f"💭 {thinking}", style="italic dim yellow"))

    def show_tool_call(self, tool_name: str, args: Optional[dict] = None) -> None:
        """
        Display a tool call.

        Args:
            tool_name: Name of the tool being called
            args: Optional tool arguments
        """
        log = self.query_one("#output", StreamingLog)

        if args:
            args_str = ", ".join(f"{k}={v}" for k, v in args.items())
            log.write(Text(f"🔧 Tool: {tool_name}({args_str})", style="bold magenta"))
        else:
            log.write(Text(f"🔧 Tool: {tool_name}", style="bold magenta"))

    def show_tool_result(self, result: str, success: bool = True) -> None:
        """
        Display a tool result.

        Args:
            result: Tool result content
            success: Whether the tool execution was successful
        """
        log = self.query_one("#output", StreamingLog)

        if success:
            log.write(Text(f"✅ Result: {result}", style="green"))
        else:
            log.write(Text(f"❌ Error: {result}", style="bold red"))

    def append_markdown(self, markdown_text: str) -> None:
        """
        Append markdown-formatted text.

        Args:
            markdown_text: Markdown content to render
        """
        log = self.query_one("#output", StreamingLog)

        # Use Rich's Markdown for rendering in the log
        md = Markdown(markdown_text)
        log.write(md)

    def show_code_block(self, code: str, language: str = "python") -> None:
        """
        Display a code block with syntax highlighting.

        Args:
            code: Code content
            language: Programming language for highlighting
        """
        from rich.syntax import Syntax

        log = self.query_one("#output", StreamingLog)
        syntax = Syntax(
            code,
            language,
            theme="monokai",
            line_numbers=True,
            word_wrap=False,
            background_color="#1e1e1e",
        )
        log.write(syntax)

    def action_clear(self) -> None:
        """Clear the output log."""
        log = self.query_one("#output", StreamingLog)
        log.clear()
        self.append_message("system", "Output cleared.")

    def action_toggle_dark(self) -> None:
        """Toggle dark mode."""
        self.dark = not self.dark


# Example usage
if __name__ == "__main__":
    app = PiCodingAgentApp()
    app.run()

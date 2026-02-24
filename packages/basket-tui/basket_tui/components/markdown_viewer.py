"""
Markdown Viewer Component

A component for rendering Markdown content with syntax highlighting.
"""

from textual.widgets import Markdown as TextualMarkdown
from textual.widget import Widget


class MarkdownViewer(TextualMarkdown):
    """
    Enhanced Markdown viewer with code syntax highlighting.

    Features:
    - Full Markdown support (headers, lists, code blocks, etc.)
    - Syntax highlighting for code blocks
    - Support for inline code
    - Hyperlink rendering
    """

    DEFAULT_CSS = """
    MarkdownViewer {
        padding: 1;
        background: $surface;
        border: solid $primary;
    }

    MarkdownViewer > * {
        margin: 0 0 1 0;
    }

    MarkdownViewer H1 {
        color: $accent;
        text-style: bold;
        background: $panel;
        padding: 1;
        border-bottom: heavy $accent;
    }

    MarkdownViewer H2 {
        color: $accent;
        text-style: bold;
        border-bottom: solid $primary;
        padding: 0 0 0 1;
    }

    MarkdownViewer H3 {
        color: $text;
        text-style: bold;
        padding: 0 0 0 1;
    }

    MarkdownViewer Code {
        background: $panel;
        color: $success;
    }

    MarkdownViewer BlockQuote {
        background: $panel;
        border-left: wide $accent;
        padding: 0 0 0 2;
        margin: 1 0;
    }

    MarkdownViewer Link {
        color: $info;
        text-style: underline;
    }
    """

    def __init__(self, markdown: str = "", **kwargs):
        """
        Initialize the Markdown viewer.

        Args:
            markdown: Markdown content to display
            **kwargs: Additional arguments for Markdown widget
        """
        super().__init__(markdown, **kwargs)


class CodeBlock(Widget):
    """
    A specialized widget for displaying code with syntax highlighting.

    This is a simpler alternative to full Markdown when you just need
    to display code.
    """

    DEFAULT_CSS = """
    CodeBlock {
        height: auto;
        background: $panel;
        border: solid $primary;
        padding: 1;
    }

    CodeBlock > Static {
        padding: 0;
    }
    """

    def __init__(self, code: str, language: str = "python", **kwargs):
        """
        Initialize the code block.

        Args:
            code: Code content to display
            language: Programming language for syntax highlighting
            **kwargs: Additional arguments for Widget
        """
        super().__init__(**kwargs)
        self._code = code
        self._language = language

    def compose(self):
        """Compose the code block widget."""
        from textual.widgets import Static
        from rich.syntax import Syntax

        # Create syntax-highlighted code
        syntax = Syntax(
            self._code,
            self._language,
            theme="monokai",
            line_numbers=True,
            word_wrap=False,
        )

        yield Static(syntax)

    def update_code(self, code: str, language: str = None):
        """
        Update the code content.

        Args:
            code: New code content
            language: Optional new language for syntax highlighting
        """
        self._code = code
        if language is not None:
            self._language = language
        self.refresh()

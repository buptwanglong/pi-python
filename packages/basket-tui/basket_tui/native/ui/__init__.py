"""Layout, input handling, and pickers for terminal-native TUI."""

from .completer import SlashCommandCompleter
from .input_handler import (
    HELP_LINES,
    SLASH_COMMANDS,
    InputResult,
    OutputPut,
    handle_input,
    handle_slash_command,
    open_picker,
)
from .banner import build_banner_lines, resolve_basket_version
from .doctor import collect_doctor_notices, format_doctor_panel
from .exit_confirm import ExitConfirmState
from .footer import SPINNER_FRAMES, format_footer, spinner_frame
from .layout import build_layout
from .question_panel import (
    FREE_TEXT_LABEL,
    format_question_panel,
    new_question_state,
    question_panel_height,
)
from .todo_panel import MAX_PANEL_LINES, format_todo_panel, todo_panel_height

__all__ = [
    "FREE_TEXT_LABEL",
    "HELP_LINES",
    "SLASH_COMMANDS",
    "InputResult",
    "MAX_PANEL_LINES",
    "OutputPut",
    "SPINNER_FRAMES",
    "ExitConfirmState",
    "SlashCommandCompleter",
    "build_banner_lines",
    "build_layout",
    "collect_doctor_notices",
    "format_doctor_panel",
    "format_footer",
    "format_question_panel",
    "format_todo_panel",
    "new_question_state",
    "question_panel_height",
    "resolve_basket_version",
    "spinner_frame",
    "handle_input",
    "handle_slash_command",
    "open_picker",
    "todo_panel_height",
]

"""
Constants for Pi TUI Application

This module defines all CSS selector IDs, CSS classes, UI constants,
and message prefixes/emojis used throughout the application.
"""

# CSS Selector IDs
OUTPUT_CONTAINER_ID = "output-container"
OUTPUT_ID = "output"
TODO_PANEL_ID = "todo-panel"
PLAN_MODE_PANEL_ID = "plan-mode-panel"
INPUT_ID = "input"

# CSS Classes
MESSAGE_BLOCK_CLASS = "message-block"
MESSAGE_USER_CLASS = "message-user"
MESSAGE_ASSISTANT_CLASS = "message-assistant"
MESSAGE_SYSTEM_CLASS = "message-system"
MESSAGE_TOOL_CLASS = "message-tool"
TOOL_BLOCK_CLASS = "tool-block"

# UI Constants
MIN_INPUT_HEIGHT = 3
MAX_INPUT_HEIGHT = 10

# Message Prefixes (minimal - remove emojis)
THINKING_PREFIX = "Thinking..."
ERROR_PREFIX = "Error:"
INFO_PREFIX = "Info:"

# Text Styles (keep clean)
THINKING_STYLE = "italic dim"
USER_MESSAGE_STYLE = "bold"
SYSTEM_MESSAGE_STYLE = "dim"

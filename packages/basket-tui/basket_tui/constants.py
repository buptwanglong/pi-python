"""
Constants for Pi TUI Application

This module defines all CSS selector IDs, CSS classes, UI constants,
and message prefixes/emojis used throughout the application.
"""

# CSS Selector IDs
OUTPUT_CONTAINER_ID = "output-container"
CHAT_LOG_ID = "output-container"  # Semantic alias for Phase 3 message list
OUTPUT_ID = "output"
TODO_PANEL_ID = "todo-panel"
PLAN_MODE_PANEL_ID = "plan-mode-panel"
INPUT_ID = "input"
INPUT_AREA_ID = "input"  # Semantic alias
INPUT_HINT_ID = "input-hint"
INPUT_ERROR_ID = "input-error"
STATUS_BAR_ID = "status-bar"
STATUS_PHASE_ID = "status-phase"
STATUS_MODEL_ID = "status-model"
STATUS_SESSION_ID = "status-session"
STATUS_QUEUE_ID = "status-queue"
HEADER_CONTEXT_ID = "header-context"
LIVE_OUTPUT_ID = "live-output"
MESSAGE_LIST_ID = "message-list"

# Status bar column widths (character widths for padding)
STATUS_PHASE_WIDTH = 14
STATUS_MODEL_WIDTH = 20
STATUS_SESSION_WIDTH = 12
STATUS_QUEUE_WIDTH = 12

# Input area shortcut hint (OpenClaw-style)
SHORTCUT_HINT = "Ctrl+G 停止 | Ctrl+Shift+T 转录 | Ctrl+E 展开工具 | /help 帮助"

# CSS Classes
MESSAGE_BLOCK_CLASS = "message-block"
MESSAGE_USER_CLASS = "message-user"
MESSAGE_ASSISTANT_CLASS = "message-assistant"
MESSAGE_SYSTEM_CLASS = "message-system"
MESSAGE_ERROR_CLASS = "message-error"
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

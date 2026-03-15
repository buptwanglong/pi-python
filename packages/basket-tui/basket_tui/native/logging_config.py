"""Logging configuration for basket-tui.

This module provides centralized logging setup for the basket-tui package.
Log level can be controlled via (in priority order):
1. BASKET_LOG_LEVEL environment variable (global for all basket modules)
2. BASKET_TUI_LOG_LEVEL environment variable (TUI-specific, backward compat)
3. settings.json log_level field
4. Default: INFO

Log output destinations:
- File: ~/.basket/logs/basket.log (auto-created, 10MB max, 5 backups)
- Console: sys.stderr (only for non-TUI modes or when BASKET_LOG_TO_CONSOLE=1)
"""

import logging
import os
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Optional

DEFAULT_FORMAT = "[%(asctime)s] [%(levelname)-8s] [%(name)s:%(lineno)d] %(message)s"
DEFAULT_DATE_FORMAT = "%Y-%m-%d %H:%M:%S"
DEFAULT_LOG_DIR = Path.home() / ".basket" / "logs"
DEFAULT_LOG_FILE = DEFAULT_LOG_DIR / "basket.log"


def get_log_level_from_settings() -> Optional[str]:
    """Try to get log level from settings.json file.

    Returns:
        Log level string or None if not found/not loadable.
    """
    try:
        # Try to import Settings from basket-assistant
        from pathlib import Path
        import json

        # Look for settings.json in ~/.basket/settings.json
        settings_path = Path.home() / ".basket" / "settings.json"
        if settings_path.exists():
            with open(settings_path) as f:
                data = json.load(f)
                return data.get("log_level")
    except Exception:
        # Silently ignore if settings can't be loaded
        pass
    return None


def setup_logging(level: str | None = None, log_to_console: bool = False) -> None:
    """Setup logging configuration for basket modules.

    Priority order for log level:
    1. Provided level parameter
    2. BASKET_LOG_LEVEL environment variable (global)
    3. BASKET_TUI_LOG_LEVEL environment variable (backward compat)
    4. settings.json log_level field
    5. Default: INFO

    Log output:
    - Always logs to file: ~/.basket/logs/basket.log
    - Optionally logs to console (stderr) if log_to_console=True or BASKET_LOG_TO_CONSOLE=1

    Args:
        level: Log level (DEBUG/INFO/WARNING/ERROR).
               If None, uses priority order above.
        log_to_console: If True, also output logs to sys.stderr.
                        Can be overridden by BASKET_LOG_TO_CONSOLE env var.
    """
    if level is None:
        # Priority 1: Global BASKET_LOG_LEVEL
        level = os.getenv("BASKET_LOG_LEVEL")

        # Priority 2: Module-specific BASKET_TUI_LOG_LEVEL (backward compat)
        if level is None:
            level = os.getenv("BASKET_TUI_LOG_LEVEL")

        # Priority 3: Settings file
        if level is None:
            level = get_log_level_from_settings()

        # Priority 4: Default
        if level is None:
            level = "INFO"

    level = level.upper()
    numeric_level = getattr(logging, level, logging.INFO)

    # Create log directory if it doesn't exist
    DEFAULT_LOG_DIR.mkdir(parents=True, exist_ok=True)

    # Configure root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(numeric_level)
    root_logger.handlers.clear()  # Clear existing handlers

    # File handler (always enabled)
    file_handler = RotatingFileHandler(
        DEFAULT_LOG_FILE,
        maxBytes=10 * 1024 * 1024,  # 10MB
        backupCount=5,
        encoding="utf-8",
    )
    file_handler.setLevel(numeric_level)
    file_handler.setFormatter(
        logging.Formatter(DEFAULT_FORMAT, datefmt=DEFAULT_DATE_FORMAT)
    )
    root_logger.addHandler(file_handler)

    # Console handler (optional, for debugging or non-TUI modes)
    console_enabled = os.getenv("BASKET_LOG_TO_CONSOLE", "0") == "1" or log_to_console
    if console_enabled:
        console_handler = logging.StreamHandler(sys.stderr)
        console_handler.setLevel(numeric_level)
        console_handler.setFormatter(
            logging.Formatter(DEFAULT_FORMAT, datefmt=DEFAULT_DATE_FORMAT)
        )
        root_logger.addHandler(console_handler)

    # Set basket_* loggers to the specified level (all basket modules)
    for logger_name in ["basket_tui", "basket_ai", "basket_agent", "basket_assistant"]:
        basket_logger = logging.getLogger(logger_name)
        basket_logger.setLevel(numeric_level)
        basket_logger.propagate = True  # Ensure logs propagate to root logger

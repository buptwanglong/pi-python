"""Main entry point for the Basket CLI.

This module delegates to the ``cli/`` subpackage for all functionality.
It exists purely so that the ``pyproject.toml`` entry-point
(``basket_assistant.main:main``) and ``python -m basket_assistant`` keep
working without any configuration changes.
"""

from .cli import main, main_async

__all__ = ["main", "main_async"]

if __name__ == "__main__":
    import sys

    sys.exit(main())

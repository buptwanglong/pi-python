"""python -m basket_assistant: same as basket CLI (init, agent list|add|remove, gateway, interactive)."""

from __future__ import annotations

import sys

from basket_assistant.main import main as cli_main


if __name__ == "__main__":
    sys.exit(cli_main())

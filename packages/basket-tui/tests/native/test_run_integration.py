"""Integration test for native run: dispatch of WebSocket events produces expected output."""

import re
import threading
from unittest.mock import patch

import pytest

from basket_tui.native.run import _dispatch_ws_message
from basket_tui.native.stream import StreamAssembler

_ANSI = re.compile(r"\x1b\[[0-9;]*m|\x1b\]8;;.*?\x1b\\\\")


def _strip_ansi(s: str) -> str:
    return _ANSI.sub("", s)


def test_dispatch_text_delta_agent_complete_prints_assistant_line():
    """Simulate WebSocket stream: text_delta + agent_complete; assert printed line contains assistant text."""
    assembler = StreamAssembler()
    width = 80
    print_lock = threading.Lock()
    printed: list[str] = []

    with patch("basket_tui.native.run.print", side_effect=lambda *a, **k: printed.append(" ".join(str(x) for x in a))):
        _dispatch_ws_message({"type": "text_delta", "delta": "Hello "}, assembler, width, print_lock)
        _dispatch_ws_message({"type": "text_delta", "delta": "world"}, assembler, width, print_lock)
        _dispatch_ws_message({"type": "agent_complete"}, assembler, width, print_lock)

    assert len(assembler.messages) == 1
    assert assembler.messages[0]["content"] == "Hello world"
    combined = _strip_ansi(" ".join(printed))
    assert "Hello" in combined and "world" in combined, f"Expected 'Hello world' in printed: {combined!r}"

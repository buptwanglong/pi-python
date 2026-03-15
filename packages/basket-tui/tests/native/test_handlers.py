"""Tests for make_handlers (GatewayHandlers from dispatch state)."""

import pytest

from basket_tui.native.handle import make_handlers
from basket_tui.native.pipeline import StreamAssembler


def test_make_handlers_returns_dict_like_on_text_delta_appends_to_buffer() -> None:
    """make_handlers(assembler, width, output_put, last_output_count, header_state, ui_state) returns a dict-like; on_text_delta('x') leaves assembler._buffer == 'x'."""
    assembler = StreamAssembler()
    width = 80
    lines_out: list[str] = []

    def output_put(line: str) -> None:
        lines_out.append(line)

    last_output_count = [0]
    header_state: dict[str, str] = {}
    ui_state: dict[str, str] = {}

    handlers = make_handlers(
        assembler, width, output_put, last_output_count, header_state, ui_state
    )

    assert handlers is not None
    assert "on_text_delta" in handlers
    on_text_delta = handlers["on_text_delta"]
    assert callable(on_text_delta)

    on_text_delta("x")
    assert assembler._buffer == "x"


def test_make_handlers_on_agent_complete_invokes_output_put_and_updates_last_output_count() -> None:
    """Calling returned on_agent_complete() invokes output_put with rendered lines and updates last_output_count[0]."""
    assembler = StreamAssembler()
    assembler.text_delta("Hello")
    width = 80
    lines_out: list[str] = []

    def output_put(line: str) -> None:
        lines_out.append(line)

    last_output_count = [0]
    header_state: dict[str, str] = {}
    ui_state: dict[str, str] = {}

    handlers = make_handlers(
        assembler, width, output_put, last_output_count, header_state, ui_state
    )

    assert "on_agent_complete" in handlers
    on_agent_complete = handlers["on_agent_complete"]
    assert callable(on_agent_complete)

    on_agent_complete()

    assert len(lines_out) >= 1
    assert any("Hello" in line or "assistant" in line for line in lines_out)
    assert last_output_count[0] == 1

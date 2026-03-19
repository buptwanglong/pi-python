"""Tests for native TUI doctor notices and panel."""

import pytest

from basket_tui.native.ui.doctor import (
    collect_doctor_notices,
    format_doctor_panel,
)


def test_collect_doctor_empty_when_no_error():
    assert (
        collect_doctor_notices(ws_url="ws://127.0.0.1:7682/ws", connection_error=None)
        == []
    )
    assert (
        collect_doctor_notices(ws_url="ws://127.0.0.1:7682/ws", connection_error="")
        == []
    )
    assert (
        collect_doctor_notices(ws_url="ws://127.0.0.1:7682/ws", connection_error="   ")
        == []
    )


def test_collect_doctor_non_empty_when_error():
    lines = collect_doctor_notices(
        ws_url="ws://127.0.0.1:7682/ws",
        connection_error="Connection timed out",
    )
    assert len(lines) >= 2
    assert "gateway" in "\n".join(lines).lower()


def test_collect_doctor_redacts_home_path(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("HOME", "/tmp/fakehome")
    err = "/tmp/fakehome/.basket/secret"
    lines = collect_doctor_notices(ws_url="ws://127.0.0.1/ws", connection_error=err)
    blob = "\n".join(lines)
    assert "/tmp/fakehome" not in blob
    assert "~/.basket/secret" in blob


def test_format_doctor_panel_empty():
    assert format_doctor_panel([], width=80) == []


def test_format_doctor_panel_has_box_and_doctor_title():
    lines = format_doctor_panel(["Line one", "Line two"], width=50)
    assert len(lines) >= 3
    assert "┌" in lines[0] and "Doctor" in lines[0]
    assert lines[0].startswith("┌")
    assert lines[-1].startswith("└")
    assert "Line one" in lines[1]

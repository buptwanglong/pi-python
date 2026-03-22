"""Tests for SlashCommandCompleter and SLASH_COMMANDS registry."""

from __future__ import annotations

import pytest
from prompt_toolkit.completion import CompleteEvent
from prompt_toolkit.document import Document

from basket_tui.native.ui.completer import SlashCommandCompleter
from basket_tui.native.ui.input_handler import HELP_LINES, SLASH_COMMANDS


def _completions(text: str, commands: tuple[tuple[str, str], ...] | None = None):
    """Helper: return list of Completion objects for given input text."""
    completer = SlashCommandCompleter(commands or SLASH_COMMANDS)
    doc = Document(text, len(text))
    return list(completer.get_completions(doc, CompleteEvent()))


class TestSlashCommandCompleterFiltering:
    """Verify the completer only triggers on leading '/' and filters correctly."""

    def test_empty_input_no_completions(self) -> None:
        assert _completions("") == []

    def test_plain_text_no_completions(self) -> None:
        assert _completions("hello") == []

    def test_slash_alone_returns_all_commands(self) -> None:
        results = _completions("/")
        assert len(results) == len(SLASH_COMMANDS)

    def test_partial_match(self) -> None:
        results = _completions("/he")
        assert len(results) == 1
        assert results[0].text == "/help"

    def test_exact_match(self) -> None:
        results = _completions("/help")
        assert len(results) == 1
        assert results[0].text == "/help"
        # display_meta may be FormattedText; compare string content
        meta_str = str(results[0].display_meta) if results[0].display_meta else ""
        assert "show this help" in meta_str

    def test_no_match(self) -> None:
        assert _completions("/xyz") == []

    def test_slash_not_first_char_no_completions(self) -> None:
        """If '/' is not at position 0, no completions should appear."""
        assert _completions("text /he") == []

    def test_case_insensitive_matching(self) -> None:
        results = _completions("/HE")
        assert len(results) == 1
        assert results[0].text == "/help"

    def test_case_insensitive_full_upper(self) -> None:
        results = _completions("/HELP")
        assert len(results) == 1
        assert results[0].text == "/help"

    def test_multiple_matches(self) -> None:
        """Commands sharing a prefix all appear."""
        # /session and /settings both start with /s
        results = _completions("/s")
        cmd_texts = [c.text for c in results]
        assert "/session" in cmd_texts
        assert "/settings" in cmd_texts


class TestSlashCommandCompleterPositioning:
    """Verify start_position replaces entire input."""

    @pytest.mark.parametrize(
        "text",
        ["/", "/h", "/hel", "/help"],
    )
    def test_start_position_replaces_full_input(self, text: str) -> None:
        results = _completions(text)
        assert len(results) > 0
        for c in results:
            assert c.start_position == -len(text)


class TestSlashCommandCompleterImmutability:
    """Verify the completer stores an immutable copy of commands."""

    def test_commands_is_tuple(self) -> None:
        completer = SlashCommandCompleter(SLASH_COMMANDS)
        assert isinstance(completer._commands, tuple)

    def test_external_mutation_does_not_affect_completer(self) -> None:
        mutable: list[tuple[str, str]] = [("/foo", "test")]
        completer = SlashCommandCompleter(tuple(mutable))
        mutable.append(("/bar", "another"))
        assert len(completer._commands) == 1


class TestSlashCommandsRegistry:
    """Verify SLASH_COMMANDS is in sync with HELP_LINES."""

    def test_all_commands_present_in_help_lines(self) -> None:
        help_text = "\n".join(HELP_LINES)
        for cmd, desc in SLASH_COMMANDS:
            assert cmd in help_text, f"{cmd} missing from HELP_LINES"
            assert desc in help_text, f"description '{desc}' missing from HELP_LINES"

    def test_help_lines_starts_with_system_header(self) -> None:
        assert HELP_LINES[0] == "[system] Commands:"

    def test_help_lines_ends_with_empty_string(self) -> None:
        assert HELP_LINES[-1] == ""

    def test_slash_commands_count(self) -> None:
        """Sanity: registry length matches known built-ins (includes /quit alias)."""
        assert len(SLASH_COMMANDS) == 11

    def test_slash_commands_all_start_with_slash(self) -> None:
        for cmd, _ in SLASH_COMMANDS:
            assert cmd.startswith("/"), f"{cmd} does not start with /"

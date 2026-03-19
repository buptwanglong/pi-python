"""Tests for scroll_state helpers."""

import pytest

from basket_tui.native.ui.scroll_state import (
    at_bottom,
    clamp_scroll,
    max_scroll,
    scroll_page_down,
    scroll_page_up,
)


def test_max_scroll_zero_when_content_fits() -> None:
    assert max_scroll(5, 10) == 0
    assert max_scroll(10, 10) == 0


def test_max_scroll_when_overflow() -> None:
    assert max_scroll(25, 10) == 15


def test_max_scroll_non_positive_dimensions() -> None:
    assert max_scroll(0, 10) == 0
    assert max_scroll(10, 0) == 0


def test_clamp_scroll() -> None:
    assert clamp_scroll(-5, 100, 10) == 0
    assert clamp_scroll(999, 100, 10) == 90
    assert clamp_scroll(40, 100, 10) == 40


@pytest.mark.parametrize(
    ("scroll", "expected"),
    [
        (90, 80),
        (3, 0),
        (0, 0),
    ],
)
def test_scroll_page_up(scroll: int, expected: int) -> None:
    assert scroll_page_up(scroll, 10, 100, 10) == expected


@pytest.mark.parametrize(
    ("scroll", "expected"),
    [
        (0, 10),
        (85, 90),
        (90, 90),
    ],
)
def test_scroll_page_down(scroll: int, expected: int) -> None:
    assert scroll_page_down(scroll, 10, 100, 10) == expected


def test_at_bottom() -> None:
    assert at_bottom(0, 5, 10) is True
    assert at_bottom(0, 100, 10) is False
    assert at_bottom(90, 100, 10) is True

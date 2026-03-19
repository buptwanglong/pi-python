"""Pure helpers for conversation viewport scrolling (row-based, no wrap)."""


def max_scroll(content_height: int, window_height: int) -> int:
    """Maximum first-visible row index (0 when all content fits)."""
    if window_height <= 0 or content_height <= 0:
        return 0
    return max(0, content_height - window_height)


def clamp_scroll(scroll: int, content_height: int, window_height: int) -> int:
    """Clamp scroll offset to [0, max_scroll]."""
    return max(0, min(scroll, max_scroll(content_height, window_height)))


def scroll_page_up(
    scroll: int, page_size: int, content_height: int, window_height: int
) -> int:
    return clamp_scroll(scroll - page_size, content_height, window_height)


def scroll_page_down(
    scroll: int, page_size: int, content_height: int, window_height: int
) -> int:
    return clamp_scroll(scroll + page_size, content_height, window_height)


def at_bottom(scroll: int, content_height: int, window_height: int) -> bool:
    """True if the viewport shows the last rows (including single-screen content)."""
    return scroll >= max_scroll(content_height, window_height)

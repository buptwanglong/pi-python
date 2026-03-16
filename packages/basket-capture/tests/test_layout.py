"""Tests for layout inferrer: infer_regions from frame lines or CastResult."""

from basket_capture.layout import Region, infer_regions


def test_infer_regions_returns_header_chat_footer_input() -> None:
    """Given a fixed multi-line TUI frame (header, chat, footer, input), infer_regions returns regions with type and line range."""
    # Simulate one TUI frame: header, middle chat, footer, input
    lines = [
        "URL=https://example.com agent=default",
        "User: hello",
        "Assistant: hi there",
        "User: how are you?",
        "idle | model=claude-sonnet",
        "> ",
    ]
    regions = infer_regions(lines)
    assert isinstance(regions, list)
    assert len(regions) >= 1
    for r in regions:
        assert isinstance(r, Region)
        assert hasattr(r, "type")
        assert hasattr(r, "start_line")
        assert hasattr(r, "end_line")
        assert r.start_line >= 0
        assert r.end_line >= r.start_line
    types = {r.type for r in regions}
    assert "header" in types or "Header" in types
    assert "chat" in types or "Chat" in types
    assert "footer" in types or "Footer" in types
    assert "input" in types or "Input" in types

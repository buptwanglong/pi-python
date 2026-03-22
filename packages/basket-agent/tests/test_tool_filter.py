"""
Tests for the dynamic tool selection module (tool_filter).

Covers:
- Core tools always included
- Keyword-based conditional inclusion/exclusion
- Config-based conditional inclusion/exclusion
- Mode-based exclusion
- Unknown tools included by default (conservative)
- Immutability guarantees
- Edge cases (empty messages, empty tools)
"""

import pytest

from basket_ai.types import Context, TextContent, Tool, UserMessage

from basket_agent.tool_filter import (
    ALWAYS_INCLUDE,
    DEFAULT_RULES,
    ToolFilterRule,
    _extract_recent_text,
    _should_include_tool,
    create_filtered_context,
    filter_tools,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_tool(name: str, description: str = "test tool") -> Tool:
    """Create a minimal Tool for testing."""
    return Tool(name=name, description=description, parameters={})


def _make_context(
    messages_text: list[str] | None = None,
    tool_names: list[str] | None = None,
) -> Context:
    """Create a Context with simple user messages and named tools."""
    messages = []
    for text in (messages_text or []):
        messages.append(UserMessage(role="user", content=text, timestamp=0))

    tools = []
    for name in (tool_names or []):
        tools.append(_make_tool(name))

    return Context(messages=messages, tools=tools)


# ---------------------------------------------------------------------------
# Tests: core tools
# ---------------------------------------------------------------------------

class TestCoreToolsAlwaysIncluded:
    """Core tools (read, write, edit, bash, grep) must never be filtered out."""

    def test_core_tools_always_included(self):
        """All ALWAYS_INCLUDE tools survive filtering regardless of context."""
        tool_names = list(ALWAYS_INCLUDE) + ["web_fetch", "web_search"]
        ctx = _make_context(
            messages_text=["hello, how are you?"],  # no keywords
            tool_names=tool_names,
        )

        result = filter_tools(ctx.tools, ctx)
        result_names = {t.name for t in result}

        for core in ALWAYS_INCLUDE:
            assert core in result_names, f"Core tool '{core}' was incorrectly filtered out"

    def test_core_tools_present_in_one_shot_mode(self):
        """Core tools survive even in one_shot mode."""
        ctx = _make_context(
            messages_text=["run this script"],
            tool_names=["read", "write", "bash"],
        )

        result = filter_tools(ctx.tools, ctx, mode="one_shot")
        result_names = {t.name for t in result}

        assert result_names == {"read", "write", "bash"}


# ---------------------------------------------------------------------------
# Tests: web_fetch keyword filtering
# ---------------------------------------------------------------------------

class TestWebFetchFiltering:
    """web_fetch should only appear when URL-related keywords are in recent messages."""

    def test_web_fetch_excluded_without_url(self):
        """web_fetch removed when no URL keyword in messages."""
        ctx = _make_context(
            messages_text=["Write a Python function to sort a list"],
            tool_names=["read", "web_fetch"],
        )

        result = filter_tools(ctx.tools, ctx)
        result_names = {t.name for t in result}

        assert "web_fetch" not in result_names
        assert "read" in result_names

    def test_web_fetch_included_with_url(self):
        """web_fetch included when an https:// URL is in a message."""
        ctx = _make_context(
            messages_text=["Check https://example.com for details"],
            tool_names=["read", "web_fetch"],
        )

        result = filter_tools(ctx.tools, ctx)
        result_names = {t.name for t in result}

        assert "web_fetch" in result_names

    def test_web_fetch_included_with_keyword_fetch(self):
        """web_fetch included when 'fetch' keyword is present."""
        ctx = _make_context(
            messages_text=["fetch the data from the API"],
            tool_names=["web_fetch"],
        )

        result = filter_tools(ctx.tools, ctx)
        assert len(result) == 1
        assert result[0].name == "web_fetch"

    def test_web_fetch_included_with_keyword_link(self):
        """web_fetch included when 'link' keyword is present."""
        ctx = _make_context(
            messages_text=["Here is the link to the docs"],
            tool_names=["web_fetch"],
        )

        result = filter_tools(ctx.tools, ctx)
        assert len(result) == 1


# ---------------------------------------------------------------------------
# Tests: web_search keyword filtering
# ---------------------------------------------------------------------------

class TestWebSearchFiltering:
    """web_search should only appear when search-related keywords are in messages."""

    def test_web_search_excluded_without_keyword(self):
        """web_search removed when no search keyword in messages."""
        ctx = _make_context(
            messages_text=["Refactor the authentication module"],
            tool_names=["bash", "web_search"],
        )

        result = filter_tools(ctx.tools, ctx)
        result_names = {t.name for t in result}

        assert "web_search" not in result_names
        assert "bash" in result_names

    def test_web_search_included_with_search_keyword(self):
        """web_search included when 'search' keyword is present."""
        ctx = _make_context(
            messages_text=["search for the best Python testing framework"],
            tool_names=["web_search"],
        )

        result = filter_tools(ctx.tools, ctx)
        assert len(result) == 1
        assert result[0].name == "web_search"

    def test_web_search_included_with_research_keyword(self):
        """web_search included when 'research' keyword is present."""
        ctx = _make_context(
            messages_text=["I need to research async patterns"],
            tool_names=["web_search"],
        )

        result = filter_tools(ctx.tools, ctx)
        assert len(result) == 1


# ---------------------------------------------------------------------------
# Tests: config-based filtering (task / parallel_task)
# ---------------------------------------------------------------------------

class TestConfigBasedFiltering:
    """task and parallel_task require has_subagents config flag."""

    def test_task_excluded_without_config(self):
        """task tool excluded when has_subagents is not set."""
        ctx = _make_context(
            messages_text=["delegate this work"],
            tool_names=["task", "read"],
        )

        result = filter_tools(ctx.tools, ctx)
        result_names = {t.name for t in result}

        assert "task" not in result_names
        assert "read" in result_names

    def test_task_included_with_config(self):
        """task tool included when has_subagents is True."""
        ctx = _make_context(
            messages_text=["delegate this work"],
            tool_names=["task"],
        )

        result = filter_tools(ctx.tools, ctx, config={"has_subagents": True})
        assert len(result) == 1
        assert result[0].name == "task"

    def test_parallel_task_excluded_without_config(self):
        """parallel_task excluded when has_subagents is not set."""
        ctx = _make_context(
            messages_text=["run in parallel"],
            tool_names=["parallel_task"],
        )

        result = filter_tools(ctx.tools, ctx)
        assert len(result) == 0

    def test_parallel_task_included_with_config(self):
        """parallel_task included when has_subagents is True."""
        ctx = _make_context(
            messages_text=["run in parallel"],
            tool_names=["parallel_task"],
        )

        result = filter_tools(ctx.tools, ctx, config={"has_subagents": True})
        assert len(result) == 1


# ---------------------------------------------------------------------------
# Tests: mode-based filtering (ask_user_question)
# ---------------------------------------------------------------------------

class TestModeBasedFiltering:
    """ask_user_question is excluded in one_shot and subagent modes."""

    def test_ask_user_excluded_in_one_shot_mode(self):
        """ask_user_question excluded in one_shot mode."""
        ctx = _make_context(
            messages_text=["do something"],
            tool_names=["ask_user_question", "read"],
        )

        result = filter_tools(ctx.tools, ctx, mode="one_shot")
        result_names = {t.name for t in result}

        assert "ask_user_question" not in result_names
        assert "read" in result_names

    def test_ask_user_excluded_in_subagent_mode(self):
        """ask_user_question excluded in subagent mode."""
        ctx = _make_context(
            messages_text=["do something"],
            tool_names=["ask_user_question"],
        )

        result = filter_tools(ctx.tools, ctx, mode="subagent")
        assert len(result) == 0

    def test_ask_user_included_in_interactive(self):
        """ask_user_question included in default interactive mode."""
        ctx = _make_context(
            messages_text=["do something"],
            tool_names=["ask_user_question"],
        )

        result = filter_tools(ctx.tools, ctx, mode="interactive")
        assert len(result) == 1
        assert result[0].name == "ask_user_question"


# ---------------------------------------------------------------------------
# Tests: unknown / unregistered tools
# ---------------------------------------------------------------------------

class TestUnknownToolHandling:
    """Tools without a matching rule are included by default (conservative)."""

    def test_unknown_tools_included_by_default(self):
        """A custom tool with no rule is always included."""
        ctx = _make_context(
            messages_text=["hello"],
            tool_names=["my_custom_tool", "another_tool"],
        )

        result = filter_tools(ctx.tools, ctx)
        result_names = {t.name for t in result}

        assert "my_custom_tool" in result_names
        assert "another_tool" in result_names


# ---------------------------------------------------------------------------
# Tests: immutability guarantees
# ---------------------------------------------------------------------------

class TestImmutability:
    """Verify that filtering never mutates the original data."""

    def test_filter_returns_new_list(self):
        """filter_tools returns a new list, not the original."""
        ctx = _make_context(
            messages_text=["hello"],
            tool_names=["read", "write"],
        )
        original_tools = ctx.tools

        result = filter_tools(ctx.tools, ctx)

        assert result is not original_tools
        assert result == original_tools  # same content
        assert len(ctx.tools) == 2  # original unchanged

    def test_create_filtered_context_immutability(self):
        """create_filtered_context returns a new Context; original unchanged."""
        original_tools = [_make_tool("read"), _make_tool("web_fetch")]
        ctx = Context(
            messages=[UserMessage(role="user", content="hello", timestamp=0)],
            tools=original_tools,
        )

        filtered_ctx = create_filtered_context(ctx)

        # Original context is unchanged
        assert len(ctx.tools) == 2
        assert ctx.tools[0].name == "read"
        assert ctx.tools[1].name == "web_fetch"

        # Filtered context has fewer tools (web_fetch removed)
        assert len(filtered_ctx.tools) == 1
        assert filtered_ctx.tools[0].name == "read"

        # Different object
        assert filtered_ctx is not ctx
        assert filtered_ctx.tools is not ctx.tools

    def test_original_tool_list_unmodified_after_removal(self):
        """Verify the input list isn't modified even when tools are removed."""
        tools = [_make_tool("web_fetch"), _make_tool("web_search")]
        ctx = _make_context(messages_text=["no relevant keywords"])
        ctx = ctx.model_copy(update={"tools": tools})

        original_len = len(tools)
        filter_tools(tools, ctx)

        assert len(tools) == original_len


# ---------------------------------------------------------------------------
# Tests: edge cases
# ---------------------------------------------------------------------------

class TestEdgeCases:
    """Edge cases and boundary conditions."""

    def test_empty_messages_doesnt_crash(self):
        """Filtering with no messages should not raise."""
        ctx = _make_context(
            messages_text=[],
            tool_names=["read", "web_fetch", "web_search"],
        )

        result = filter_tools(ctx.tools, ctx)
        result_names = {t.name for t in result}

        # Core tool kept, keyword-dependent tools excluded
        assert "read" in result_names
        assert "web_fetch" not in result_names
        assert "web_search" not in result_names

    def test_empty_tools_returns_empty(self):
        """Filtering an empty tool list returns an empty list."""
        ctx = _make_context(messages_text=["search something"])

        result = filter_tools([], ctx)
        assert result == []

    def test_no_rules_includes_all(self):
        """With empty rules list, all tools are included (no filtering)."""
        ctx = _make_context(
            messages_text=["hello"],
            tool_names=["web_fetch", "web_search", "task"],
        )

        result = filter_tools(ctx.tools, ctx, rules=[])
        assert len(result) == 3

    def test_case_insensitive_keyword_matching(self):
        """Keywords match case-insensitively."""
        ctx = _make_context(
            messages_text=["SEARCH for Python tutorials"],
            tool_names=["web_search"],
        )

        result = filter_tools(ctx.tools, ctx)
        assert len(result) == 1
        assert result[0].name == "web_search"

    def test_lookback_window(self):
        """Only the last N messages are checked for keywords."""
        # Create 10 messages; only the first has the keyword
        messages = ["check this URL https://example.com"] + ["hello world"] * 9
        ctx = _make_context(
            messages_text=messages,
            tool_names=["web_fetch"],
        )

        # Default lookback is 5 — the URL message is in position 0, outside the window
        result = filter_tools(ctx.tools, ctx)
        assert len(result) == 0

    def test_lookback_window_within_range(self):
        """Keyword in recent messages within lookback window triggers inclusion."""
        messages = ["hello world"] * 3 + ["check this URL https://example.com"]
        ctx = _make_context(
            messages_text=messages,
            tool_names=["web_fetch"],
        )

        result = filter_tools(ctx.tools, ctx)
        assert len(result) == 1

    def test_list_content_blocks(self):
        """Messages with list-of-blocks content are handled correctly."""
        msg = UserMessage(
            role="user",
            content=[TextContent(type="text", text="search for Python docs")],
            timestamp=0,
        )
        ctx = Context(
            messages=[msg],
            tools=[_make_tool("web_search")],
        )

        result = filter_tools(ctx.tools, ctx)
        assert len(result) == 1
        assert result[0].name == "web_search"


# ---------------------------------------------------------------------------
# Tests: _extract_recent_text helper
# ---------------------------------------------------------------------------

class TestExtractRecentText:
    """Tests for the internal _extract_recent_text helper."""

    def test_extracts_string_content(self):
        """String message content is extracted correctly."""
        messages = [UserMessage(role="user", content="Hello World", timestamp=0)]
        result = _extract_recent_text(messages)
        assert result == "hello world"

    def test_extracts_list_content(self):
        """List-of-blocks content is extracted correctly."""
        messages = [
            UserMessage(
                role="user",
                content=[TextContent(type="text", text="Search Online")],
                timestamp=0,
            )
        ]
        result = _extract_recent_text(messages)
        assert result == "search online"

    def test_respects_lookback(self):
        """Only the last N messages are included."""
        messages = [
            UserMessage(role="user", content=f"msg-{i}", timestamp=0)
            for i in range(10)
        ]
        result = _extract_recent_text(messages, lookback=3)
        assert "msg-7" in result
        assert "msg-8" in result
        assert "msg-9" in result
        assert "msg-0" not in result

    def test_empty_messages(self):
        """Empty message list returns empty string."""
        result = _extract_recent_text([])
        assert result == ""


# ---------------------------------------------------------------------------
# Tests: _should_include_tool helper
# ---------------------------------------------------------------------------

class TestShouldIncludeTool:
    """Tests for the internal _should_include_tool helper."""

    def test_mode_exclusion(self):
        """Tool is excluded when current mode is in exclude_modes."""
        rule = ToolFilterRule(
            tool_name="test",
            exclude_modes=frozenset({"one_shot"}),
        )
        assert _should_include_tool(rule, "hello", {}, "one_shot") is False

    def test_config_requirement_missing(self):
        """Tool is excluded when required config is missing."""
        rule = ToolFilterRule(
            tool_name="test",
            require_config="needs_flag",
        )
        assert _should_include_tool(rule, "hello", {}, "interactive") is False

    def test_config_requirement_present(self):
        """Tool is included when required config is present and truthy."""
        rule = ToolFilterRule(
            tool_name="test",
            require_config="needs_flag",
        )
        assert _should_include_tool(rule, "hello", {"needs_flag": True}, "interactive") is True

    def test_keyword_match(self):
        """Tool included when keyword is found in text."""
        rule = ToolFilterRule(
            tool_name="test",
            keywords=frozenset({"search"}),
        )
        assert _should_include_tool(rule, "please search for this", {}) is True

    def test_keyword_no_match(self):
        """Tool excluded when no keyword matches."""
        rule = ToolFilterRule(
            tool_name="test",
            keywords=frozenset({"search"}),
        )
        assert _should_include_tool(rule, "hello world", {}) is False

    def test_no_conditions_includes(self):
        """Tool with no keywords, no config, no mode exclusion is included."""
        rule = ToolFilterRule(tool_name="test")
        assert _should_include_tool(rule, "hello", {}) is True


# ---------------------------------------------------------------------------
# Tests: custom rules
# ---------------------------------------------------------------------------

class TestCustomRules:
    """Verify that custom rules can be supplied."""

    def test_custom_rule_applied(self):
        """A custom rule filters as expected."""
        custom_rules = [
            ToolFilterRule(
                tool_name="my_tool",
                keywords=frozenset({"activate"}),
            ),
        ]
        ctx = _make_context(
            messages_text=["please activate the system"],
            tool_names=["my_tool", "other_tool"],
        )

        result = filter_tools(ctx.tools, ctx, rules=custom_rules)
        result_names = {t.name for t in result}

        assert "my_tool" in result_names
        assert "other_tool" in result_names  # not governed by any rule

    def test_custom_rule_excludes(self):
        """A custom rule excludes tool when keyword not present."""
        custom_rules = [
            ToolFilterRule(
                tool_name="my_tool",
                keywords=frozenset({"activate"}),
            ),
        ]
        ctx = _make_context(
            messages_text=["just a normal message"],
            tool_names=["my_tool"],
        )

        result = filter_tools(ctx.tools, ctx, rules=custom_rules)
        assert len(result) == 0


# ---------------------------------------------------------------------------
# Tests: ToolFilterRule immutability
# ---------------------------------------------------------------------------

class TestToolFilterRuleImmutability:
    """ToolFilterRule is frozen and should not be mutatable."""

    def test_rule_is_frozen(self):
        """Attempting to mutate a rule raises an error."""
        rule = ToolFilterRule(tool_name="test", keywords=frozenset({"hello"}))

        with pytest.raises(Exception):  # ValidationError for frozen model
            rule.tool_name = "changed"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

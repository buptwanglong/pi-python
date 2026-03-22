"""
Dynamic tool selection based on conversation context.

Filters irrelevant tools from the LLM context to reduce token overhead
(1,000-3,000 tokens per turn) and improve tool selection accuracy.

Design principles:
- Frozen Pydantic models for rules (immutable)
- Pure functions: filter_tools takes inputs, returns new list
- Immutability: create_filtered_context returns new Context
- Conservative: unknown tools included by default, core tools always included
- No new dependencies
"""

from typing import Dict, FrozenSet, List, Optional, Set

from pydantic import BaseModel, ConfigDict, Field

from basket_ai.types import Context, Message, Tool


# Core tools that should always be available regardless of context
ALWAYS_INCLUDE: FrozenSet[str] = frozenset({
    "read",
    "write",
    "edit",
    "bash",
    "grep",
})


class ToolFilterRule(BaseModel):
    """
    Rule for conditionally including a tool.

    A tool governed by a rule is included when:
    - It is not excluded by the current mode (exclude_modes)
    - Its required config flag is truthy (require_config)
    - At least one keyword is found in recent messages (keywords)

    If keywords is empty the keyword check is skipped (always passes).
    If require_config is None the config check is skipped (always passes).
    """

    tool_name: str
    keywords: FrozenSet[str] = frozenset()
    require_config: Optional[str] = None
    exclude_modes: FrozenSet[str] = frozenset()

    model_config = ConfigDict(frozen=True)


# Default filter rules for tools known to be conditionally useful
DEFAULT_RULES: List[ToolFilterRule] = [
    ToolFilterRule(
        tool_name="web_fetch",
        keywords=frozenset({
            "http://", "https://", "url", "fetch",
            "webpage", "website", "link",
        }),
    ),
    ToolFilterRule(
        tool_name="web_search",
        keywords=frozenset({
            "search", "find online", "google",
            "look up", "research", "web search",
        }),
    ),
    ToolFilterRule(
        tool_name="task",
        require_config="has_subagents",
    ),
    ToolFilterRule(
        tool_name="parallel_task",
        require_config="has_subagents",
    ),
    ToolFilterRule(
        tool_name="ask_user_question",
        exclude_modes=frozenset({"one_shot", "subagent"}),
    ),
]


def _extract_recent_text(messages: List[Message], lookback: int = 5) -> str:
    """
    Extract lowercased text from the last *lookback* messages for keyword matching.

    Handles both plain-string content and list-of-blocks content safely.
    Returns a single space-joined string.
    """
    recent = messages[-lookback:] if len(messages) > lookback else messages
    texts: List[str] = []
    for msg in recent:
        content = getattr(msg, "content", "")
        if isinstance(content, str):
            texts.append(content.lower())
        elif isinstance(content, list):
            for block in content:
                if hasattr(block, "text"):
                    texts.append(block.text.lower())
    return " ".join(texts)


def _should_include_tool(
    rule: ToolFilterRule,
    recent_text: str,
    config: Dict[str, bool],
    mode: str = "interactive",
) -> bool:
    """Determine whether a tool should be included based on its rule."""
    # Check mode exclusion first (cheapest check)
    if mode in rule.exclude_modes:
        return False

    # Check config requirement
    if rule.require_config is not None and not config.get(rule.require_config, False):
        return False

    # Check keyword presence (only when rule has keywords)
    if rule.keywords:
        return any(kw.lower() in recent_text for kw in rule.keywords)

    # No special conditions beyond mode/config → include
    return True


def filter_tools(
    tools: List[Tool],
    context: Context,
    rules: Optional[List[ToolFilterRule]] = None,
    config: Optional[Dict[str, bool]] = None,
    mode: str = "interactive",
) -> List[Tool]:
    """
    Filter tools based on conversation context.

    Args:
        tools: All available tools.
        context: Current conversation context (messages inspected for keywords).
        rules: Filter rules (uses DEFAULT_RULES if None).
        config: Configuration flags (e.g. ``{"has_subagents": True}``).
        mode: Current mode — ``"interactive"``, ``"one_shot"``, or ``"subagent"``.

    Returns:
        A **new** list containing only the relevant tools.
        The original list is never modified.
    """
    active_rules = rules if rules is not None else DEFAULT_RULES
    active_config = config if config is not None else {}

    recent_text = _extract_recent_text(context.messages)

    # Pre-compute which tool names are governed by at least one rule
    rule_tool_names: Set[str] = {r.tool_name for r in active_rules}

    filtered: List[Tool] = []
    for tool in tools:
        # Core tools are unconditionally included
        if tool.name in ALWAYS_INCLUDE:
            filtered.append(tool)
            continue

        # Tools without a rule are included by default (conservative)
        if tool.name not in rule_tool_names:
            filtered.append(tool)
            continue

        # Evaluate matching rules — include if *any* rule passes
        matching_rules = [r for r in active_rules if r.tool_name == tool.name]
        if any(
            _should_include_tool(r, recent_text, active_config, mode)
            for r in matching_rules
        ):
            filtered.append(tool)

    return filtered


def create_filtered_context(
    context: Context,
    rules: Optional[List[ToolFilterRule]] = None,
    config: Optional[Dict[str, bool]] = None,
    mode: str = "interactive",
) -> Context:
    """
    Create a new Context with only relevant tools.

    The original ``context`` is **never** mutated — a shallow copy is returned
    with the ``tools`` list replaced by the filtered result.

    Args:
        context: Original conversation context.
        rules: Filter rules (uses DEFAULT_RULES if None).
        config: Configuration flags.
        mode: Current interaction mode.

    Returns:
        New :class:`Context` instance with filtered tools.
    """
    filtered = filter_tools(context.tools, context, rules, config, mode)
    return context.model_copy(update={"tools": filtered})


__all__ = [
    "ALWAYS_INCLUDE",
    "DEFAULT_RULES",
    "ToolFilterRule",
    "create_filtered_context",
    "filter_tools",
]

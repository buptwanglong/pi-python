"""Tests for declarative tool registry."""

import pytest
from pydantic import BaseModel, Field

from basket_assistant.tools._registry import ToolDefinition, register, get_all, clear


class DummyParams(BaseModel):
    text: str = Field(..., description="Input text")


@pytest.fixture(autouse=True)
def clean_registry():
    """Clear registry before and after each test."""
    clear()
    yield
    clear()


def test_register_and_get_all():
    defn = ToolDefinition(
        name="dummy",
        description="A dummy tool",
        parameters=DummyParams,
        factory=lambda ctx: (lambda **kw: "ok"),
    )
    register(defn)
    all_tools = get_all()
    assert len(all_tools) == 1
    assert all_tools[0].name == "dummy"


def test_get_all_returns_copy():
    """Mutations to returned list should not affect registry."""
    defn = ToolDefinition(
        name="dummy",
        description="A dummy tool",
        parameters=DummyParams,
        factory=lambda ctx: (lambda **kw: "ok"),
    )
    register(defn)
    result = get_all()
    result.clear()
    assert len(get_all()) == 1


def test_plan_mode_blocked_default_false():
    defn = ToolDefinition(
        name="dummy",
        description="A dummy tool",
        parameters=DummyParams,
        factory=lambda ctx: (lambda **kw: "ok"),
    )
    assert defn.plan_mode_blocked is False


def test_plan_mode_blocked_true():
    defn = ToolDefinition(
        name="dummy",
        description="A dummy tool",
        parameters=DummyParams,
        factory=lambda ctx: (lambda **kw: "ok"),
        plan_mode_blocked=True,
    )
    assert defn.plan_mode_blocked is True


def test_description_factory_default_none():
    defn = ToolDefinition(
        name="dummy",
        description="A dummy tool",
        parameters=DummyParams,
        factory=lambda ctx: (lambda **kw: "ok"),
    )
    assert defn.description_factory is None


def test_description_factory_callable():
    defn = ToolDefinition(
        name="dummy",
        description="fallback",
        parameters=DummyParams,
        factory=lambda ctx: (lambda **kw: "ok"),
        description_factory=lambda ctx: "dynamic description",
    )
    assert defn.description_factory is not None
    assert defn.description_factory(None) == "dynamic description"


def test_multiple_registrations():
    for i in range(3):
        register(ToolDefinition(
            name=f"tool_{i}",
            description=f"Tool {i}",
            parameters=DummyParams,
            factory=lambda ctx: (lambda **kw: "ok"),
        ))
    assert len(get_all()) == 3
    assert [t.name for t in get_all()] == ["tool_0", "tool_1", "tool_2"]

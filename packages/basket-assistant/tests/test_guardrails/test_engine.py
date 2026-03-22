"""Tests for the GuardrailEngine."""

import pytest

from basket_assistant.guardrails.engine import GuardrailEngine
from basket_assistant.guardrails.rules import GuardrailResult
from basket_assistant.guardrails.defaults import create_default_engine


# ---------------------------------------------------------------------------
# Engine evaluate()
# ---------------------------------------------------------------------------


class TestGuardrailEngine:
    """Tests for the evaluation engine."""

    def test_engine_all_pass(self):
        """Engine returns allowed when no checks block."""
        engine = GuardrailEngine()
        result = engine.evaluate("bash", {"command": "echo hello"})
        assert result.allowed

    def test_engine_first_block_wins(self):
        """First blocking check determines the result."""

        def always_block(tool_name, arguments):
            return GuardrailResult(
                allowed=False,
                rule_id="first",
                message="First blocker",
            )

        def also_block(tool_name, arguments):
            return GuardrailResult(
                allowed=False,
                rule_id="second",
                message="Second blocker",
            )

        engine = GuardrailEngine(checks=[always_block, also_block])
        result = engine.evaluate("bash", {"command": "anything"})
        assert not result.allowed
        assert result.rule_id == "first"

    def test_engine_disabled(self):
        """Disabled engine always allows."""

        def always_block(tool_name, arguments):
            return GuardrailResult(allowed=False, rule_id="x", message="no")

        engine = GuardrailEngine(checks=[always_block], enabled=False)
        result = engine.evaluate("bash", {"command": "rm -rf /"})
        assert result.allowed

    def test_engine_enable_toggle(self):
        """Engine can be enabled/disabled at runtime."""

        def always_block(tool_name, arguments):
            return GuardrailResult(allowed=False, rule_id="x", message="no")

        engine = GuardrailEngine(checks=[always_block], enabled=True)
        assert not engine.evaluate("bash", {"command": "test"}).allowed

        engine.enabled = False
        assert engine.evaluate("bash", {"command": "test"}).allowed

        engine.enabled = True
        assert not engine.evaluate("bash", {"command": "test"}).allowed

    def test_engine_default_checks_block_dangerous(self):
        """Default engine blocks dangerous commands without explicit check list."""
        engine = GuardrailEngine()
        result = engine.evaluate("bash", {"command": "rm -rf /"})
        assert not result.allowed

    def test_engine_default_checks_block_secrets(self):
        """Default engine blocks secret exposure."""
        engine = GuardrailEngine()
        result = engine.evaluate("bash", {"command": "printenv"})
        assert not result.allowed

    def test_engine_with_workspace_dir(self, tmp_path):
        """Engine with workspace_dir blocks writes outside it."""
        workspace = str(tmp_path / "ws")
        engine = GuardrailEngine(workspace_dir=workspace)
        result = engine.evaluate(
            "write", {"file_path": "/etc/passwd", "content": "bad"}
        )
        assert not result.allowed
        assert result.rule_id == "path_outside_workspace"

    def test_engine_with_workspace_allows_inside(self, tmp_path):
        """Engine with workspace_dir allows writes inside it."""
        workspace = tmp_path / "ws"
        workspace.mkdir()
        engine = GuardrailEngine(workspace_dir=str(workspace))
        result = engine.evaluate(
            "write", {"file_path": str(workspace / "ok.txt"), "content": "fine"}
        )
        assert result.allowed

    def test_engine_without_workspace_allows_writes(self):
        """Engine without workspace_dir allows writes anywhere."""
        engine = GuardrailEngine()
        result = engine.evaluate(
            "write", {"file_path": "/etc/passwd", "content": "data"}
        )
        assert result.allowed

    def test_engine_custom_checks_only(self):
        """Custom checks replace defaults entirely."""
        call_log = []

        def custom_check(tool_name, arguments):
            call_log.append(tool_name)
            return GuardrailResult(allowed=True)

        engine = GuardrailEngine(checks=[custom_check])
        result = engine.evaluate("bash", {"command": "rm -rf /"})
        # Custom check allows even dangerous commands (defaults not loaded)
        assert result.allowed
        assert call_log == ["bash"]

    def test_engine_checks_property_returns_copy(self):
        """Checks property returns a copy, not internal list."""
        engine = GuardrailEngine()
        checks = engine.checks
        original_len = len(checks)
        checks.append(lambda tn, args: GuardrailResult(allowed=True))
        assert len(engine.checks) == original_len

    def test_engine_workspace_dir_property(self, tmp_path):
        """Workspace dir is accessible via property."""
        ws = str(tmp_path / "ws")
        engine = GuardrailEngine(workspace_dir=ws)
        assert engine.workspace_dir == ws

    def test_engine_workspace_dir_none_by_default(self):
        engine = GuardrailEngine()
        assert engine.workspace_dir is None


# ---------------------------------------------------------------------------
# create_default_engine
# ---------------------------------------------------------------------------


class TestCreateDefaultEngine:
    """Tests for the convenience factory function."""

    def test_default_engine_blocks_dangerous(self):
        engine = create_default_engine()
        result = engine.evaluate("bash", {"command": "rm -rf /"})
        assert not result.allowed

    def test_default_engine_with_workspace(self, tmp_path):
        ws = str(tmp_path / "ws")
        engine = create_default_engine(workspace_dir=ws)
        result = engine.evaluate(
            "write", {"file_path": "/etc/passwd", "content": "x"}
        )
        assert not result.allowed

    def test_default_engine_disabled(self):
        engine = create_default_engine(enabled=False)
        result = engine.evaluate("bash", {"command": "rm -rf /"})
        assert result.allowed

    def test_default_engine_allows_safe_commands(self):
        engine = create_default_engine()
        result = engine.evaluate("bash", {"command": "ls -la"})
        assert result.allowed


# ---------------------------------------------------------------------------
# Guardrail wrapping integration
# ---------------------------------------------------------------------------


class TestGuardrailWrapping:
    """Tests for the _wrap_execute_fn_for_guardrails function."""

    @pytest.mark.asyncio
    async def test_wrap_blocks_dangerous_command(self):
        from basket_assistant.agent.tools import _wrap_execute_fn_for_guardrails

        async def mock_execute(**kwargs):
            return "executed"

        engine = GuardrailEngine()
        wrapped = _wrap_execute_fn_for_guardrails(mock_execute, engine, "bash")
        result = await wrapped(command="rm -rf /")
        assert "Guardrail blocked" in result

    @pytest.mark.asyncio
    async def test_wrap_allows_safe_command(self):
        from basket_assistant.agent.tools import _wrap_execute_fn_for_guardrails

        async def mock_execute(**kwargs):
            return "executed"

        engine = GuardrailEngine()
        wrapped = _wrap_execute_fn_for_guardrails(mock_execute, engine, "bash")
        result = await wrapped(command="echo hello")
        assert result == "executed"

    @pytest.mark.asyncio
    async def test_wrap_calls_original_fn_with_kwargs(self):
        from basket_assistant.agent.tools import _wrap_execute_fn_for_guardrails

        received_kwargs = {}

        async def mock_execute(**kwargs):
            received_kwargs.update(kwargs)
            return "done"

        engine = GuardrailEngine()
        wrapped = _wrap_execute_fn_for_guardrails(mock_execute, engine, "read")
        await wrapped(file_path="/tmp/test.txt")
        assert received_kwargs == {"file_path": "/tmp/test.txt"}

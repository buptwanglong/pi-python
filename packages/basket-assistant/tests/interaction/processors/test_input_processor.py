"""Tests for InputProcessor - priority-based input routing."""

import pytest

from basket_assistant.interaction.commands.registry import CommandRegistry
from basket_assistant.interaction.processors.input_processor import InputProcessor, ProcessResult


class MockAgent:
    """Mock agent for testing."""

    def __init__(self):
        self._pending_asks = []

    async def try_resume_pending_ask(self, user_input, tool_call_id=None):
        """Mock try_resume_pending_ask."""
        if not self._pending_asks:
            return False, None
        # Simulate successful resume
        return True, "Pending ask resumed"


@pytest.fixture
def mock_agent():
    """Create a mock agent."""
    return MockAgent()


@pytest.fixture
def command_registry(mock_agent):
    """Create a command registry with test commands."""
    registry = CommandRegistry()

    # Register test commands
    def plan_handler(args: str) -> str:
        return f"Planning: {args}"

    async def async_handler(args: str) -> str:
        return f"Async: {args}"

    registry.register("plan", plan_handler, "Plan command")
    registry.register_async("async_cmd", async_handler, "Async command")

    return registry


@pytest.fixture
def input_processor(mock_agent, command_registry):
    """Create an input processor."""
    return InputProcessor(mock_agent, command_registry)


class TestInputProcessor:
    """Test InputProcessor priority-based routing."""

    @pytest.mark.asyncio
    async def test_pending_ask_highest_priority(self, input_processor, mock_agent):
        """Test that pending ask has highest priority."""
        # Set up pending ask
        mock_agent._pending_asks = [{"tool_call_id": "test-id", "question": "What?"}]

        result = await input_processor.process("any input")

        assert result.action == "handled"
        assert result.message is None  # Handled by agent internally

    @pytest.mark.asyncio
    async def test_no_pending_ask_returns_false(self, input_processor):
        """Test that no pending ask returns False for resume."""
        result = await input_processor.process("normal input")

        # Should not be handled by pending ask
        assert result.action == "send_to_agent"

    @pytest.mark.asyncio
    async def test_command_second_priority(self, input_processor):
        """Test that commands have second priority."""
        result = await input_processor.process("/plan something")

        assert result.action == "handled"
        assert result.message is None  # Commands handle output themselves

    @pytest.mark.asyncio
    async def test_async_command_execution(self, input_processor):
        """Test that async commands work correctly."""
        result = await input_processor.process("/async_cmd test")

        assert result.action == "handled"

    @pytest.mark.asyncio
    async def test_skill_invocation_third_priority(self, input_processor, mock_agent):
        """Test that skill invocation has third priority."""
        result = await input_processor.process("/skill test-skill optional message")

        assert result.action == "handled"
        assert result.invoked_skill_id == "test-skill"
        assert result.message is not None
        # Message should include skill name + optional text
        assert "test-skill" in str(result.message)

    @pytest.mark.asyncio
    async def test_skill_without_message(self, input_processor):
        """Test skill invocation without optional message."""
        result = await input_processor.process("/skill my-skill")

        assert result.action == "handled"
        assert result.invoked_skill_id == "my-skill"

    @pytest.mark.asyncio
    async def test_invalid_skill_format(self, input_processor):
        """Test that invalid skill format returns error."""
        result = await input_processor.process("/skill")

        assert result.action == "handled"
        assert result.error is not None
        assert "Usage: /skill <skill-id>" in result.error

    @pytest.mark.asyncio
    async def test_normal_input_lowest_priority(self, input_processor):
        """Test that normal input has lowest priority."""
        result = await input_processor.process("Hello, how are you?")

        assert result.action == "send_to_agent"
        assert result.message is not None
        assert result.message.content == "Hello, how are you?"

    @pytest.mark.asyncio
    async def test_priority_order_pending_ask_over_command(
        self, input_processor, mock_agent
    ):
        """Test that pending ask takes priority over commands."""
        mock_agent._pending_asks = [{"tool_call_id": "test-id", "question": "What?"}]

        # Even if input looks like command, pending ask wins
        result = await input_processor.process("/plan something")

        assert result.action == "handled"
        # Should be handled by pending ask, not command

    @pytest.mark.asyncio
    async def test_priority_order_command_over_skill(self, input_processor):
        """Test that registered commands take priority over skill syntax."""
        # Register a command called "skill"
        def skill_cmd_handler(args: str) -> str:
            return "Command handled"

        input_processor.command_registry.register(
            "skill", skill_cmd_handler, "Skill command"
        )

        result = await input_processor.process("/skill test")

        # Should be handled by command, not skill invocation
        assert result.action == "handled"
        assert result.invoked_skill_id is None

    @pytest.mark.asyncio
    async def test_unknown_command_returns_error(self, input_processor):
        """Test that unknown commands return error."""
        result = await input_processor.process("/unknown_cmd")

        assert result.action == "handled"
        assert result.error is not None
        assert "Unknown command" in result.error

    @pytest.mark.asyncio
    async def test_empty_input(self, input_processor):
        """Test that empty input is sent to agent."""
        result = await input_processor.process("")

        assert result.action == "send_to_agent"
        assert result.message is not None
        assert result.message.content == ""

    @pytest.mark.asyncio
    async def test_whitespace_only_input(self, input_processor):
        """Test that whitespace-only input is sent to agent."""
        result = await input_processor.process("   ")

        assert result.action == "send_to_agent"
        assert result.message is not None


class TestClearCompactRouting:
    """Test /clear and /compact are routed correctly as handled commands."""

    @pytest.fixture
    def full_registry(self):
        """Create a command registry with all builtins registered."""
        from basket_assistant.interaction.commands.handlers import BuiltinCommandHandlers

        class FullMockContext:
            def __init__(self):
                self.messages = []
                self.system_prompt = ""
                self.tools = []

            def model_copy(self, update=None):
                new = FullMockContext()
                new.messages = list(self.messages)
                new.system_prompt = self.system_prompt
                new.tools = list(self.tools)
                if update:
                    for k, v in update.items():
                        setattr(new, k, v)
                return new

        class FullMockModel:
            provider = "openai"
            model_id = "test"
            context_window = 128000

        class FullMockSettings:
            def __init__(self):
                self.model = FullMockModel()
                self.agent = type("A", (), {"max_turns": 10, "auto_save": True})()
                self.workspace_dir = "/tmp"

            def to_dict(self):
                return {"model": {"provider": "openai"}, "agent": {"max_turns": 10}}

        class FullMockSessionManager:
            async def create_session(self, model_id=""):
                return "new-session"

            async def list_sessions(self):
                return []

            async def load_session(self, sid):
                return []

        class FullMockAgent:
            def __init__(self):
                self.settings = FullMockSettings()
                self.session_manager = FullMockSessionManager()
                self.context = FullMockContext()
                self.model = FullMockModel()
                self._todo_show_full = False
                self.plan_mode = False
                self._current_todos = []
                self._pending_asks = []
                self._session_id = None
                self.conversation = []

            def load_history(self, msgs):
                self.conversation = msgs

            async def try_resume_pending_ask(self, user_input, tool_call_id=None):
                return False, None

        agent = FullMockAgent()
        registry = CommandRegistry(agent)
        processor = InputProcessor(agent, registry)
        return processor

    @pytest.mark.asyncio
    async def test_clear_command_is_handled(self, full_registry):
        """Test /clear is routed as a handled command."""
        result = await full_registry.process("/clear")
        assert result.action == "handled"
        assert result.error is None or result.error == ""

    @pytest.mark.asyncio
    async def test_compact_command_is_handled(self, full_registry):
        """Test /compact is routed as a handled command."""
        result = await full_registry.process("/compact")
        assert result.action == "handled"
        assert result.error is None or result.error == ""


class TestProcessResult:
    """Test ProcessResult dataclass."""

    def test_process_result_defaults(self):
        """Test ProcessResult default values."""
        result = ProcessResult(action="handled")

        assert result.action == "handled"
        assert result.message is None
        assert result.invoked_skill_id is None
        assert result.error is None

    def test_process_result_with_message(self):
        """Test ProcessResult with message."""
        from basket_ai.types import UserMessage
        import time

        msg = UserMessage(role="user", content="test", timestamp=int(time.time() * 1000))
        result = ProcessResult(action="send_to_agent", message=msg)

        assert result.action == "send_to_agent"
        assert result.message == msg

    def test_process_result_with_skill(self):
        """Test ProcessResult with skill invocation."""
        result = ProcessResult(action="handled", invoked_skill_id="test-skill")

        assert result.action == "handled"
        assert result.invoked_skill_id == "test-skill"

    def test_process_result_with_error(self):
        """Test ProcessResult with error."""
        result = ProcessResult(action="handled", error="Something went wrong")

        assert result.action == "handled"
        assert result.error == "Something went wrong"

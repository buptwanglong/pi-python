"""Tests for CommandRegistry."""

import pytest
from basket_assistant.commands.registry import Command, CommandRegistry


@pytest.fixture
def registry():
    """Create a fresh CommandRegistry for each test."""
    return CommandRegistry()


def test_register_sync_command(registry):
    """Test registering a synchronous command."""
    def my_command(arg: str) -> str:
        return f"Result: {arg}"

    registry.register(
        name="test",
        handler=my_command,
        description="Test command"
    )

    assert registry.has_command("/test")
    commands = registry.list_commands()
    assert len(commands) == 1
    assert commands[0].name == "test"
    assert commands[0].description == "Test command"
    assert not commands[0].is_async


def test_register_async_command(registry):
    """Test registering an asynchronous command."""
    async def my_async_command(arg: str) -> str:
        return f"Async result: {arg}"

    registry.register_async(
        name="async_test",
        handler=my_async_command,
        description="Async test command"
    )

    assert registry.has_command("/async_test")
    commands = registry.list_commands()
    assert len(commands) == 1
    assert commands[0].name == "async_test"
    assert commands[0].is_async


def test_has_command(registry):
    """Test checking if text is a command."""
    def dummy_handler():
        pass

    registry.register("test", dummy_handler, "Test")

    # Should match command
    assert registry.has_command("/test")
    assert registry.has_command("/test arg1 arg2")

    # Should not match
    assert not registry.has_command("not a command")
    assert not registry.has_command("/ test")  # Space after slash
    assert not registry.has_command("/unknown")


@pytest.mark.asyncio
async def test_execute_sync_command(registry):
    """Test executing a synchronous command."""
    def echo_command(text: str) -> str:
        return f"Echo: {text}"

    registry.register("echo", echo_command, "Echo command")

    success, result = await registry.execute("/echo hello world")
    assert success is True
    assert result == "Echo: hello world"


@pytest.mark.asyncio
async def test_execute_async_command(registry):
    """Test executing an asynchronous command."""
    async def async_echo(text: str) -> str:
        return f"Async echo: {text}"

    registry.register_async("aecho", async_echo, "Async echo")

    success, result = await registry.execute("/aecho hello")
    assert success is True
    assert result == "Async echo: hello"


@pytest.mark.asyncio
async def test_execute_unknown_command(registry):
    """Test executing an unknown command."""
    success, result = await registry.execute("/unknown arg1 arg2")
    assert success is False
    assert "Unknown command" in result


@pytest.mark.asyncio
async def test_execute_command_with_exception(registry):
    """Test handling exceptions during command execution."""
    def failing_command(arg: str) -> str:
        raise ValueError("Something went wrong")

    registry.register("fail", failing_command, "Failing command")

    success, result = await registry.execute("/fail test")
    assert success is False
    assert "Something went wrong" in result


def test_list_commands(registry):
    """Test listing all registered commands."""
    def cmd1():
        pass

    def cmd2():
        pass

    async def cmd3():
        pass

    registry.register("cmd1", cmd1, "First command")
    registry.register("cmd2", cmd2, "Second command")
    registry.register_async("cmd3", cmd3, "Third command")

    commands = registry.list_commands()
    assert len(commands) == 3

    names = [cmd.name for cmd in commands]
    assert "cmd1" in names
    assert "cmd2" in names
    assert "cmd3" in names


@pytest.mark.asyncio
async def test_command_with_aliases(registry):
    """Test commands with aliases."""
    def toggle_command(arg: str = "") -> str:
        return f"Toggle: {arg}"

    registry.register(
        name="toggle",
        handler=toggle_command,
        description="Toggle something",
        aliases=["t", "tog"]
    )

    # All aliases should work
    assert registry.has_command("/toggle")
    assert registry.has_command("/t")
    assert registry.has_command("/tog")

    # Execute via alias
    success, result = await registry.execute("/t on")
    assert success is True
    assert result == "Toggle: on"


@pytest.mark.asyncio
async def test_command_case_insensitive(registry):
    """Test that commands are case-insensitive."""
    def test_cmd():
        return "OK"

    registry.register("test", test_cmd, "Test")

    assert registry.has_command("/TEST")
    assert registry.has_command("/Test")
    assert registry.has_command("/test")

    success, result = await registry.execute("/TEST")
    assert success is True


@pytest.mark.asyncio
async def test_mixed_sync_async_execution(registry):
    """Test executing both sync and async commands in the same registry."""
    def sync_cmd() -> str:
        return "sync"

    async def async_cmd() -> str:
        return "async"

    registry.register("sync", sync_cmd, "Sync")
    registry.register_async("async", async_cmd, "Async")

    # Execute sync command
    success, result = await registry.execute("/sync")
    assert success is True
    assert result == "sync"

    # Execute async command
    success, result = await registry.execute("/async")
    assert success is True
    assert result == "async"


@pytest.mark.asyncio
async def test_execute_async_returns_bool_str_tuple(registry):
    """Handlers may return (success, message); execute unwraps them."""

    async def dual(arg: str) -> tuple[bool, str]:
        return False, "nope"

    registry.register_async("dual", dual, "dual")
    ok, msg = await registry.execute("/dual x")
    assert ok is False
    assert msg == "nope"


@pytest.mark.asyncio
async def test_execute_without_args(registry):
    """Test executing command without arguments."""
    def no_args_command() -> str:
        return "No args"

    registry.register("noargs", no_args_command, "No args")

    success, result = await registry.execute("/noargs")
    assert success is True
    assert result == "No args"


def test_command_dataclass():
    """Test Command dataclass."""
    def handler():
        pass

    cmd = Command(
        name="test",
        handler=handler,
        description="Test command",
        is_async=False,
        aliases=["t", "tst"]
    )

    assert cmd.name == "test"
    assert cmd.handler == handler
    assert cmd.description == "Test command"
    assert cmd.is_async is False
    assert cmd.aliases == ["t", "tst"]

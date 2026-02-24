"""
Tests for the extension system.
"""

import pytest
from pathlib import Path
from pydantic import BaseModel, Field
from unittest.mock import Mock, AsyncMock, patch

from basket_assistant.extensions import ExtensionAPI, ExtensionLoader


class MockCodingAgent:
    """Mock CodingAgent for testing."""

    def __init__(self):
        self.agent = Mock()
        self.agent.register_tool = Mock()
        self.agent.on = Mock()
        self.agent.context = Mock()
        self.settings = Mock()
        self.session_manager = Mock()


def test_extension_api_init():
    """Test ExtensionAPI initialization."""
    agent = MockCodingAgent()
    api = ExtensionAPI(agent)

    assert api._agent == agent
    assert api._commands == {}
    assert api._event_handlers == {}


def test_extension_api_register_tool():
    """Test tool registration via decorator."""
    agent = MockCodingAgent()
    api = ExtensionAPI(agent)

    class TestParams(BaseModel):
        name: str = Field(..., description="Name parameter")

    @api.register_tool(
        name="test_tool",
        description="A test tool",
        parameters=TestParams,
    )
    async def test_tool(name: str) -> str:
        return f"Hello, {name}!"

    # Verify tool was registered with agent
    agent.agent.register_tool.assert_called_once()
    call_args = agent.agent.register_tool.call_args
    assert call_args.kwargs["name"] == "test_tool"
    assert call_args.kwargs["description"] == "A test tool"
    assert call_args.kwargs["parameters"] == TestParams


def test_extension_api_register_command():
    """Test command registration via decorator."""
    agent = MockCodingAgent()
    api = ExtensionAPI(agent)

    @api.register_command("/test")
    def test_command(args: str):
        return f"Command: {args}"

    # Verify command was stored
    assert "/test" in api._commands
    assert api._commands["/test"](["arg1", "arg2"]) == "Command: ['arg1', 'arg2']"


def test_extension_api_register_event():
    """Test event handler registration via decorator."""
    agent = MockCodingAgent()
    api = ExtensionAPI(agent)

    @api.on("test_event")
    async def test_handler(event, ctx=None):
        return f"Event: {event}"

    # Verify event handler was stored
    assert "test_event" in api._event_handlers
    assert test_handler in api._event_handlers["test_event"]

    # Verify event handler was registered with agent
    agent.agent.on.assert_called_once_with("test_event", test_handler)


def test_extension_api_get_context():
    """Test getting agent context."""
    agent = MockCodingAgent()
    agent.agent.context = {"test": "context"}
    api = ExtensionAPI(agent)

    context = api.get_context()
    assert context == {"test": "context"}


def test_extension_api_get_settings():
    """Test getting agent settings."""
    agent = MockCodingAgent()
    agent.settings = {"test": "settings"}
    api = ExtensionAPI(agent)

    settings = api.get_settings()
    assert settings == {"test": "settings"}


def test_extension_api_get_session_manager():
    """Test getting session manager."""
    agent = MockCodingAgent()
    agent.session_manager = Mock()
    api = ExtensionAPI(agent)

    session_manager = api.get_session_manager()
    assert session_manager == agent.session_manager


def test_extension_api_execute_command():
    """Test executing registered commands."""
    agent = MockCodingAgent()
    api = ExtensionAPI(agent)

    # Register a command
    executed = []

    @api.register_command("/test")
    def test_command(args: str):
        executed.append(args)

    # Execute the command
    result = api.execute_command("/test", "arg1 arg2")
    assert result is True
    assert executed == ["arg1 arg2"]

    # Try non-existent command
    result = api.execute_command("/nonexistent", "args")
    assert result is False


def test_extension_api_get_commands():
    """Test getting list of registered commands."""
    agent = MockCodingAgent()
    api = ExtensionAPI(agent)

    @api.register_command("/cmd1")
    def cmd1(args):
        pass

    @api.register_command("/cmd2")
    def cmd2(args):
        pass

    commands = api.get_commands()
    assert set(commands) == {"/cmd1", "/cmd2"}


def test_extension_loader_init():
    """Test ExtensionLoader initialization."""
    agent = MockCodingAgent()
    loader = ExtensionLoader(agent)

    assert loader._agent == agent
    assert isinstance(loader._api, ExtensionAPI)
    assert loader._loaded_extensions == {}


def test_extension_loader_get_api():
    """Test getting the ExtensionAPI."""
    agent = MockCodingAgent()
    loader = ExtensionLoader(agent)

    api = loader.get_api()
    assert isinstance(api, ExtensionAPI)


def test_extension_loader_get_loaded_extensions():
    """Test getting loaded extension list."""
    agent = MockCodingAgent()
    loader = ExtensionLoader(agent)

    # Initially empty
    assert loader.get_loaded_extensions() == []

    # Add some extensions
    loader._loaded_extensions["/path/to/ext1.py"] = Mock()
    loader._loaded_extensions["/path/to/ext2.py"] = Mock()

    loaded = loader.get_loaded_extensions()
    assert len(loaded) == 2
    assert "/path/to/ext1.py" in loaded
    assert "/path/to/ext2.py" in loaded


def test_extension_loader_load_extension_success(tmp_path, capsys):
    """Test successful extension loading."""
    agent = MockCodingAgent()
    loader = ExtensionLoader(agent)

    # Create a test extension file
    ext_file = tmp_path / "test_ext.py"
    ext_file.write_text("""
def setup(basket):
    @basket.register_command("/hello")
    def hello_cmd(args):
        print(f"Hello, {args}!")
""")

    # Load the extension
    result = loader.load_extension(ext_file)

    # Verify success
    assert result is True
    assert str(ext_file) in loader._loaded_extensions

    # Check output
    captured = capsys.readouterr()
    assert "✅ Loaded extension: test_ext" in captured.out


def test_extension_loader_load_extension_missing_setup(tmp_path, capsys):
    """Test loading extension without setup() function."""
    agent = MockCodingAgent()
    loader = ExtensionLoader(agent)

    # Create an extension without setup()
    ext_file = tmp_path / "bad_ext.py"
    ext_file.write_text("""
def not_setup(basket):
    pass
""")

    # Load the extension
    result = loader.load_extension(ext_file)

    # Verify failure
    assert result is False
    assert str(ext_file) not in loader._loaded_extensions

    # Check error output
    captured = capsys.readouterr()
    assert "❌ Extension missing setup() function" in captured.out


def test_extension_loader_load_extension_error(tmp_path, capsys):
    """Test loading extension with syntax error."""
    agent = MockCodingAgent()
    loader = ExtensionLoader(agent)

    # Create an extension with error
    ext_file = tmp_path / "error_ext.py"
    ext_file.write_text("""
def setup(basket):
    raise ValueError("Test error")
""")

    # Load the extension
    result = loader.load_extension(ext_file)

    # Verify failure
    assert result is False
    assert str(ext_file) not in loader._loaded_extensions

    # Check error output
    captured = capsys.readouterr()
    assert "❌ Error loading extension" in captured.out
    assert "Test error" in captured.out


def test_extension_loader_load_extensions_from_dir(tmp_path, capsys):
    """Test loading all extensions from a directory."""
    agent = MockCodingAgent()
    loader = ExtensionLoader(agent)

    # Create test extensions
    ext1 = tmp_path / "ext1.py"
    ext1.write_text("def setup(basket): pass")

    ext2 = tmp_path / "ext2.py"
    ext2.write_text("def setup(basket): pass")

    # Create a file to skip
    (tmp_path / "__init__.py").write_text("")
    (tmp_path / "_private.py").write_text("")

    # Load from directory
    count = loader.load_extensions_from_dir(tmp_path)

    # Verify only ext1 and ext2 loaded (skipped __init__ and _private)
    assert count == 2
    assert len(loader.get_loaded_extensions()) == 2


def test_extension_loader_load_extensions_from_nonexistent_dir(tmp_path):
    """Test loading from non-existent directory."""
    agent = MockCodingAgent()
    loader = ExtensionLoader(agent)

    # Try to load from non-existent directory
    count = loader.load_extensions_from_dir(tmp_path / "nonexistent")

    # Should return 0 without error
    assert count == 0


def test_extension_loader_load_default_extensions(tmp_path, monkeypatch, capsys):
    """Test loading from default locations."""
    agent = MockCodingAgent()
    loader = ExtensionLoader(agent)

    # Mock home and cwd
    user_ext_dir = tmp_path / ".basket" / "extensions"
    user_ext_dir.mkdir(parents=True)

    local_ext_dir = tmp_path / "extensions"
    local_ext_dir.mkdir(parents=True)

    # Create test extensions
    (user_ext_dir / "user_ext.py").write_text("def setup(basket): pass")
    (local_ext_dir / "local_ext.py").write_text("def setup(basket): pass")

    # Mock paths
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    monkeypatch.setattr(Path, "cwd", lambda: tmp_path)

    # Load default extensions
    count = loader.load_default_extensions()

    # Verify both loaded
    assert count == 2
    captured = capsys.readouterr()
    assert "✅ Loaded extension: user_ext" in captured.out
    assert "✅ Loaded extension: local_ext" in captured.out

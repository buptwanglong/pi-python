# Example Extensions for Pi Coding Agent

This directory contains example extensions that demonstrate how to extend the Pi Coding Agent with custom tools, commands, and event handlers.

## Available Examples

### 1. Hello World (`hello_extension.py`)
Basic extension demonstrating all core features:
- Custom tool registration (`hello`)
- Slash command (`/greet`)
- Event handler (logs tool calls)

**Usage:**
```python
# Copy to ~/.pi/extensions/ or ./extensions/
# The agent will auto-load it on startup

# Using the tool (agent can call this)
"Say hello to Alice enthusiastically"

# Using the command
/greet Alice
```

### 2. Code Formatter (`formatter_extension.py`)
Adds code formatting capabilities:
- Tool: `format` - Format files with black/prettier/rustfmt
- Command: `/format <file> [formatter]`

**Requirements:**
```bash
pip install black
npm install -g prettier
cargo install rustfmt
```

**Usage:**
```python
# Via tool
"Format the main.py file"

# Via command
/format src/main.py black
```

### 3. Git Helper (`git_helper_extension.py`)
Convenient git operations:
- Tools: `git_commit`, `git_branch`
- Commands: `/git-status`, `/git-log`
- Event handler: Logs git operations

**Usage:**
```python
# Create a commit
"Commit all changes with message 'Fix bug in auth'"

# Switch branches
"Switch to feature/new-ui branch"

# Check status
/git-status

# View recent commits
/git-log 10
```

### 4. Project Context (`project_context_extension.py`)
Manage project-specific knowledge:
- Tools: `context_add`, `context_get`
- Commands: `/context`, `/context-clear`
- Storage: `.pi/project_context.json`

**Usage:**
```python
# Add context
"Add context: architecture = microservices with event sourcing"

# Retrieve context
"Get context for architecture"

# View all context
/context

# Clear context
/context-clear
```

## Creating Your Own Extension

### Basic Structure

```python
"""
Your Extension Name

Brief description of what it does.
"""

from pydantic import BaseModel, Field

class YourToolParams(BaseModel):
    """Parameters for your tool."""
    param1: str = Field(..., description="Description")

def setup(pi):
    """
    Extension setup function.

    Args:
        pi: ExtensionAPI instance
    """

    # Register a tool
    @pi.register_tool(
        name="your_tool",
        description="What your tool does",
        parameters=YourToolParams,
    )
    async def your_tool(param1: str) -> str:
        """Your tool implementation."""
        return f"Result: {param1}"

    # Register a command
    @pi.register_command("/your-cmd")
    def your_command(args: str):
        """Your command implementation."""
        print(f"Command called with: {args}")

    # Register an event handler
    @pi.on("agent_tool_call_start")
    async def on_tool_call(event, ctx=None):
        """Handle tool call events."""
        print(f"Tool: {event.get('tool_name')}")

    print("✅ Your extension loaded!")
```

### Extension API

**Available decorators:**
- `@pi.register_tool(name, description, parameters)` - Register a tool
- `@pi.register_command(command)` - Register a slash command
- `@pi.on(event_name)` - Register an event handler

**Available events:**
- `agent_tool_call_start` - Tool execution started
- `agent_tool_call_end` - Tool execution finished
- `text_delta` - Text streaming from LLM
- `thinking_delta` - Thinking content streaming

**API methods:**
- `pi.get_context()` - Get agent context
- `pi.get_settings()` - Get agent settings
- `pi.get_session_manager()` - Get session manager
- `pi.execute_command(command, args)` - Execute a command
- `pi.get_commands()` - List registered commands

### Installation

1. **User-level extensions** (available in all projects):
   ```bash
   mkdir -p ~/.pi/extensions
   cp your_extension.py ~/.pi/extensions/
   ```

2. **Project-level extensions** (project-specific):
   ```bash
   mkdir -p ./extensions
   cp your_extension.py ./extensions/
   ```

3. **Restart the agent** - Extensions are loaded at startup:
   ```bash
   pi
   ```

### Best Practices

1. **Error handling**: Always wrap tool logic in try/except
2. **Timeouts**: Use timeouts for subprocess calls
3. **Documentation**: Add docstrings and clear descriptions
4. **Return values**: Return clear success/error messages
5. **Type hints**: Use Pydantic models for tool parameters
6. **Testing**: Test your extension before deploying

### Debugging

If your extension fails to load:

1. Check the error message at startup
2. Verify your `setup()` function exists
3. Ensure all imports are available
4. Test parameter models validate correctly
5. Check that tool functions are async

### Example: Minimal Extension

```python
def setup(pi):
    from pydantic import BaseModel, Field

    class EchoParams(BaseModel):
        message: str = Field(..., description="Message to echo")

    @pi.register_tool(
        name="echo",
        description="Echo a message back",
        parameters=EchoParams,
    )
    async def echo_tool(message: str) -> str:
        return f"Echo: {message}"

    print("✅ Echo extension loaded!")
```

## Resources

- [Extension API Reference](../docs/extensions.md)
- [Pydantic Documentation](https://docs.pydantic.dev/)
- [Agent Events Reference](../docs/events.md)

## Contributing

Have a useful extension? Consider sharing it:

1. Fork the repository
2. Add your extension to `examples/extensions/`
3. Update this README
4. Submit a pull request

## License

All example extensions are provided under the same license as Pi Coding Agent.

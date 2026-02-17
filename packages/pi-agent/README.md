# Pi-Agent

Stateful agent runtime with tool execution and event streaming.

## Features

- 🔄 **Agent Loop**: Automatic tool execution with multi-turn conversations
- 🔧 **Tool Management**: Easy tool registration and execution
- 📡 **Event System**: Subscribe to agent events (tool calls, turns, completion)
- 🎯 **Steering Messages**: Guide agent behavior dynamically
- 🔗 **Follow-up Messages**: Multi-step workflows
- 🎮 **State Management**: Complete conversation state tracking

## Installation

```bash
cd packages/pi-agent
poetry install
```

## Quick Start

### Basic Agent

```python
import asyncio
from pi_agent import Agent
from pi_ai.api import get_model
from pydantic import BaseModel, Field

# Create a model
model = get_model("openai", "gpt-4o-mini")

# Create an agent
agent = Agent(model)

# Register a tool
class CalculatorParams(BaseModel):
    a: int = Field(..., description="First number")
    b: int = Field(..., description="Second number")
    operation: str = Field(..., description="Operation: add, subtract, multiply, divide")

async def calculator(a: int, b: int, operation: str) -> float:
    if operation == "add":
        return a + b
    elif operation == "subtract":
        return a - b
    elif operation == "multiply":
        return a * b
    elif operation == "divide":
        return a / b
    else:
        raise ValueError(f"Unknown operation: {operation}")

agent.register_tool(
    name="calculator",
    description="Perform arithmetic operations",
    parameters=CalculatorParams,
    execute_fn=calculator
)

# Subscribe to events
def on_tool_call(event):
    print(f"Tool called: {event['tool_name']}")
    print(f"Arguments: {event['arguments']}")

agent.on("agent_tool_call_start", on_tool_call)

# Run the agent
async def main():
    state = await agent.run_once("What is 15 + 27?")

    # Get the final response
    final_message = state.context.messages[-1]
    print(f"Final response: {final_message.content[0].text}")

asyncio.run(main())
```

### Agent with Steering

```python
import asyncio
from pi_agent import Agent
from pi_ai.api import get_model

model = get_model("anthropic", "claude-sonnet-4-20250514")
agent = Agent(model)

async def main():
    # Run with steering messages
    state = await agent.run(
        steering_messages=[
            "Be extremely concise",
            "Use bullet points"
        ]
    )

    print(state.context.messages[-1].content[0].text)

asyncio.run(main())
```

### Multi-Step Workflow

```python
import asyncio
from pi_agent import Agent
from pi_ai.api import get_model

model = get_model("openai", "gpt-4o-mini")
agent = Agent(model)

async def main():
    # Run with follow-up messages
    state = await agent.run(
        follow_up_messages=[
            "Analyze the data",
            "Summarize your findings",
            "Suggest next steps"
        ]
    )

asyncio.run(main())
```

## API Reference

### Agent

Main agent class for managing conversations with tool execution.

#### `__init__(model, context=None)`

Create a new agent.

**Parameters:**
- `model` (Model): LLM model configuration
- `context` (Context, optional): Initial conversation context

#### `register_tool(name, description, parameters, execute_fn)`

Register a tool with the agent.

**Parameters:**
- `name` (str): Tool name
- `description` (str): Tool description
- `parameters` (BaseModel): Pydantic model for parameters
- `execute_fn` (Callable): Async function to execute the tool

#### `on(event_type, handler)`

Subscribe to an event.

**Parameters:**
- `event_type` (str): Event type to subscribe to
- `handler` (Callable): Event handler (sync or async)

**Event Types:**
- `agent_turn_start` - Turn started
- `agent_turn_end` - Turn completed
- `agent_tool_call_start` - Tool call started
- `agent_tool_call_end` - Tool call completed
- `agent_complete` - Agent finished
- `agent_error` - Error occurred
- Plus all LLM events (`text_delta`, `thinking_delta`, etc.)

#### `async run(steering_messages=None, follow_up_messages=None, stream_llm_events=True)`

Run the complete agent loop.

**Parameters:**
- `steering_messages` (List[str], optional): Steering messages
- `follow_up_messages` (List[str], optional): Follow-up messages
- `stream_llm_events` (bool): Whether to emit LLM events

**Returns:**
- `AgentState`: Final agent state

#### `async run_once(user_message, stream_llm_events=True)`

Run a single turn with a user message.

**Parameters:**
- `user_message` (str): User message content
- `stream_llm_events` (bool): Whether to emit LLM events

**Returns:**
- `AgentState`: Final agent state

### AgentState

Complete state of an agent conversation.

**Attributes:**
- `model` (Model): LLM model
- `context` (Context): Conversation context
- `tools` (List[AgentTool]): Available tools
- `steering_messages` (List[SteeringMessage]): Steering messages
- `follow_up_messages` (List[FollowUpMessage]): Follow-up messages
- `max_turns` (int): Maximum turns (default: 10)
- `current_turn` (int): Current turn number

**Methods:**
- `add_message(message)` - Add message to context
- `add_steering(content, priority=0)` - Add steering message
- `add_follow_up(content)` - Add follow-up message
- `get_tool(name)` - Get tool by name
- `clear_steering()` - Clear steering messages
- `pop_follow_up()` - Pop next follow-up message

## Event System

The agent emits events during execution:

```python
agent = Agent(model)

# Subscribe to tool calls
@agent.on("agent_tool_call_start")
def on_tool_start(event):
    print(f"Calling tool: {event['tool_name']}")

@agent.on("agent_tool_call_end")
def on_tool_end(event):
    if event.get('error'):
        print(f"Tool failed: {event['error']}")
    else:
        print(f"Tool result: {event['result']}")

# Subscribe to LLM events
@agent.on("text_delta")
def on_text(event):
    print(event['delta'], end='', flush=True)

# Subscribe to completion
@agent.on("agent_complete")
def on_complete(event):
    print(f"\nCompleted in {event['total_turns']} turns")
```

## Testing

```bash
# Run unit tests
poetry run pytest tests/ -v

# Run specific test file
poetry run pytest tests/test_agent.py -v
```

## Examples

See the examples directory for more comprehensive examples:
- Basic agent with tools
- Multi-turn conversations
- Event handling
- Steering and follow-up messages

## License

MIT

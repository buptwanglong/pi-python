# Assistant Interactive Flow Refactor Design

**Date**: 2026-03-14
**Status**: Approved
**Author**: Claude (via brainstorming skill)

## Overview

重构 basket-assistant 的交互流程配置，提高可维护性、可扩展性和可测试性。当前交互流程代码分散在多个文件中，命令处理、输入预处理、模式初始化等逻辑混杂在一起，难以理解和维护。

## Goals

**主要目标**（按优先级排序）：
1. **职责清晰**：命令处理、输入预处理、模式初始化各自独立，职责明确
2. **易于扩展**：添加新命令 < 10 行代码，添加新模式 < 100 行代码
3. **易于测试**：每个组件可独立测试，目标覆盖率 85%+

**成功指标**：
- 添加新命令只需在 CommandRegistry 注册一个处理函数（~5-10 行）
- 添加新模式只需继承 InteractionMode 并实现 2 个方法（~80-100 行）
- 测试覆盖率：CommandRegistry 90%+，InputProcessor 85%+，Modes 80%+
- 代码结构清晰，新人能在 30 分钟内理解架构

## Current Problems

### 1. 命令处理分散且重复

**当前实现**（`agent/run.py` 中的 `run_interactive()`）：
```python
# 66-139 行：大量 if-elif 语句处理命令
if user_input.lower() == "help":
    print_help(agent)
    continue

if user_input.lower() == "settings":
    print_settings(agent)
    continue

if user_input.strip().lower() in ("/plan", "/plan on", "/plan off"):
    on = user_input.strip().lower() != "/plan off"
    agent.set_plan_mode(on)
    print(f"Plan mode {'on' if on else 'off'}", flush=True)
    continue

if user_input.strip().lower() == "/sessions":
    sessions = await agent.session_manager.list_sessions()
    # ... 处理逻辑
    continue

if user_input.strip().lower().startswith("/open "):
    session_id = user_input.split(maxsplit=1)[1].strip()
    # ... 处理逻辑
    continue
```

**问题**：
- ❌ 命令处理逻辑硬编码在交互循环中
- ❌ 添加新命令需要修改核心流程代码
- ❌ 无法动态注册命令（extension 需要特殊处理）
- ❌ 难以测试单个命令

### 2. 输入处理流程复杂

**当前实现**（`agent/run.py` 的 100-140 行）：
```python
# 1. 检查 pending asks
if agent._pending_asks:
    print()
    try:
        resumed = await agent.try_resume_pending_ask(user_input, stream_llm_events=True)
        if resumed:
            print()
            continue
    except Exception as resume_err:
        logger.exception("Resume pending ask failed")
        print(f"\n❌ Error: {resume_err}", flush=True)
        continue

# 2. 处理 /skill 命令
invoked_skill_id = None
message_content = user_input

if user_input.strip().lower().startswith("/skill "):
    parts = user_input.split(maxsplit=2)
    if len(parts) < 2:
        print("Usage: /skill <id> [your message]")
        continue
    invoked_skill_id = parts[1].strip()
    message_content = parts[2].strip() if len(parts) > 2 else ""
    # ... 更多逻辑

# 3. 处理 extension 命令
elif user_input.startswith("/"):
    command_parts = user_input.split(maxsplit=1)
    command = command_parts[0]
    args = command_parts[1] if len(command_parts) > 1 else ""

    if agent.extension_loader.extension_api.execute_command(command, args):
        continue
    else:
        print(f"Unknown command: {command}")
        # ... 错误处理
        continue
```

**问题**：
- ❌ 多个处理步骤混在一起，难以理解执行顺序
- ❌ 错误处理分散在各处
- ❌ 无法复用这个处理逻辑（TUI 模式需要重新实现）

### 3. 模式初始化重复

**当前实现**：

**CLI 模式**（`agent/run.py`）：
```python
async def run_interactive(agent) -> None:
    from basket_assistant.core.events import EventPublisher
    from basket_assistant.adapters import CLIAdapter

    publisher = EventPublisher(agent.agent)
    cli_adapter = CLIAdapter(publisher, verbose=agent.settings.agent.verbose)

    try:
        if agent._session_id is None:
            session_id = await agent.session_manager.create_session(agent.model.id)
            await agent.set_session_id(session_id)

        # ... 交互循环
    finally:
        cli_adapter.cleanup()
        publisher.cleanup()
```

**TUI 模式**（`modes/tui.py`）：
```python
async def run_tui_mode(coding_agent, max_cols: Optional[int] = None) -> None:
    if not getattr(coding_agent, "_session_id", None):
        session_id = await coding_agent.session_manager.create_session(
            coding_agent.model.id
        )
        await coding_agent.set_session_id(session_id)
        logger.info(f"Created new session: {session_id}")

    app = PiCodingAgentApp(...)

    from basket_assistant.core.events import EventPublisher
    from basket_assistant.adapters import TUIAdapter

    publisher = EventPublisher(coding_agent.agent)
    tui_adapter = TUIAdapter(publisher, app.event_bus)

    try:
        # ... TUI 循环
    finally:
        tui_adapter.cleanup()
        publisher.cleanup()
```

**问题**：
- ❌ Session 创建逻辑重复
- ❌ Publisher + Adapter 初始化逻辑重复
- ❌ Cleanup 逻辑重复
- ❌ 添加新模式需要复制大量样板代码

## Proposed Solution: CommandRegistry + InteractionMode Pattern

### Architecture

```
┌─────────────────────────────────────────────────────┐
│              InteractionMode (抽象基类)              │
│  - agent: AssistantAgent                           │
│  - command_registry: CommandRegistry               │
│  - input_processor: InputProcessor                 │
│  ────────────────────────────────────────────────  │
│  + setup_publisher_adapter() → (publisher, adapter)│
│  + run() → None                                    │
│  + process_and_run_agent(input) → bool             │
└──────────────────┬──────────────────────────────────┘
                   │ 继承
        ┌──────────┼──────────┬─────────────┐
        │                     │             │
   ┌────▼─────┐        ┌─────▼────┐   ┌────▼──────┐
   │CLIMode   │        │TUIMode   │   │AttachMode │
   │          │        │          │   │           │
   └──────────┘        └──────────┘   └───────────┘

┌────────────────────┐        ┌──────────────────────┐
│ CommandRegistry    │        │  InputProcessor      │
│ ─────────────────  │        │  ─────────────────── │
│ + register()       │        │ + process() →        │
│ + execute()        │        │   ProcessResult      │
│ + has_command()    │        │                      │
└────────────────────┘        │ - handle_pending_ask │
                              │ - handle_skill       │
                              │ - handle_extension   │
                              └──────────────────────┘
```

**核心原则**：
- **单一职责**：每个类只做一件事
- **依赖注入**：InteractionMode 依赖 CommandRegistry 和 InputProcessor
- **模板方法模式**：基类定义流程骨架，子类实现具体细节
- **策略模式**：不同的 Mode 是不同的交互策略

### Directory Structure

```
basket_assistant/
  interaction/                   # 新增：交互层
    __init__.py                 # 公开 API
    commands/
      __init__.py
      registry.py               # CommandRegistry（150行）
      handlers.py               # 内置命令处理器（200行）
    processors/
      __init__.py
      input_processor.py        # InputProcessor（150行）
    modes/
      __init__.py
      base.py                  # InteractionMode 基类（100行）
      cli.py                   # CLIMode（80行）
      tui.py                   # TUIMode（80行）
      attach.py                # AttachMode（100行）
    errors.py                  # 异常定义（30行）

tests/
  interaction/                  # 新增：交互层测试
    commands/
      test_registry.py         # 150行
      test_handlers.py         # 100行
    processors/
      test_input_processor.py  # 120行
    modes/
      test_base.py            # 80行
      test_cli_mode.py        # 80行
      test_tui_mode.py        # 80行
    test_integration.py       # 100行
```

**代码行数估算**：
- 新增代码：~900 行（核心逻辑）
- 测试代码：~700 行
- 删除代码：~400 行（旧的重复逻辑）
- **净增加**：~1200 行（但结构更清晰，可维护性大幅提升）

## Component Design

### 1. CommandRegistry

**职责**：
- 管理所有命令的注册和执行
- 支持同步和异步命令
- 支持命令别名
- 提供统一的错误处理

**接口设计**：

```python
from typing import Callable, Optional
from dataclasses import dataclass

@dataclass
class Command:
    """命令定义"""
    name: str                    # 命令名称，如 "plan"
    handler: Callable            # 处理函数
    description: str             # 描述
    is_async: bool = False       # 是否异步
    aliases: list[str] = None    # 别名，如 ["/plan", "/plan on"]

class CommandRegistry:
    """命令注册表"""

    def __init__(self, agent: Any):
        """初始化，自动注册内置命令"""
        self.agent = agent
        self._commands: Dict[str, Command] = {}
        self._alias_map: Dict[str, str] = {}
        self._register_builtin_commands()

    def register(
        self,
        name: str,
        handler: Callable[[str], tuple[bool, Optional[str]]],
        description: str,
        aliases: Optional[list[str]] = None
    ) -> None:
        """注册同步命令

        Args:
            name: 命令名称（不带斜杠）
            handler: 处理函数，签名 (args: str) -> (success: bool, error: str)
            description: 命令描述
            aliases: 命令别名列表
        """
        pass

    def register_async(
        self,
        name: str,
        handler: Callable[[str], tuple[bool, Optional[str]]],
        description: str,
        aliases: Optional[list[str]] = None
    ) -> None:
        """注册异步命令"""
        pass

    async def execute(self, command_text: str) -> tuple[bool, Optional[str]]:
        """执行命令

        Args:
            command_text: 用户输入的完整命令（如 "/plan on"）

        Returns:
            (success, error):
                - (True, None): 命令处理成功
                - (False, "error msg"): 命令执行失败
        """
        pass

    def has_command(self, text: str) -> bool:
        """判断文本是否是命令"""
        return text.strip().startswith("/") and \
               text.strip().split()[0].lower() in self._alias_map

    def list_commands(self) -> list[Command]:
        """列出所有命令"""
        return list(self._commands.values())
```

**内置命令**（`handlers.py`）：

| 命令 | 别名 | 描述 | 同步/异步 |
|------|------|------|----------|
| help | help, /help | 显示帮助信息 | 同步 |
| settings | settings, /settings | 显示当前设置 | 同步 |
| todos | /todos | 切换 todo 显示模式 | 同步 |
| plan | /plan, /plan on, /plan off | 切换 plan 模式 | 同步 |
| sessions | /sessions | 列出所有 session | 异步 |
| open | /open | 切换 session | 异步 |

**使用示例**：

```python
# Extension 注册自定义命令
def my_command_handler(args: str) -> tuple[bool, Optional[str]]:
    print(f"Executing my command with args: {args}")
    return True, None

registry.register(
    "mycommand",
    my_command_handler,
    "My custom command",
    aliases=["/mycommand", "/mc"]
)
```

### 2. InputProcessor

**职责**：
- 预处理用户输入
- 按优先级处理不同类型的输入（pending ask > 命令 > skill > extension > 普通）
- 返回处理结果指示下一步动作

**接口设计**：

```python
from dataclasses import dataclass
from typing import Optional
from basket_ai.types import UserMessage

@dataclass
class ProcessResult:
    """输入处理结果"""
    action: str  # "continue" | "send_to_agent" | "handled"
    message: Optional[UserMessage] = None  # 如果需要发送给 agent
    invoked_skill_id: Optional[str] = None  # 如果调用了 skill
    error: Optional[str] = None  # 如果有错误

class InputProcessor:
    """输入预处理器"""

    def __init__(self, agent: Any, command_registry: CommandRegistry):
        self.agent = agent
        self.command_registry = command_registry

    async def process(self, user_input: str) -> ProcessResult:
        """处理用户输入

        处理顺序（优先级从高到低）：
        1. Pending ask（最高优先级）
        2. 命令（/plan, /todos 等）
        3. Skill 调用（/skill <id>）
        4. Extension 命令
        5. 普通输入（发送给 agent）

        Args:
            user_input: 用户输入的文本

        Returns:
            ProcessResult 表示处理结果
        """
        # 1. 处理 pending ask
        if self.agent._pending_asks:
            handled = await self._handle_pending_ask(user_input)
            if handled:
                return ProcessResult(action="handled")

        # 2. 处理命令
        if self.command_registry.has_command(user_input):
            success, error = await self.command_registry.execute(user_input)
            if success:
                return ProcessResult(action="handled")
            # 命令失败，继续尝试其他处理

        # 3. 处理 skill 调用
        if user_input.strip().lower().startswith("/skill "):
            skill_id, message = self._parse_skill_input(user_input)
            if skill_id:
                user_msg = self._create_user_message(message)
                return ProcessResult(
                    action="send_to_agent",
                    message=user_msg,
                    invoked_skill_id=skill_id
                )

        # 4. 处理 extension 命令
        if user_input.startswith("/"):
            handled = self._handle_extension_command(user_input)
            if handled:
                return ProcessResult(action="handled")
            else:
                # 未知命令
                return ProcessResult(
                    action="handled",
                    error=f"Unknown command: {user_input.split()[0]}"
                )

        # 5. 普通输入
        user_msg = self._create_user_message(user_input)
        return ProcessResult(action="send_to_agent", message=user_msg)
```

**处理流程图**：

```
User Input
    ↓
是 Pending Ask？ → 是 → 处理并返回 handled
    ↓ 否
是命令？(/plan) → 是 → 执行命令 → 返回 handled
    ↓ 否
是 Skill？(/skill) → 是 → 解析参数 → 返回 send_to_agent + skill_id
    ↓ 否
是 Extension 命令？(/) → 是 → 执行 extension → 返回 handled
    ↓ 否
普通输入 → 返回 send_to_agent
```

### 3. InteractionMode (Base Class)

**职责**：
- 提供交互模式的通用框架
- 管理 agent、command_registry、input_processor 的生命周期
- 定义模板方法，子类实现具体细节

**接口设计**：

```python
from abc import ABC, abstractmethod
from typing import Any, Optional, Tuple

class InteractionMode(ABC):
    """交互模式基类"""

    def __init__(self, agent: Any):
        self.agent = agent
        self.command_registry = CommandRegistry(agent)
        self.input_processor = InputProcessor(agent, self.command_registry)
        self.publisher: Optional[Any] = None
        self.adapter: Optional[Any] = None

    @abstractmethod
    def setup_publisher_adapter(self) -> Tuple[Any, Any]:
        """设置 publisher 和 adapter（子类实现）

        Returns:
            (publisher, adapter) 元组
        """
        pass

    @abstractmethod
    async def run(self) -> None:
        """运行交互模式（子类实现）"""
        pass

    async def initialize(self) -> None:
        """初始化（创建 session、设置 publisher）"""
        # 创建或恢复 session
        if not self.agent._session_id:
            session_id = await self.agent.session_manager.create_session(
                self.agent.model.id
            )
            await self.agent.set_session_id(session_id)

        # 设置 publisher 和 adapter
        self.publisher, self.adapter = self.setup_publisher_adapter()

    async def cleanup(self) -> None:
        """清理资源"""
        if self.adapter:
            self.adapter.cleanup()
        if self.publisher:
            self.publisher.cleanup()

    async def process_and_run_agent(
        self,
        user_input: str,
        stream: bool = True
    ) -> bool:
        """处理输入并运行 agent（通用流程）

        Args:
            user_input: 用户输入
            stream: 是否流式输出

        Returns:
            是否应该继续（False 表示退出）
        """
        # 特殊命令：exit/quit
        if user_input.lower() in ["exit", "quit"]:
            return False

        # 处理输入
        result = await self.input_processor.process(user_input)

        if result.action == "handled":
            # 已处理，不需要调用 agent
            if result.error:
                print(f"❌ {result.error}")
            return True

        if result.action == "send_to_agent":
            # 记录消息数量，用于错误恢复
            n_before = len(self.agent.context.messages)

            # 添加消息
            self.agent.context.messages.append(result.message)

            try:
                # 运行 agent
                await self.agent._run_with_trajectory_if_enabled(
                    stream_llm_events=stream,
                    invoked_skill_id=result.invoked_skill_id
                )

                # 保存 session
                if self.agent._session_id:
                    new_messages = self.agent.context.messages[n_before:]
                    if new_messages:
                        await self.agent.session_manager.append_messages(
                            self.agent._session_id, new_messages
                        )

            except KeyboardInterrupt:
                # 用户中断
                logger.info("User interrupted agent execution")
                self.agent.context.messages = self.agent.context.messages[:n_before]
                raise
            except Exception as e:
                # Agent 执行失败，恢复上下文
                logger.exception("Agent execution failed")
                self.agent.context.messages = self.agent.context.messages[:n_before]
                print(f"\n❌ Error: {e}")
                if self.agent.settings.agent.verbose:
                    import traceback
                    traceback.print_exc()
                print("Context has been restored to previous state.")

        return True
```

### 4. Concrete Modes

#### CLIMode

```python
class CLIMode(InteractionMode):
    """CLI 交互模式（REPL）"""

    def __init__(self, agent: Any, verbose: bool = False):
        super().__init__(agent)
        self.verbose = verbose

    def setup_publisher_adapter(self) -> Tuple[Any, Any]:
        """设置 CLI 的 publisher 和 adapter"""
        from basket_assistant.core.events import EventPublisher
        from basket_assistant.adapters import CLIAdapter

        publisher = EventPublisher(self.agent.agent)
        adapter = CLIAdapter(publisher, verbose=self.verbose)
        return publisher, adapter

    async def run(self) -> None:
        """运行 CLI 交互循环"""
        await self.initialize()

        try:
            print("Basket - Interactive Mode")
            print("Type 'exit' or 'quit' to quit, 'help' for help")
            print("-" * 50)

            while True:
                try:
                    # 显示 todo 列表
                    if self.agent._current_todos:
                        self._print_todos()

                    # 获取用户输入
                    user_input = input("\n> ").strip()
                    if not user_input:
                        continue

                    # 处理输入并运行 agent
                    print()
                    should_continue = await self.process_and_run_agent(user_input)
                    print()

                    if not should_continue:
                        print("Goodbye!")
                        break

                except KeyboardInterrupt:
                    print("\n\nInterrupted. Type 'exit' to quit.")
                    continue
                except Exception as e:
                    logger.exception("CLI loop error")
                    print(f"\n❌ Unexpected error: {e}")
        finally:
            await self.cleanup()
```

#### TUIMode

```python
class TUIMode(InteractionMode):
    """TUI 交互模式（Textual UI）"""

    def __init__(self, agent: Any, max_cols: Optional[int] = None):
        super().__init__(agent)
        self.max_cols = max_cols
        self.app: Optional[PiCodingAgentApp] = None

    def setup_publisher_adapter(self) -> Tuple[Any, Any]:
        """设置 TUI 的 publisher 和 adapter"""
        from basket_assistant.core.events import EventPublisher
        from basket_assistant.adapters import TUIAdapter

        publisher = EventPublisher(self.agent.agent)
        adapter = TUIAdapter(publisher, self.app.event_bus)
        return publisher, adapter

    async def run(self) -> None:
        """运行 TUI 交互循环"""
        # 先创建 app（需要 event_bus）
        from basket_tui.app import PiCodingAgentApp
        self.app = PiCodingAgentApp(
            agent=self.agent.agent,
            coding_agent=self.agent,
            max_cols=self.max_cols,
        )

        # 初始化（包括 publisher + adapter）
        await self.initialize()

        try:
            # 设置输入处理器
            async def handle_input(text: str) -> None:
                await self.process_and_run_agent(text, stream=True)

            self.app.set_input_handler(handle_input)

            # 运行 TUI app
            await self.app.run_async()
        finally:
            await self.cleanup()
```

#### AttachMode

```python
class AttachMode(InteractionMode):
    """Attach 模式（远程 TUI）"""

    def __init__(
        self,
        agent: Any,
        app: Any,
        bind_host: str = "127.0.0.1",
        bind_port: int = 7681,
    ):
        super().__init__(agent)
        self.app = app
        self.bind_host = bind_host
        self.bind_port = bind_port

    def setup_publisher_adapter(self) -> Tuple[Any, Any]:
        """复用 TUIAdapter"""
        from basket_assistant.core.events import EventPublisher
        from basket_assistant.adapters import TUIAdapter

        publisher = EventPublisher(self.agent.agent)
        adapter = TUIAdapter(publisher, self.app.event_bus)
        return publisher, adapter

    async def run(self) -> None:
        """运行 Attach 模式"""
        await self.initialize()

        try:
            # 设置输入处理器
            async def handle_input(text: str) -> None:
                await self.process_and_run_agent(text, stream=True)

            self.app.set_input_handler(handle_input)

            # 启动远程服务器（从 modes/attach.py 迁移逻辑）
            logger.info(f"Starting attach mode on {self.bind_host}:{self.bind_port}")
            await self._run_attach_server()
        finally:
            await self.cleanup()
```

## Data Flow

### 用户输入流程

```
User Input: "/plan on"
     ↓
InteractionMode.process_and_run_agent("/plan on")
     ↓
InputProcessor.process("/plan on")
     ↓
检查：是 pending ask？ → 否
检查：是命令？ → 是
     ↓
CommandRegistry.execute("/plan on")
     ↓
解析：cmd="/plan", args="on"
查找：alias_map["/plan"] → "plan"
获取：commands["plan"] → Command(handler=handle_plan)
     ↓
执行：handle_plan("on")
     ↓
     agent.set_plan_mode(True)
     print("Plan mode on")
     return (True, None)
     ↓
返回：ProcessResult(action="handled")
     ↓
InteractionMode：不调用 agent，继续循环
```

### 普通输入流程

```
User Input: "Hello world"
     ↓
InteractionMode.process_and_run_agent("Hello world")
     ↓
InputProcessor.process("Hello world")
     ↓
检查：是 pending ask？ → 否
检查：是命令？ → 否
检查：是 skill？ → 否
检查：是 extension？ → 否
     ↓
创建 UserMessage("Hello world")
返回：ProcessResult(action="send_to_agent", message=msg)
     ↓
InteractionMode.process_and_run_agent:
     agent.context.messages.append(msg)
     await agent._run_with_trajectory_if_enabled()
     ↓
Agent 执行 → 生成响应
     ↓
EventPublisher 发布事件 → Adapter 显示输出
     ↓
继续循环
```

## Error Handling

### 错误处理策略

#### 1. CommandRegistry 层

```python
async def execute(self, command_text: str) -> tuple[bool, Optional[str]]:
    """执行命令，捕获所有异常"""
    try:
        # ... 执行逻辑
        return True, None
    except Exception as e:
        logger.exception(f"Command execution failed: {command_name}")
        # 返回错误，不抛出异常
        return False, str(e)
```

**原则**：
- ✅ 捕获所有异常，返回错误信息
- ✅ 记录详细日志
- ❌ 不抛出异常（让上层决定如何处理）

#### 2. InputProcessor 层

```python
async def process(self, user_input: str) -> ProcessResult:
    """处理输入，异常时降级为普通输入"""
    try:
        # ... 处理逻辑
        return ProcessResult(action="send_to_agent", message=msg)
    except Exception as e:
        logger.exception("Input processing failed")
        # 降级处理：当作普通输入
        user_msg = self._create_user_message(user_input)
        return ProcessResult(
            action="send_to_agent",
            message=user_msg,
            error=f"Input processing error: {e}"
        )
```

**原则**：
- ✅ 降级处理：出错时当作普通输入
- ✅ 返回错误信息（可选显示给用户）
- ❌ 不阻止用户继续使用

#### 3. InteractionMode 层

```python
async def process_and_run_agent(self, user_input: str) -> bool:
    """运行 agent，错误时恢复上下文"""
    n_before = len(self.agent.context.messages)

    try:
        # ... agent 执行
        return True
    except KeyboardInterrupt:
        # 用户中断
        self.agent.context.messages = self.agent.context.messages[:n_before]
        raise  # 向上抛出，让交互循环处理
    except Exception as e:
        # Agent 执行失败
        logger.exception("Agent execution failed")
        self.agent.context.messages = self.agent.context.messages[:n_before]
        print(f"\n❌ Error: {e}")
        if self.verbose:
            import traceback
            traceback.print_exc()
        print("Context has been restored to previous state.")
        return True  # 继续循环
```

**原则**：
- ✅ 恢复上下文（删除失败的消息）
- ✅ 显示错误信息
- ✅ 继续循环（不退出程序）
- ✅ KeyboardInterrupt 特殊处理（向上抛出）

### 异常定义

```python
# basket_assistant/interaction/errors.py

class InteractionError(Exception):
    """交互层基础异常"""
    pass

class CommandExecutionError(InteractionError):
    """命令执行错误"""
    pass

class InputProcessingError(InteractionError):
    """输入处理错误"""
    pass

class ModeInitializationError(InteractionError):
    """模式初始化错误"""
    pass
```

## Testing Strategy

### 测试覆盖率目标

| 组件 | 目标覆盖率 | 测试行数 |
|------|-----------|---------|
| CommandRegistry | 90%+ | 150 |
| BuiltinCommandHandlers | 85%+ | 100 |
| InputProcessor | 85%+ | 120 |
| InteractionMode (base) | 85%+ | 80 |
| CLIMode | 80%+ | 80 |
| TUIMode | 80%+ | 80 |
| AttachMode | 75%+ | 60 |
| Integration tests | - | 100 |
| **总计** | **85%+** | **~770** |

### 单元测试

#### CommandRegistry 测试

```python
# tests/interaction/commands/test_registry.py

import pytest
from basket_assistant.interaction.commands import CommandRegistry

@pytest.fixture
def registry(mock_agent):
    return CommandRegistry(mock_agent)

def test_register_command(registry):
    """测试注册命令"""
    called = []
    def handler(args):
        called.append(args)
        return True, None

    registry.register("test", handler, "Test", aliases=["/test"])
    assert registry.has_command("/test")

@pytest.mark.asyncio
async def test_execute_command(registry):
    """测试执行命令"""
    success, error = await registry.execute("/help")
    assert success is True
    assert error is None

@pytest.mark.asyncio
async def test_unknown_command(registry):
    """测试未知命令"""
    success, error = await registry.execute("/unknown")
    assert success is False
    assert "Unknown command" in error

@pytest.mark.asyncio
async def test_command_with_args(registry):
    """测试带参数的命令"""
    success, error = await registry.execute("/plan on")
    assert success is True

@pytest.mark.asyncio
async def test_async_command(registry):
    """测试异步命令"""
    success, error = await registry.execute("/sessions")
    assert success is True
```

#### InputProcessor 测试

```python
# tests/interaction/processors/test_input_processor.py

import pytest
from basket_assistant.interaction.processors import InputProcessor

@pytest.mark.asyncio
async def test_normal_input(processor):
    """测试普通输入"""
    result = await processor.process("Hello")
    assert result.action == "send_to_agent"
    assert result.message.content == "Hello"

@pytest.mark.asyncio
async def test_command_input(processor):
    """测试命令输入"""
    result = await processor.process("/help")
    assert result.action == "handled"

@pytest.mark.asyncio
async def test_skill_input(processor):
    """测试 skill 调用"""
    result = await processor.process("/skill refactor Please help")
    assert result.action == "send_to_agent"
    assert result.invoked_skill_id == "refactor"
    assert "Please help" in result.message.content

@pytest.mark.asyncio
async def test_pending_ask(processor):
    """测试 pending ask 优先级"""
    processor.agent._pending_asks = [{"question": "Continue?"}]
    result = await processor.process("yes")
    assert result.action == "handled"

@pytest.mark.asyncio
async def test_extension_command(processor):
    """测试 extension 命令"""
    # Mock extension
    processor.agent.extension_loader.extension_api.execute_command = \
        lambda cmd, args: True

    result = await processor.process("/myext")
    assert result.action == "handled"
```

#### InteractionMode 测试

```python
# tests/interaction/modes/test_cli_mode.py

import pytest
from basket_assistant.interaction.modes import CLIMode

@pytest.mark.asyncio
async def test_initialization(mock_agent):
    """测试初始化"""
    mode = CLIMode(mock_agent)
    await mode.initialize()

    assert mode.publisher is not None
    assert mode.adapter is not None
    assert mode.agent._session_id is not None

@pytest.mark.asyncio
async def test_cleanup(mock_agent):
    """测试清理"""
    mode = CLIMode(mock_agent)
    await mode.initialize()
    await mode.cleanup()

    # 验证资源已清理（适配器已取消订阅）
    assert len(mode.adapter._subscribers) == 0

@pytest.mark.asyncio
async def test_process_exit(mock_agent):
    """测试退出命令"""
    mode = CLIMode(mock_agent)
    await mode.initialize()

    result = await mode.process_and_run_agent("exit")
    assert result is False  # 应该退出

@pytest.mark.asyncio
async def test_process_normal(mock_agent):
    """测试普通输入"""
    mode = CLIMode(mock_agent)
    await mode.initialize()

    result = await mode.process_and_run_agent("Hello")
    assert result is True  # 继续循环
    assert len(mock_agent.context.messages) > 0
```

### 集成测试

```python
# tests/interaction/test_integration.py

import pytest
from basket_assistant.interaction.modes import CLIMode

@pytest.mark.asyncio
async def test_full_flow(mock_agent):
    """测试完整交互流程"""
    mode = CLIMode(mock_agent)
    await mode.initialize()

    try:
        # 测试命令
        result = await mode.process_and_run_agent("/help")
        assert result is True

        # 测试普通输入
        result = await mode.process_and_run_agent("Hello")
        assert result is True
        assert len(mock_agent.context.messages) > 0

        # 测试 skill 调用
        result = await mode.process_and_run_agent("/skill test Help me")
        assert result is True

        # 测试退出
        result = await mode.process_and_run_agent("exit")
        assert result is False
    finally:
        await mode.cleanup()

@pytest.mark.asyncio
async def test_error_recovery(mock_agent):
    """测试错误恢复"""
    mode = CLIMode(mock_agent)
    await mode.initialize()

    # 模拟 agent 执行失败
    mock_agent.set_should_fail(True)

    try:
        n_before = len(mock_agent.context.messages)
        result = await mode.process_and_run_agent("This will fail")

        # 应该继续循环
        assert result is True
        # 上下文已恢复
        assert len(mock_agent.context.messages) == n_before
    finally:
        await mode.cleanup()

@pytest.mark.asyncio
async def test_command_precedence(mock_agent):
    """测试输入处理优先级"""
    mode = CLIMode(mock_agent)
    await mode.initialize()

    try:
        # Pending ask 优先级最高
        mock_agent._pending_asks = [{"question": "Continue?"}]
        result = await mode.process_and_run_agent("/help")  # 应该处理 ask，不是命令
        assert result is True

        # 命令优先于普通输入
        mock_agent._pending_asks = []
        result = await mode.process_and_run_agent("/plan on")
        assert result is True
        assert mock_agent.get_plan_mode() is True
    finally:
        await mode.cleanup()
```

## Migration Strategy

### Phase 1: 实现新架构（1-2 天）

**目标**：创建所有新组件，不破坏现有代码

**任务**：
- [ ] 创建 `interaction/` 目录结构
- [ ] 实现 `CommandRegistry`（150 行）
- [ ] 实现 `BuiltinCommandHandlers`（200 行）
- [ ] 实现 `InputProcessor`（150 行）
- [ ] 实现 `InteractionMode` 基类（100 行）
- [ ] 实现 `CLIMode`（80 行）
- [ ] 实现 `TUIMode`（80 行）
- [ ] 实现 `AttachMode`（100 行）
- [ ] 编写单元测试（~500 行）

**验证**：
- 所有新代码通过单元测试
- 现有功能不受影响（不修改 `agent/run.py`）

### Phase 2: 迁移到新架构（2-3 天）

**目标**：逐步迁移现有代码到新架构

**任务**：
- [ ] 更新 `main.py`：使用 `CLIMode` 替代 `run_interactive()`
- [ ] 更新 `main.py`：使用 `TUIMode` 替代 `run_tui_mode()`
- [ ] 更新 `main.py`：使用 `AttachMode` 替代 `run_tui_mode_attach()`
- [ ] 运行现有所有测试，确保行为一致
- [ ] 添加集成测试（~200 行）

**验证**：
- 所有现有测试通过
- 集成测试覆盖关键场景
- 手动测试 CLI、TUI、Attach 模式

### Phase 3: 清理旧代码（1-2 天）

**目标**：删除重复代码，更新文档

**任务**：
- [ ] 删除 `agent/run.py` 中的 `run_interactive()`（保留辅助函数）
- [ ] 删除 `modes/tui.py` 中的重复逻辑
- [ ] 删除 `modes/attach.py` 中的重复逻辑
- [ ] 更新 `CLAUDE.md` 文档
- [ ] 更新 `README.md`（如果有）
- [ ] Code review

**验证**：
- 没有重复代码
- 文档准确反映新架构
- 所有测试通过

### 迁移风险和缓解措施

| 风险 | 影响 | 概率 | 缓解措施 |
|------|------|------|---------|
| 破坏现有功能 | 高 | 中 | 全面的集成测试 + 逐步迁移 |
| 性能下降 | 中 | 低 | 基准测试（命令执行、输入处理） |
| 用户体验变化 | 中 | 低 | 保持现有行为，只重构内部实现 |
| Extension 兼容性 | 中 | 中 | 保留 extension API，内部适配 |

## Performance Considerations

### 1. 命令查找优化

```python
# 使用字典查找，O(1) 时间复杂度
self._alias_map[cmd]  # 而不是遍历所有命令
```

**性能指标**：
- 命令查找：< 0.01ms
- 命令执行：取决于具体命令（通常 < 1ms）

### 2. 输入处理短路

```python
# 按优先级检查，找到就立即返回
if pending_ask:
    return ProcessResult(action="handled")
if is_command:
    return ProcessResult(action="handled")
# ... 避免不必要的检查
```

**性能指标**：
- 输入处理：< 0.1ms
- 完整流程（输入 → agent）：取决于 agent 执行时间

### 3. 事件发布

已在 EventPublisher 设计中优化：
- 同步发布（CLI/TUI）：无额外延迟
- 异步发布（WebSocket）：非阻塞

### 4. 基准测试

```python
# benchmarks/interaction_benchmark.py

import time
from basket_assistant.interaction.commands import CommandRegistry

def benchmark_command_lookup(registry, n=10000):
    """基准测试：命令查找"""
    start = time.perf_counter()
    for _ in range(n):
        registry.has_command("/plan")
    elapsed = time.perf_counter() - start
    print(f"Command lookup: {elapsed/n*1000:.4f} ms per call")

async def benchmark_command_execution(registry, n=1000):
    """基准测试：命令执行"""
    start = time.perf_counter()
    for _ in range(n):
        await registry.execute("/help")
    elapsed = time.perf_counter() - start
    print(f"Command execution: {elapsed/n*1000:.4f} ms per call")
```

**目标性能**：
- 命令查找：< 0.01ms
- 命令执行（/help）：< 1ms
- 输入处理：< 0.1ms

## Future Extensions

### 1. 命令自动补全

```python
class CommandRegistry:
    def get_completions(self, prefix: str) -> list[str]:
        """获取命令补全建议"""
        return [
            alias for alias in self._alias_map.keys()
            if alias.startswith(prefix)
        ]

# 在 CLI 中使用
completions = registry.get_completions("/pl")
# → ["/plan", "/plan on", "/plan off"]
```

### 2. 命令历史记录

```python
class InteractionMode:
    def __init__(self, agent):
        super().__init__(agent)
        self.command_history = []

    async def process_and_run_agent(self, user_input):
        # 记录命令
        if self.command_registry.has_command(user_input):
            self.command_history.append({
                "command": user_input,
                "timestamp": time.time()
            })
        # ...
```

### 3. 批量命令执行

```python
# 支持用 ; 分隔多个命令
"/plan on; /todos; Hello world"

# InputProcessor 解析并依次执行
async def process_batch(self, batch_input: str) -> list[ProcessResult]:
    commands = batch_input.split(";")
    results = []
    for cmd in commands:
        result = await self.process(cmd.strip())
        results.append(result)
    return results
```

### 4. 命令权限控制

```python
@dataclass
class Command:
    name: str
    handler: Callable
    description: str
    permissions: list[str] = None  # 新增：权限列表

# 检查权限
if command.permissions and not self._check_permissions(command.permissions):
    return False, "Permission denied"
```

### 5. 命令参数验证

```python
from pydantic import BaseModel

class PlanCommandArgs(BaseModel):
    """Plan 命令参数"""
    action: Literal["on", "off", "toggle"]

# 在 handler 中验证
def handle_plan(self, args: str) -> tuple[bool, str]:
    try:
        parsed = PlanCommandArgs(action=args or "toggle")
        # ...
    except ValidationError as e:
        return False, f"Invalid arguments: {e}"
```

## Success Criteria

### 功能指标

- ✅ 所有现有功能正常工作（CLI、TUI、Attach 模式）
- ✅ 添加新命令只需 5-10 行代码
- ✅ 添加新模式只需 80-100 行代码
- ✅ Extension 可以注册自定义命令

### 质量指标

- ✅ 测试覆盖率 85%+
- ✅ 所有单元测试通过
- ✅ 所有集成测试通过
- ✅ 无重复代码（DRY 原则）

### 性能指标

- ✅ 命令查找 < 0.01ms
- ✅ 命令执行 < 1ms（/help）
- ✅ 输入处理 < 0.1ms
- ✅ 无性能下降（与现有实现相比）

### 可维护性指标

- ✅ 新人能在 30 分钟内理解架构
- ✅ 代码结构清晰（每个类 < 200 行）
- ✅ 文档完整（CLAUDE.md 更新）
- ✅ 通过 Code Review

## Risks and Mitigations

| 风险 | 影响 | 概率 | 缓解措施 | 备选方案 |
|------|------|------|---------|---------|
| 破坏现有功能 | 高 | 中 | 全面测试 + 逐步迁移 | 回滚到旧代码 |
| 性能下降 | 中 | 低 | 基准测试 + 优化 | 优化热路径 |
| Extension 兼容性问题 | 中 | 中 | 保留旧 API + 内部适配 | 提供迁移指南 |
| 学习曲线陡峭 | 低 | 低 | 清晰文档 + 示例 | 提供教程 |
| 工期超期 | 中 | 中 | 分阶段交付 | 先完成核心功能 |

## Conclusion

此次重构通过引入 **CommandRegistry + InteractionMode 模式**，将交互流程配置从分散、重复、难以维护的状态，转变为清晰、模块化、易于扩展的架构。

**核心改进**：

1. **命令处理统一化**：所有命令在 CommandRegistry 中注册，支持动态注册和别名
2. **输入处理流程化**：InputProcessor 按优先级处理不同类型输入，逻辑清晰
3. **模式初始化标准化**：InteractionMode 基类封装通用逻辑，子类只实现差异部分
4. **错误处理分层化**：各层负责自己的错误处理，向上传递处理结果

**预期效果**：

- 添加新命令：从 20+ 行（修改核心逻辑）→ 5-10 行（注册处理函数）
- 添加新模式：从 150+ 行（复制粘贴）→ 80-100 行（继承基类）
- 代码可读性：从 "需要跟踪多个文件" → "每个组件职责明确"
- 测试覆盖率：从 60% → 85%+

这个设计为未来的扩展（WebUI、命令补全、权限控制等）打下了坚实的基础。
